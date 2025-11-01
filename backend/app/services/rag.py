import asyncio
from typing import List, Optional
import httpx

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..core.config import settings
from ..core.database import load_faiss_index
from ..models.document import DocumentInDB
from ..models.history import HistoryReference, create_history
from ..models.document import get_document_by_id, get_documents_by_user
from ..services.embedding import EmbeddingService


class RAGService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.provider = settings.llm_provider.lower()
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens
        self.max_context_length = settings.rag_max_context_length
        self._openai_client = None
        self._gemini_api_key = None
        self._gemini_base_url = "https://generativelanguage.googleapis.com/v1/models"
        
        # Initialize OpenAI client if needed
        if self.provider == "openai" and settings.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.openai_api_key)
                print(f"[RAG] OpenAI client initialized successfully with model: {self.model}")
            except Exception as e:
                print(f"[RAG] Failed to initialize OpenAI client: {e}")
                import traceback
                print(f"[RAG] Traceback: {traceback.format_exc()}")
                self._openai_client = None
        
        # Initialize Gemini if needed
        if self.provider == "gemini":
            self._gemini_api_key = settings.gemini_api_key
            if self._gemini_api_key:
                print(f"[RAG] Gemini API initialized successfully with model: {self.model}")
            else:
                print("[RAG] Gemini API key not found, falling back to local generation")
                self.provider = "local"
        
        if self.provider == "openai" and self._openai_client is None:
            print("[RAG] Falling back to local generation mode")
            self.provider = "local"

    async def ask(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        question: str,
        document_id: Optional[str] = None,
        top_k: Optional[int] = None,  # Deprecated: kept for backward compatibility but will be auto-calculated
        conversation_id: Optional[str] = None,  # Group Q&As in the same conversation
    ) -> dict:
        # Auto-calculate top_k based on max_context_length
        # We'll dynamically select chunks until we reach max_context_length

        documents: List[DocumentInDB] = []
        if document_id:
            doc = await get_document_by_id(db, document_id)
            if not doc or doc.user_id != user_id:
                raise ValueError("Document not found or not accessible")
            documents = [doc]
        else:
            documents = await get_documents_by_user(db, user_id)

        question_embeddings = await self.embedding_service.embed_texts([question])
        if not question_embeddings:
            return {
                "answer": "Không thể tạo embedding cho câu hỏi.",
                "references": [],
                "documents": [],
            }

        query_vector = np.array(question_embeddings, dtype="float32")
        results = []

        # Search with a larger initial top_k to have more candidates for context selection
        # We'll search up to 50 chunks initially, then filter by context length
        for doc in documents:
            namespace = doc.faiss_namespace or f"user_{doc.user_id}_doc_{doc.id}"
            index = load_faiss_index(namespace)
            if index is None or index.ntotal == 0:
                continue
            if index.d != query_vector.shape[1]:
                continue
            try:
                # Search for more candidates initially (up to 50), we'll filter by context length later
                search_k = min(50, index.ntotal)
                distances, ids = index.search(query_vector, search_k)
            except Exception:
                continue
            for dist, vector_id in zip(distances[0], ids[0]):
                if vector_id == -1:
                    continue
                similarity = float(1.0 / (1.0 + dist))
                results.append(
                    {
                        "document": doc,
                        "namespace": namespace,
                        "vector_id": int(vector_id),
                        "similarity": similarity,
                    }
                )

        if not results:
            return {
                "answer": "Không tìm thấy đoạn văn phù hợp trong tài liệu của bạn.",
                "references": [],
                "documents": [doc.id for doc in documents],
            }

        # Lấy metadata và nội dung chunk từ MongoDB
        references: List[HistoryReference] = []
        context_parts: List[str] = []

        # Boost chunks that contain keywords from the question
        question_lower = question.lower()
        question_keywords = [q.strip() for q in question_lower.replace("?", "").replace("!", "").split() if len(q.strip()) > 2]
        
        # Store original similarity for reference
        for item in results:
            item["original_similarity"] = item["similarity"]
        
        print(f"[RAG] Found {len(results)} candidate chunks, searching for content matching question keywords: {question_keywords[:5]}")
        
        # Get content previews for boosting - cache records to avoid duplicate queries
        for item in results:
            doc = item["document"]
            record = await db["embeddings"].find_one(
                {"document_id": doc.id, "vector_index": item["vector_id"]}
            )
            if not record:
                continue
            
            # Cache record and content for later use
            item["_record"] = record
            chunk_id = record.get("chunk_id")
            chunk_doc = None
            if chunk_id:
                try:
                    from bson import ObjectId
                    chunk_doc = await db["chunks"].find_one({"_id": ObjectId(chunk_id)})
                except Exception:
                    chunk_doc = await db["chunks"].find_one({"_id": chunk_id})
            content = (chunk_doc or {}).get("content") or record.get("content") or ""
            item["_content"] = content
            item["_chunk_doc"] = chunk_doc
            content_lower = content.lower()
            
            # Boost if content contains question keywords (especially section numbers)
            keyword_matches = sum(1 for kw in question_keywords if kw in content_lower)
            
            # Special boost for section numbers (phần 2, chương 1, etc.)
            import re
            if any(kw in ["phần", "chương", "part"] for kw in question_keywords):
                # Look for section numbers in content
                question_numbers = re.findall(r'\d+', question_lower)
                
                # Also find all subsection patterns (2.1, 2.2, 2.3, etc.) in question
                all_subsection_patterns = re.findall(r'\b\d+\.\d+\b', question_lower)
                
                # Check for main section number (e.g., "phần 2")
                matched_main_section = False
                for num in question_numbers:
                    if f"phần {num}" in content_lower or f"chương {num}" in content_lower or f"part {num}" in content_lower:
                        keyword_matches += 3  # Strong boost for matching section numbers
                        matched_main_section = True
                        
                        # Additional boost for subsections (2.1, 2.2, 2.3, etc.)
                        # If question asks for full section, boost all subsections
                        section_pattern = rf"{num}\.\d+"  # Pattern like "2.1", "2.2", "2.3"
                        if re.search(section_pattern, content_lower):
                            keyword_matches += 5  # Extra strong boost for subsections
                        break
                
                # Boost for specific subsection numbers (2.1, 2.2, 2.3) mentioned in question
                for subsec in all_subsection_patterns:
                    if subsec in content_lower:
                        keyword_matches += 8  # Very strong boost for exact subsection match
                        print(f"[RAG] Found exact subsection match: {subsec} in chunk {record.get('chunk_index', '?')}")
            
            if keyword_matches > 0:
                # Boost similarity by up to 0.3 for keyword matches
                boost = min(0.3, keyword_matches * 0.08)
                item["similarity"] = min(1.0, item["similarity"] + boost)
                item["keyword_matches"] = keyword_matches
                print(f"[RAG] Boosted chunk {record.get('chunk_index', '?')} by {boost:.3f} (matches: {keyword_matches})")
        
        # Sort by boosted similarity
        sorted_results = sorted(results, key=lambda r: r["similarity"], reverse=True)
        
        # Dynamically select chunks until we reach max_context_length
        # Priority: chunks with section numbers matching the question get included first
        selected_results = []
        priority_chunks = []  # Chunks with section matches
        regular_chunks = []  # Other chunks
        
        for item in sorted_results:
            # Check if this chunk contains section numbers that match the question
            content_lower = (item.get("_content", "") or "").lower()
            has_section_match = False
            
            if any(kw in ["phần", "chương", "part"] for kw in question_keywords):
                question_numbers = re.findall(r'\d+', question_lower)
                for num in question_numbers:
                    # Check for main section or subsections
                    if (f"phần {num}" in content_lower or f"chương {num}" in content_lower or 
                        re.search(rf"{num}\.\d+", content_lower)):
                        has_section_match = True
                        break
            
            if has_section_match:
                priority_chunks.append(item)
            else:
                regular_chunks.append(item)
        
        # Combine: priority chunks first, then regular chunks
        all_chunks_ordered = priority_chunks + regular_chunks
        
        current_context_length = 0
        for item in all_chunks_ordered:
            content = item.get("_content", "")
            content_length = len(content) if content else 0
            
            # Reserve space for question, formatting, etc. (~500 chars)
            if current_context_length + content_length + 500 > self.max_context_length:
                break
            
            selected_results.append(item)
            current_context_length += content_length
        
        print(f"[RAG] Selected {len(selected_results)} chunks after keyword boosting (context length: {current_context_length}/{self.max_context_length} chars)")
        print(f"[RAG] Priority chunks: {len(priority_chunks)}, Regular chunks: {len(regular_chunks)}")
        
        # If no conversation_id provided, use the first history ID as conversation starter
        # Otherwise, reuse the conversation_id to group Q&As
        final_conversation_id = conversation_id
        
        for idx, item in enumerate(selected_results):
            doc = item["document"]
            # Use cached record and content from boosting phase
            record = item.get("_record")
            content = item.get("_content")
            chunk_doc = item.get("_chunk_doc")
            
            if not record:
                # Fallback if not cached
                record = await db["embeddings"].find_one(
                    {"document_id": doc.id, "vector_index": item["vector_id"]}
                )
                if not record:
                    continue
                chunk_id = record.get("chunk_id")
                chunk_doc = None
                if chunk_id:
                    try:
                        from bson import ObjectId
                        chunk_doc = await db["chunks"].find_one({"_id": ObjectId(chunk_id)})
                    except Exception:
                        chunk_doc = await db["chunks"].find_one({"_id": chunk_id})
                content = (chunk_doc or {}).get("content") or record.get("content")
            preview = None
            if content:
                preview = content[:160]
                # Use cleaner format for context
                chunk_idx = record.get("chunk_index", "?")
                context_parts.append(f"Chunk {chunk_idx}:\n{content}")
                print(f"[RAG] Added chunk {chunk_idx} to context (similarity: {item['similarity']:.3f}, preview: {preview[:50]}...)")
            references.append(
                HistoryReference(
                    document_id=doc.id,
                    chunk_id=str(chunk_doc.get("_id")) if chunk_doc else chunk_id,
                    chunk_index=record.get("chunk_index"),
                    score=item["similarity"],
                    content_preview=preview,
                )
            )
        
        print(f"[RAG] Total context length: {sum(len(p) for p in context_parts)} characters")

        answer = await self._generate_answer(question, context_parts)

        # Create history with conversation_id to group Q&As
        history_record = await create_history(
            db, user_id, question, answer, references, document_id, final_conversation_id
        )

        # If this is a new conversation (no conversation_id), return the history ID as new conversation_id
        if not final_conversation_id:
            final_conversation_id = history_record.id

        return {
            "answer": answer,
            "references": references,
            "documents": [ref.document_id for ref in references if ref.document_id],
            "conversation_id": final_conversation_id,  # Return conversation_id for frontend to use
            "history_id": history_record.id,  # Also return history_id for reference
        }

    async def _generate_answer(self, question: str, context_parts: List[str]) -> str:
        context_text = "\n".join(context_parts) if context_parts else ""
        
        # Try Gemini first (default)
        if self.provider == "gemini" and self._gemini_api_key:
            try:
                prompt = f"""Bạn là trợ lý học tập chuyên nghiệp. Hãy trả lời câu hỏi một cách chi tiết và chính xác dựa trên ngữ cảnh được cung cấp. Trả lời bằng tiếng Việt. Nếu thông tin trong ngữ cảnh không đủ để trả lời, hãy nói rõ điều đó.

Dưới đây là các đoạn văn liên quan từ tài liệu:

{context_text}

Câu hỏi: {question}

Hãy trả lời câu hỏi một cách đầy đủ, chi tiết và chính xác DỰA TRÊN các đoạn văn được cung cấp ở trên. Nếu câu hỏi đề cập đến một phần/chương cụ thể (ví dụ: 'phần 2', 'chương 1'), hãy tìm và sử dụng các đoạn văn liên quan đến phần/chương đó. Chỉ sử dụng thông tin có trong các đoạn văn. Nếu không có thông tin đủ để trả lời, hãy nói rõ điều đó."""

                url = f"{self._gemini_base_url}/{self.model}:generateContent"
                params = {"key": self._gemini_api_key}
                
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": self.max_tokens,
                    }
                }
                
                print(f"[RAG] Calling Gemini API with model: {self.model}")
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, params=params, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    
                if "candidates" in data and len(data["candidates"]) > 0:
                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"[RAG] Gemini response received (length: {len(content) if content else 0})")
                    return content.strip() if content else ""
                else:
                    print(f"[RAG] Gemini API returned unexpected format: {data}")
                    raise Exception("Unexpected response format from Gemini")
                    
            except Exception as e:
                print(f"[RAG] Gemini API call failed: {e}")
                import traceback
                print(f"[RAG] Traceback: {traceback.format_exc()}")
                # Fall through to OpenAI or local
                pass
        
        # Try OpenAI if Gemini failed or provider is OpenAI
        if self.provider == "openai" and self._openai_client:
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "Bạn là trợ lý học tập chuyên nghiệp. Hãy trả lời câu hỏi một cách chi tiết và chính xác dựa trên ngữ cảnh được cung cấp. Trả lời bằng tiếng Việt. Nếu thông tin trong ngữ cảnh không đủ để trả lời, hãy nói rõ điều đó.",
                    },
                    {
                        "role": "user",
                        "content": f"Dưới đây là các đoạn văn liên quan từ tài liệu:\n\n{context_text}\n\nCâu hỏi: {question}\n\nHãy trả lời câu hỏi một cách đầy đủ, chi tiết và chính xác DỰA TRÊN các đoạn văn được cung cấp ở trên. Nếu câu hỏi đề cập đến một phần/chương cụ thể (ví dụ: 'phần 2', 'chương 1'), hãy tìm và sử dụng các đoạn văn liên quan đến phần/chương đó. Chỉ sử dụng thông tin có trong các đoạn văn. Nếu không có thông tin đủ để trả lời, hãy nói rõ điều đó.",
                    },
                ]

                print(f"[RAG] Calling OpenAI API with model: {self.model}")
                response = await asyncio.to_thread(
                    self._openai_client.chat.completions.create,
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.2,
                )
                content = response.choices[0].message.content
                print(f"[RAG] OpenAI response received (length: {len(content) if content else 0})")
                return content.strip() if content else ""
            except Exception as e:
                print(f"[RAG] OpenAI API call failed: {e}")
                # Fall through to local generation
                pass

        # Fallback: tổng hợp thủ công
        if context_text:
            first = context_parts[0] if context_parts else ""
            return (
                "(Trả lời tạm thời) Dựa trên tài liệu: "
                + first[:400]
                + "...\n--> Câu trả lời cần được xác thực thêm."
            )
        return "Chưa có đủ dữ liệu để trả lời câu hỏi này."


rag_service = RAGService()

