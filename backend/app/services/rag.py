import asyncio

from typing import List, Optional

import httpx

import numpy as np

from motor.motor_asyncio import AsyncIOMotorDatabase

import re



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
    
    def _extract_section_from_content(self, content: str, file_type: str) -> Optional[str]:
        """Extract section/heading from content if it looks like a heading.
        
        For DOCX/MD/TXT: Look for patterns like "7.1.2. Section Name" or short lines
        that could be headings.
        """
        if not content or file_type not in ["docx", "doc", "md", "txt"]:
            return None
        
        content = content.strip()
        
        # If content is very short (likely a heading), check if it matches heading patterns
        if len(content) > 150:  # Too long to be a heading
            return None
        
        # Pattern 1: Numbered sections like "7.1.2. Section Name" or "1.2.3 Section Name"
        import re
        numbered_section_pattern = r'^(\d+\.)+\s*\d+[\.\s]+(.+)$'
        match = re.match(numbered_section_pattern, content)
        if match:
            # Return the full content as it's likely a section heading
            return content
        
        # Pattern 2: Short lines that might be headings (less than 80 chars, ends with colon or no period)
        if len(content) < 80 and not content.endswith('.'):
            # Could be a heading, but be more careful
            # Check if it has structure like "SECTION NAME:" or "Section Name"
            if ':' in content or content.isupper() or (len(content.split()) <= 10 and not content.endswith('.')):
                return content
        
        # Pattern 3: Markdown-style headings (already handled by parser, but just in case)
        if content.startswith('#'):
            return content.lstrip('#').strip()
        
        return None
    
    def _is_numbered_section(self, text: str) -> bool:
        """Check if text looks like a numbered section heading (e.g., '7.2.2. Section Name')."""
        if not text:
            return False
        import re
        # Pattern for numbered sections: starts with digits and dots like "7.2.2." or "1.2.3 "
        numbered_pattern = r'^(\d+\.)+\s*\d+[\.\s]+'
        return bool(re.match(numbered_pattern, text.strip()))



    async def ask(

        self,

        db: AsyncIOMotorDatabase,

        user_id: str,

        question: str,

        document_id: Optional[str] = None,

        top_k: Optional[int] = None,

        conversation_id: Optional[str] = None,

    ) -> dict:

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



        # Search with larger initial top_k for more candidates

        for doc in documents:

            namespace = doc.faiss_namespace or f"user_{doc.user_id}_doc_{doc.id}"

            index = load_faiss_index(namespace)

            if index is None or index.ntotal == 0:

                continue

            if index.d != query_vector.shape[1]:

                continue

            try:

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



        # Boost chunks that contain keywords from the question

        question_lower = question.lower()

        question_keywords = [q.strip() for q in question_lower.replace("?", "").replace("!", "").split() if len(q.strip()) > 2]

        

        for item in results:

            item["original_similarity"] = item["similarity"]



        print(f"[RAG] Found {len(results)} candidate chunks, boosting by question keywords: {question_keywords[:5]}")



        # Cache content for boosting and later use

        for item in results:

            doc = item["document"]

            record = await db["embeddings"].find_one(

                {"document_id": doc.id, "vector_index": item["vector_id"]}

            )

            if not record:

                continue

            

            item["_record"] = record

            chunk_id = record.get("chunk_id")

            chunk_doc = None

            if chunk_id:

                try:

                    from bson import ObjectId

                    chunk_doc = await db["chunks"].find_one({"_id": ObjectId(chunk_id)})

                except Exception:

                    chunk_doc = await db["chunks"].find_one({"_id": chunk_id})
            
            # Debug: kiểm tra chunk_doc và metadata cho một vài chunks
            chunk_idx = record.get("chunk_index") if record else None
            if chunk_idx in [1, 3, 8, 10, 11] and doc.file_type in ["docx", "doc"]:
                if chunk_doc:
                    metadata = chunk_doc.get("metadata", {})
                    print(f"[RAG] Query chunk {chunk_idx}: chunk_id={chunk_id}, found={chunk_doc is not None}, metadata={metadata}")
                else:
                    print(f"[RAG] Query chunk {chunk_idx}: chunk_id={chunk_id}, chunk_doc NOT FOUND")

            content = (chunk_doc or {}).get("content") or record.get("content") or ""

            item["_content"] = content

            item["_chunk_doc"] = chunk_doc

            content_lower = content.lower()



            # Boost if content contains question keywords

            keyword_matches = sum(1 for kw in question_keywords if kw in content_lower)



            # Special boost for section numbers

            if any(kw in ["phần", "chương", "part"] for kw in question_keywords):

                question_numbers = re.findall(r'\d+', question_lower)

                all_subsection_patterns = re.findall(r'\b\d+\.\d+\b', question_lower)



                for num in question_numbers:

                    if f"phần {num}" in content_lower or f"chương {num}" in content_lower or f"part {num}" in content_lower:

                        keyword_matches += 3

                        section_pattern = rf"{num}\.\d+"

                        if re.search(section_pattern, content_lower):

                            keyword_matches += 5

                        break



                for subsec in all_subsection_patterns:

                    if subsec in content_lower:

                        keyword_matches += 8

                        print(f"[RAG] Found exact subsection match: {subsec} in chunk {record.get('chunk_index', '?')}")



            if keyword_matches > 0:

                boost = min(0.3, keyword_matches * 0.08)

                item["similarity"] = min(1.0, item["similarity"] + boost)

                item["keyword_matches"] = keyword_matches

                print(f"[RAG] Boosted chunk {record.get('chunk_index', '?')} by {boost:.3f} (matches: {keyword_matches})")



        # Sort by boosted similarity

        sorted_results = sorted(results, key=lambda r: r["similarity"], reverse=True)



        # Select chunks for context - prioritize section matches

        selected_results = []

        priority_chunks = []

        regular_chunks = []



        for item in sorted_results:

            content_lower = (item.get("_content", "") or "").lower()

            has_section_match = False



            if any(kw in ["phần", "chương", "part"] for kw in question_keywords):

                question_numbers = re.findall(r'\d+', question_lower)

                for num in question_numbers:

                    if (f"phần {num}" in content_lower or f"chương {num}" in content_lower or

                         re.search(rf"{num}\.\d+", content_lower)):

                        has_section_match = True

                        break



            if has_section_match:

                priority_chunks.append(item)

            else:

                regular_chunks.append(item)



        all_chunks_ordered = priority_chunks + regular_chunks



        current_context_length = 0

        chunk_metadata_for_context = []  # Store metadata to pass to LLM

        

        for item in all_chunks_ordered:

            content = item.get("_content", "")

            content_length = len(content) if content else 0



            if current_context_length + content_length + 500 > self.max_context_length:

                break



            selected_results.append(item)

            

            # Store chunk metadata

            record = item.get("_record")

            chunk_doc = item.get("_chunk_doc")

            
            # Lấy metadata từ chunk_doc (chunks collection)
            chunk_metadata = {}
            if chunk_doc:
                chunk_metadata = (chunk_doc.get("metadata") or {})
                # Debug: log metadata cho một vài chunks để kiểm tra
                chunk_idx = record.get("chunk_index") if record else None
                if chunk_idx in [1, 3, 8, 10, 11] and item["document"].file_type in ["docx", "doc"]:
                    print(f"[RAG] Building context - chunk {chunk_idx}: chunk_doc metadata = {chunk_metadata}")
            else:
                # Nếu không có chunk_doc, thử từ record
                if record:
                    chunk_metadata = (record.get("metadata") or {})
            
            # Đảm bảo chunk_metadata là dict
            if not isinstance(chunk_metadata, dict):
                chunk_metadata = {}

            # Lấy heading hoặc section title cho DOCX

            heading = chunk_metadata.get("heading") or chunk_metadata.get("title") or chunk_metadata.get("section_title")
            section = chunk_metadata.get("section")
            
            # Nếu không có section/heading trong metadata, thử extract từ content
            if not section and not heading and content and item["document"].file_type in ["docx", "doc", "md", "txt"]:
                extracted = self._extract_section_from_content(content, item["document"].file_type)
                if extracted:
                    section = extracted
                    # Nếu content ngắn và có vẻ là heading, thì đó là heading
                    if len(content.strip()) < 100:
                        heading = extracted

            chunk_idx = record.get("chunk_index") if record else None
            
            chunk_metadata_for_context.append({

                "chunk_index": chunk_idx,

                "document_id": record.get("document_id") if record else None,  # THÊM document_id

                "page_number": chunk_metadata.get("page_number"),

                "section": section,

                "heading": heading,  # THÊM heading

                "document_type": item["document"].file_type,  # THÊM loại file

                "document_filename": item["document"].filename,  # THÊM tên file

                "content": content

            })
            
            # Debug: log section/heading cho một vài chunks
            if chunk_idx in [1, 3, 8, 10, 11] and item["document"].file_type in ["docx", "doc"]:
                print(f"[RAG] Context metadata for chunk {chunk_idx}: section={section}, heading={heading}, extracted_from_content={section != chunk_metadata.get('section')}")

            

            current_context_length += content_length



        print(f"[RAG] Selected {len(selected_results)} chunks (context length: {current_context_length}/{self.max_context_length} chars)")

        print(f"[RAG] Priority chunks: {len(priority_chunks)}, Regular chunks: {len(regular_chunks)}")



        # Generate answer with chunk tracking

        answer, chunks_actually_used = await self._generate_answer_with_tracking(

            question, chunk_metadata_for_context

        )



        print(f"[RAG] LLM used {len(chunks_actually_used)} chunks in answer")

        print(f"[RAG] Chunks used: {chunks_actually_used}")



        # Build references from chunks actually used in answer
        # If LLM didn't return chunk indices, use all selected chunks (sorted by similarity)
        
        # Create a metadata map from chunk_metadata_for_context for quick lookup
        # Key: (chunk_index, document_id) -> metadata dict
        metadata_map = {}
        for chunk_meta in chunk_metadata_for_context:
            key = (chunk_meta.get("chunk_index"), chunk_meta.get("document_id"))
            metadata_map[key] = chunk_meta
        
        # Second pass: Fill in missing sections by looking backward at previous chunks
        # This ensures all chunks have section information if available from earlier chunks
        # Sort chunks by chunk_index within each document to ensure proper order
        chunks_by_doc = {}
        for chunk_meta in chunk_metadata_for_context:
            doc_id = chunk_meta.get("document_id")
            if doc_id not in chunks_by_doc:
                chunks_by_doc[doc_id] = []
            chunks_by_doc[doc_id].append(chunk_meta)
        
        # For each document, sort chunks by chunk_index and fill in missing sections
        for doc_id, doc_chunks in chunks_by_doc.items():
            # Sort by chunk_index
            doc_chunks.sort(key=lambda x: x.get("chunk_index") or 0)
            
            # Now iterate through chunks in order and fill in missing sections
            for i, chunk_meta in enumerate(doc_chunks):
                chunk_idx = chunk_meta.get("chunk_index")
                current_section = chunk_meta.get("section")
                current_heading = chunk_meta.get("heading")
                
                # If this chunk doesn't have a section/heading, try to find one from previous chunks
                if not current_section and not current_heading and chunk_idx is not None and chunk_idx > 0:
                    # Look backward through previous chunks in the same document
                    # Collect all potential sections and choose the best one
                    candidate_sections = []
                    
                    # Look backward through chunks we've already processed
                    for j in range(i - 1, -1, -1):
                        prev_chunk = doc_chunks[j]
                        prev_section = prev_chunk.get("section")
                        prev_heading = prev_chunk.get("heading")
                        
                        # Collect all sections/headings we find
                        if prev_heading:
                            candidate_sections.append({
                                "text": prev_heading,
                                "is_heading": True,
                                "is_numbered": self._is_numbered_section(prev_heading),
                                "length": len(prev_heading),
                                "chunk_idx": prev_chunk.get("chunk_index")
                            })
                        if prev_section and prev_section != prev_heading:
                            candidate_sections.append({
                                "text": prev_section,
                                "is_heading": False,
                                "is_numbered": self._is_numbered_section(prev_section),
                                "length": len(prev_section),
                                "chunk_idx": prev_chunk.get("chunk_index")
                            })
                    
                    # Choose the best section: prefer numbered sections, then short headings
                    found_section = None
                    found_heading = None
                    
                    if candidate_sections:
                        # Sort by priority:
                        # 1. Numbered sections (like "7.2.2. ...")
                        # 2. Short headings (< 60 chars)
                        # 3. Other sections
                        def section_priority(candidate):
                            priority = 0
                            if candidate["is_numbered"]:
                                priority += 1000  # Highest priority
                            if candidate["is_heading"]:
                                priority += 100
                            if candidate["length"] < 60:
                                priority += 50
                            # Prefer sections from chunks closer to current chunk
                            priority += (100 - candidate["chunk_idx"] or 0) / 100
                            return priority
                        
                        candidate_sections.sort(key=section_priority, reverse=True)
                        best_candidate = candidate_sections[0]
                        found_section = best_candidate["text"]
                        found_heading = best_candidate["text"] if best_candidate["is_heading"] else None
                    
                    # If we found a section from a previous chunk, update this chunk's metadata
                    if found_section or found_heading:
                        chunk_meta["section"] = found_section
                        chunk_meta["heading"] = found_heading
                        # Also update the metadata_map entry
                        metadata_key = (chunk_idx, doc_id)
                        if metadata_key in metadata_map:
                            metadata_map[metadata_key]["section"] = found_section
                            metadata_map[metadata_key]["heading"] = found_heading
                            print(f"[RAG] Filled section for chunk {chunk_idx} from previous chunk: {found_section or found_heading}")
        
        # Count chunks per document BEFORE filtering (to determine which documents are most relevant)
        chunks_by_document = {}
        if chunks_actually_used:
            for chunk_info in chunks_actually_used:
                if isinstance(chunk_info, dict):
                    doc_id = chunk_info.get("document_id")
                else:
                    # Find document_id from selected_results
                    doc_id = None
                    for item in selected_results:
                        record = item.get("_record")
                        if record and record.get("chunk_index") == chunk_info:
                            doc_id = record.get("document_id")
                            break
                if doc_id:
                    chunks_by_document[doc_id] = chunks_by_document.get(doc_id, 0) + 1
        
        final_references: List[HistoryReference] = []
        
        # If chunks_actually_used is empty, use top selected_results chunks (chunks sent to LLM)
        # This ensures we always have references when an answer is generated
        if not chunks_actually_used and selected_results:
            # Sort by similarity score (descending) and take top chunks
            # selected_results is already sorted (priority_chunks + regular_chunks), but ensure by similarity
            sorted_for_refs = sorted(selected_results, key=lambda r: r.get("similarity", 0), reverse=True)
            
            # Count chunks per document to determine relevance
            temp_chunks_by_doc = {}
            for item in sorted_for_refs[:15]:  # Check top 15
                record = item.get("_record")
                if record:
                    doc_id = record.get("document_id")
                    if doc_id:
                        temp_chunks_by_doc[doc_id] = temp_chunks_by_doc.get(doc_id, 0) + 1
            chunks_by_document = temp_chunks_by_doc
            
            # If document_id is specified, only use chunks from that document
            if document_id:
                top_chunks = [item for item in sorted_for_refs if item.get("_record", {}).get("document_id") == document_id][:15]
            else:
                # Filter: only keep chunks from documents with most chunks (if multiple documents)
                if len(chunks_by_document) > 1:
                    max_chunks = max(chunks_by_document.values())
                    # Only keep documents with at least 2 chunks, or if all have 1 chunk, keep all
                    if max_chunks >= 2:
                        relevant_docs = {doc_id for doc_id, count in chunks_by_document.items() if count >= 2}
                        if relevant_docs:
                            top_chunks = [item for item in sorted_for_refs 
                                        if item.get("_record", {}).get("document_id") in relevant_docs][:15]
                            print(f"[RAG] Filtered to documents with 2+ chunks: {relevant_docs}")
                        else:
                            top_chunks = sorted_for_refs[:15]
                    else:
                        top_chunks = sorted_for_refs[:15]
                else:
                    top_chunks = sorted_for_refs[:15]
            
            print(f"[RAG] No chunks returned by LLM, using top {len(top_chunks)} chunks (out of {len(selected_results)}) as references")
            # Convert selected_results to chunk_info format
            chunks_actually_used = []
            for item in top_chunks:
                record = item.get("_record")
                if record:
                    chunks_actually_used.append({
                        "chunk_index": record.get("chunk_index"),
                        "document_id": record.get("document_id")
                    })
            
            # Update chunks_by_document based on selected chunks
            chunks_by_document = {}
            for chunk_info in chunks_actually_used:
                doc_id = chunk_info.get("document_id")
                if doc_id:
                    chunks_by_document[doc_id] = chunks_by_document.get(doc_id, 0) + 1

        for chunk_info in chunks_actually_used:

            # chunk_info có thể là số (chunk_index) hoặc dict {"chunk_index": X, "document_id": Y}

            if isinstance(chunk_info, dict):

                target_chunk_index = chunk_info.get("chunk_index")

                target_document_id = chunk_info.get("document_id")

            else:

                target_chunk_index = chunk_info

                target_document_id = None

            

            # Find the corresponding item in selected_results

            for item in selected_results:

                record = item.get("_record")

                doc = item["document"]

                

                if not record:

                    continue

                

                # QUAN TRỌNG: Check cả chunk_index VÀ document_id để tránh nhầm lẫn

                chunk_index_match = record.get("chunk_index") == target_chunk_index

                

                # Nếu có document_id trong chunk_info, phải match cả document_id

                if target_document_id:

                    document_id_match = record.get("document_id") == target_document_id

                    if not (chunk_index_match and document_id_match):

                        continue

                else:

                    # Nếu không có document_id, chỉ cần match chunk_index

                    if not chunk_index_match:

                        continue

                

                chunk_doc = item.get("_chunk_doc")

                content = item.get("_content")

                record = item.get("_record")

                

                # Lấy metadata - ưu tiên từ metadata_map (đã có sẵn từ chunk_metadata_for_context)
                # Đây là nguồn đáng tin cậy nhất vì đã được lấy trực tiếp từ database khi build context
                metadata_key = (target_chunk_index, target_document_id or record.get("document_id") if record else None)
                cached_metadata = metadata_map.get(metadata_key)
                
                if cached_metadata:
                    # Sử dụng metadata từ cache (đã có section, heading, page_number)
                    # Metadata map đã được fill với sections từ previous chunks trong second pass
                    page_number = cached_metadata.get("page_number")
                    section = cached_metadata.get("section")
                    heading = cached_metadata.get("heading")
                    display_section = section or heading
                    
                    # If the section is not a numbered section, we might find a better one from database
                    # So we'll still try to find a numbered section later if display_section is not numbered
                else:
                    # Fallback: lấy từ database nếu không có trong cache
                    chunk_metadata = {}
                    
                    # Ưu tiên metadata từ chunk_doc (chunks collection)
                    if chunk_doc:
                        chunk_metadata = (chunk_doc.get("metadata") or {})
                    
                    # Nếu không có, thử từ record (embeddings collection)
                    if not chunk_metadata and record:
                        chunk_metadata = (record.get("metadata") or {})
                    
                    # Đảm bảo chunk_metadata là dict
                    if not isinstance(chunk_metadata, dict):
                        chunk_metadata = {}
                    
                    page_number = chunk_metadata.get("page_number")
                    section = chunk_metadata.get("section")
                    heading = chunk_metadata.get("heading") or chunk_metadata.get("title") or chunk_metadata.get("section_title")
                    display_section = section or heading
                    
                    # Debug: log nếu không tìm thấy trong cache
                    if target_chunk_index in [1, 3, 8, 10, 11, 42, 31, 48, 66]:
                        print(f"[RAG] Warning: chunk {target_chunk_index} not found in metadata_map, using database. metadata={chunk_metadata}")
                
                # If still no section, try to extract from content (shouldn't happen often after second pass)
                if not display_section and content and doc.file_type:
                    extracted_section = self._extract_section_from_content(content, doc.file_type)
                    if extracted_section:
                        display_section = extracted_section
                        print(f"[RAG] Extracted section from content for chunk {target_chunk_index}: {display_section}")
                
                # If still no section, or if section is not numbered (might have better numbered section),
                # try to find from previous chunks in database
                # This handles cases where the chunk wasn't in chunk_metadata_for_context
                # or where we want to find a better numbered section
                has_section = bool(display_section)
                is_numbered = self._is_numbered_section(display_section) if display_section else False
                
                # Query database if: no section, or has section but not numbered (might find better numbered section)
                if target_chunk_index is not None and target_chunk_index > 0 and (not has_section or not is_numbered):
                    doc_id_for_lookup = target_document_id or record.get("document_id") if record else None
                    if doc_id_for_lookup:
                        try:
                            # Query database for previous chunks in the same document
                            # Look for chunks with chunk_index < target_chunk_index, ordered by chunk_index desc
                            # Limit to 10 chunks to avoid too many queries
                            previous_chunks = await db["chunks"].find({
                                "document_id": doc_id_for_lookup,
                                "chunk_index": {"$lt": target_chunk_index}
                            }).sort("chunk_index", -1).limit(10).to_list(length=10)
                            
                            # Collect candidate sections from previous chunks
                            candidate_sections = []
                            for prev_chunk in previous_chunks:
                                prev_metadata = prev_chunk.get("metadata") or {}
                                prev_section = prev_metadata.get("section")
                                prev_heading = prev_metadata.get("heading")
                                
                                # Also try to extract from content if it looks like a heading
                                prev_content = prev_chunk.get("content", "")
                                if not prev_section and not prev_heading and prev_content:
                                    extracted = self._extract_section_from_content(prev_content, doc.file_type if doc else "docx")
                                    if extracted:
                                        prev_section = extracted
                                
                                if prev_heading:
                                    candidate_sections.append({
                                    "text": prev_heading,
                                    "is_heading": True,
                                    "is_numbered": self._is_numbered_section(prev_heading),
                                    "length": len(prev_heading),
                                    "chunk_idx": prev_chunk.get("chunk_index")
                                })
                                if prev_section and prev_section != prev_heading:
                                    candidate_sections.append({
                                        "text": prev_section,
                                        "is_heading": False,
                                        "is_numbered": self._is_numbered_section(prev_section),
                                        "length": len(prev_section),
                                        "chunk_idx": prev_chunk.get("chunk_index")
                                    })
                            
                            # Choose the best section: prefer numbered sections
                            if candidate_sections:
                                def section_priority(candidate):
                                    priority = 0
                                    if candidate["is_numbered"]:
                                        priority += 1000  # Highest priority
                                    if candidate["is_heading"]:
                                        priority += 100
                                    if candidate["length"] < 60:
                                        priority += 50
                                    # Prefer sections from chunks closer to current chunk
                                    priority += (100 - candidate["chunk_idx"] or 0) / 100
                                    return priority
                                
                                candidate_sections.sort(key=section_priority, reverse=True)
                                best_candidate = candidate_sections[0]
                                
                                # Only use database section if:
                                # 1. We had no section, OR
                                # 2. Database has a numbered section (better than non-numbered)
                                if not has_section or (best_candidate["is_numbered"] and not is_numbered):
                                    display_section = best_candidate["text"]
                                    print(f"[RAG] Found section from database for chunk {target_chunk_index}: {display_section} (from chunk {best_candidate['chunk_idx']})")
                        except Exception as e:
                            print(f"[RAG] Error querying database for previous chunks: {e}")
                
                if not display_section:
                    print(f"[RAG] No section found for chunk {target_chunk_index} after all attempts")

                

                preview = content[:160] if content else None

                

                final_references.append(

                    HistoryReference(

                        document_id=doc.id,

                        document_filename=doc.filename,

                        document_file_type=doc.file_type,

                        chunk_id=str(chunk_doc.get("_id")) if chunk_doc else None,

                        chunk_index=target_chunk_index,

                        page_number=page_number,

                        section=display_section,  # Sử dụng section hoặc heading

                        score=item["similarity"],

                        content_preview=preview,

                    )

                )

                break



        # Remove duplicates - khác biệt giữa PDF và DOCX

        seen_keys = set()

        deduplicated_refs = []

        

        for ref in final_references:

            # Với PDF: deduplicate theo page

            if ref.document_file_type and ref.document_file_type.lower() == "pdf" and ref.page_number:

                page_key = f"{ref.document_id}_page_{ref.page_number}"

                if page_key in seen_keys:

                    continue

                seen_keys.add(page_key)

            

            # Với DOCX: deduplicate theo section hoặc chunk

            elif ref.document_file_type and ref.document_file_type.lower() in ["docx", "doc"]:

                if ref.section:

                    section_key = f"{ref.document_id}_section_{ref.section}"

                    if section_key in seen_keys:

                        continue

                    seen_keys.add(section_key)

                else:

                    # Nếu không có section, dùng chunk_index

                    chunk_key = f"{ref.document_id}_chunk_{ref.chunk_index}"

                    if chunk_key in seen_keys:

                        continue

                    seen_keys.add(chunk_key)

            else:

                # Fallback: deduplicate theo chunk_index

                chunk_key = f"{ref.document_id}_chunk_{ref.chunk_index}"

                if chunk_key in seen_keys:

                    continue

                seen_keys.add(chunk_key)

            

            deduplicated_refs.append(ref)



        # Filter references based on document_id and relevance
        # Use chunks_by_document to determine which documents are most relevant
        filtered_refs = deduplicated_refs
        
        if document_id:
            # Only keep references from the specified document
            filtered_refs = [ref for ref in deduplicated_refs if ref.document_id == document_id]
            print(f"[RAG] Filtered references to document {document_id}: {len(filtered_refs)} references")
        else:
            # Use chunks_by_document to filter - allow multiple documents if they're all relevant
            # This ensures we show references from all relevant documents, not just one
            if len(chunks_by_document) > 1:
                # Find document with most chunks
                max_chunks = max(chunks_by_document.values())
                sorted_counts = sorted(chunks_by_document.values(), reverse=True)
                second_max = sorted_counts[1] if len(sorted_counts) > 1 else 0
                
                # If one document has significantly more chunks (3+ more), only keep that document
                # Otherwise, keep all documents with at least 2 chunks
                if max_chunks >= 3 and max_chunks - second_max >= 3:
                    # One document has significantly more chunks (3+ more), only keep that
                    docs_with_max_chunks = {doc_id for doc_id, count in chunks_by_document.items() if count == max_chunks}
                    filtered_refs = [ref for ref in deduplicated_refs if ref.document_id in docs_with_max_chunks]
                    removed_docs = set(chunks_by_document.keys()) - docs_with_max_chunks
                    if removed_docs:
                        print(f"[RAG] Filtered to document with most chunks ({max_chunks}): {docs_with_max_chunks}, removed: {removed_docs}")
                else:
                    # Documents have similar chunk counts, keep all documents with at least 2 chunks
                    # This allows multiple documents to be referenced if they're all relevant
                    if max_chunks >= 2:
                        relevant_docs = {doc_id for doc_id, count in chunks_by_document.items() if count >= 2}
                        if relevant_docs and len(relevant_docs) < len(chunks_by_document):
                            filtered_refs = [ref for ref in deduplicated_refs if ref.document_id in relevant_docs]
                            removed_docs = set(chunks_by_document.keys()) - relevant_docs
                            if removed_docs:
                                print(f"[RAG] Filtered out documents with only 1 chunk: {removed_docs}")
                                print(f"[RAG] Keeping references from {len(relevant_docs)} documents: {relevant_docs}")
                    else:
                        # All documents have only 1 chunk, keep all
                        print(f"[RAG] All documents have 1 chunk, keeping all references")
            elif len(chunks_by_document) == 1:
                # Only one document, keep all references
                print(f"[RAG] Single document, keeping all references")
        
        # Smart filtering: If there are multiple sections, prioritize the section(s) with most chunks
        # Count chunks per section from chunks_actually_used (not from deduplicated_refs)
        if len(filtered_refs) > 2 and chunks_actually_used:
            # Count chunks per section from chunks_actually_used
            section_chunk_counts = {}
            for chunk_info in chunks_actually_used:
                if isinstance(chunk_info, dict):
                    chunk_idx = chunk_info.get("chunk_index")
                    doc_id = chunk_info.get("document_id")
                else:
                    chunk_idx = chunk_info
                    doc_id = None
                
                # Find section from metadata_map
                metadata_key = (chunk_idx, doc_id)
                chunk_meta = metadata_map.get(metadata_key)
                if chunk_meta:
                    # Determine section key
                    file_type = chunk_meta.get("document_type", "").lower()
                    if file_type in ["docx", "doc"]:
                        section = chunk_meta.get("section") or chunk_meta.get("heading")
                        if section:
                            section_key = f"{doc_id}_{section}"
                        else:
                            section_key = f"{doc_id}_no_section_{chunk_idx}"
                    elif file_type == "pdf":
                        page = chunk_meta.get("page_number")
                        if page:
                            section_key = f"{doc_id}_page_{page}"
                        else:
                            section_key = f"{doc_id}_no_page_{chunk_idx}"
                    else:
                        section_key = f"{doc_id}_other_{chunk_idx}"
                    
                    section_chunk_counts[section_key] = section_chunk_counts.get(section_key, 0) + 1
            
            # Group filtered_refs by section
            section_refs = {}
            for ref in filtered_refs:
                if ref.document_file_type and ref.document_file_type.lower() in ["docx", "doc"]:
                    section_key = f"{ref.document_id}_{ref.section}" if ref.section else f"{ref.document_id}_no_section_{ref.chunk_index}"
                elif ref.document_file_type and ref.document_file_type.lower() == "pdf":
                    section_key = f"{ref.document_id}_page_{ref.page_number}" if ref.page_number else f"{ref.document_id}_no_page_{ref.chunk_index}"
                else:
                    section_key = f"{ref.document_id}_other_{ref.chunk_index}"
                
                if section_key not in section_refs:
                    section_refs[section_key] = []
                section_refs[section_key].append(ref)
            
            # Sort sections by chunk count (from chunks_actually_used), not by reference count
            sorted_sections = sorted(
                section_refs.items(), 
                key=lambda x: section_chunk_counts.get(x[0], 0), 
                reverse=True
            )
            
            # Keep references from top sections based on chunk count
            if sorted_sections:
                top_section_key = sorted_sections[0][0]
                top_chunk_count = section_chunk_counts.get(top_section_key, 0)
                
                if top_chunk_count >= 3:
                    # Only keep top section if it has 3+ chunks
                    filtered_refs = section_refs[top_section_key]
                    print(f"[RAG] Filtered to top section only: {top_section_key} ({top_chunk_count} chunks, {len(filtered_refs)} references)")
                elif len(sorted_sections) > 1:
                    # Keep top 2 sections
                    second_section_key = sorted_sections[1][0]
                    second_chunk_count = section_chunk_counts.get(second_section_key, 0)
                    filtered_refs = section_refs[top_section_key] + section_refs[second_section_key]
                    print(f"[RAG] Filtered to top 2 sections: {top_section_key} ({top_chunk_count} chunks), {second_section_key} ({second_chunk_count} chunks)")
                else:
                    # Only one section, keep all
                    filtered_refs = sorted_sections[0][1]

        final_references = filtered_refs[:5]  # Limit to 5 references



        print(f"[RAG] Final references: {len(final_references)} chunks")

        print(f"[RAG] Reference details:")

        for ref in final_references:

            print(f"  - File: {ref.document_filename}, Page: {ref.page_number}, Section: {ref.section}, Chunk: {ref.chunk_index}")



        # Ensure conversation_id is set - use provided conversation_id or create new one
        # If conversation_id is provided, use it (for continuing existing conversation)
        # If not provided, we'll set it to history_id after creating the record
        final_conversation_id = conversation_id

        # Create history with conversation_id (may be None for new conversation)
        history_record = await create_history(
            db, user_id, question, answer, final_references, document_id, final_conversation_id
        )

        # If no conversation_id was provided, use the history_id as conversation_id
        # This ensures all Q&As in the same conversation share the same conversation_id
        if not final_conversation_id:
            final_conversation_id = history_record.id
            # Update the history record to set conversation_id = history_id
            # This ensures consistency when loading conversations
            try:
                from bson import ObjectId
                update_result = await db["histories"].update_one(
                    {"_id": ObjectId(history_record.id)},
                    {"$set": {"conversation_id": history_record.id}}
                )
                if update_result.modified_count > 0:
                    print(f"[RAG] Set conversation_id = history_id for new conversation: {history_record.id}")
                # Also update the history_record object for return value
                history_record.conversation_id = history_record.id
            except Exception as e:
                print(f"[RAG] Warning: Failed to update conversation_id for history {history_record.id}: {e}")
        else:
            # Conversation_id was provided, ensure it's set correctly in the record
            # (It should already be set, but double-check for consistency)
            try:
                from bson import ObjectId
                # Verify the record has the correct conversation_id
                existing_record = await db["histories"].find_one({"_id": ObjectId(history_record.id)})
                if existing_record and existing_record.get("conversation_id") != final_conversation_id:
                    await db["histories"].update_one(
                        {"_id": ObjectId(history_record.id)},
                        {"$set": {"conversation_id": final_conversation_id}}
                    )
                    print(f"[RAG] Updated conversation_id to {final_conversation_id} for history {history_record.id}")
            except Exception as e:
                print(f"[RAG] Warning: Failed to verify conversation_id for history {history_record.id}: {e}")



        return {

            "answer": answer,

            "references": final_references,

            "documents": list(set([ref.document_id for ref in final_references if ref.document_id])),

            "conversation_id": final_conversation_id,

            "history_id": history_record.id,

        }



    async def _generate_answer_with_tracking(

        self, question: str, chunk_metadata_list: List[dict]

    ) -> tuple[str, List[dict]]:

        """

        Generate answer and track which chunks were actually used.

        Returns: (answer, list of chunk info dicts with chunk_index and document_id)

        """

        # Build context with explicit chunk markers

        context_parts = []

        for chunk_meta in chunk_metadata_list:

            chunk_idx = chunk_meta["chunk_index"]

            document_id = chunk_meta.get("document_id")

            content = chunk_meta["content"]

            page = chunk_meta.get("page_number")

            section = chunk_meta.get("section")

            heading = chunk_meta.get("heading")

            doc_type = chunk_meta.get("document_type", "")

            doc_filename = chunk_meta.get("document_filename", "")

            

            # Add metadata in marker - khác nhau cho PDF và DOCX

            meta_info = f"Chunk {chunk_idx}"

            

            # Thêm tên file để phân biệt

            if doc_filename:

                meta_info += f" [{doc_filename}]"

            

            if doc_type and doc_type.lower() in ["docx", "doc"]:

                # DOCX: Hiển thị section/heading thay vì trang

                if heading:

                    meta_info += f", {heading}"

                elif section:

                    meta_info += f", {section}"

            else:

                # PDF: Hiển thị trang

                if page:

                    meta_info += f", Trang {page}"

                if section:

                    meta_info += f", {section}"

            

            context_parts.append(f"[{meta_info}]\n{content}")

        

        context_text = "\n\n".join(context_parts)



        # Enhanced prompt asking LLM to cite chunks

        prompt = f"""Bạn là trợ lý học tập chuyên nghiệp. Hãy trả lời câu hỏi một cách chi tiết và chính xác dựa trên ngữ cảnh được cung cấp.



Dưới đây là các đoạn văn từ tài liệu (mỗi đoạn có đánh dấu [Chunk X [tên_file], ...]):



{context_text}



Câu hỏi: {question}



QUAN TRỌNG: 

1. Hãy trả lời câu hỏi DỰA TRÊN các đoạn văn được cung cấp ở trên

2. Sau khi trả lời, hãy liệt kê các chunk numbers mà bạn đã sử dụng để trả lời ở cuối câu trả lời theo format:

   [CHUNKS_USED: 1, 5, 7]

   (Chỉ liệt kê số thứ tự chunk, cách nhau bởi dấu phẩy)



Hãy trả lời:"""



        # Try Gemini first

        if self.provider == "gemini" and self._gemini_api_key:

            try:

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

                

                print(f"[RAG] Calling Gemini API with chunk tracking")

                async with httpx.AsyncClient(timeout=60.0) as client:

                    response = await client.post(url, params=params, json=payload)

                    response.raise_for_status()

                    data = response.json()

                    

                    if "candidates" in data and len(data["candidates"]) > 0:

                        full_response = data["candidates"][0]["content"]["parts"][0]["text"]

                        answer, chunks_used = self._parse_answer_and_chunks(full_response, chunk_metadata_list)

                        print(f"[RAG] Gemini response received, chunks used: {chunks_used}")

                        return answer, chunks_used

                    else:

                        print(f"[RAG] Gemini API returned unexpected format: {data}")

                        raise Exception("Unexpected response format from Gemini")

                

            except Exception as e:

                print(f"[RAG] Gemini API call failed: {e}")

                import traceback

                print(f"[RAG] Traceback: {traceback.format_exc()}")



        # Try OpenAI

        if self.provider == "openai" and self._openai_client:

            try:

                messages = [

                    {

                        "role": "system",

                        "content": "Bạn là trợ lý học tập chuyên nghiệp. Hãy trả lời câu hỏi dựa trên ngữ cảnh và LUÔN liệt kê các chunk numbers đã sử dụng ở cuối theo format [CHUNKS_USED: 1, 2, 3]",

                    },

                    {

                        "role": "user",

                        "content": prompt,

                    },

                ]

                

                print(f"[RAG] Calling OpenAI API with chunk tracking")

                response = await asyncio.to_thread(

                    self._openai_client.chat.completions.create,

                    model=self.model,

                    messages=messages,

                    max_tokens=self.max_tokens,

                    temperature=0.2,

                )

                full_response = response.choices[0].message.content

                answer, chunks_used = self._parse_answer_and_chunks(full_response, chunk_metadata_list)

                print(f"[RAG] OpenAI response received, chunks used: {chunks_used}")

                return answer, chunks_used

            except Exception as e:

                print(f"[RAG] OpenAI API call failed: {e}")



        # Fallback: manual summary

        if context_text and chunk_metadata_list:

            first_chunk = chunk_metadata_list[0]

            chunks_used = [{

                "chunk_index": first_chunk.get("chunk_index"),

                "document_id": first_chunk.get("document_id")

            }]

            first_content = first_chunk.get("content", "")

            return (

                "(Trả lời tạm thời) Dựa trên tài liệu: "

                + first_content[:400]

                + "...\n--> Câu trả lời cần được xác thực thêm.",

                chunks_used

            )

        return "Chưa có đủ dữ liệu để trả lời câu hỏi này.", []



    def _parse_answer_and_chunks(self, full_response: str, chunk_metadata_list: List[dict]) -> tuple[str, List[dict]]:

        """

        Parse LLM response to extract answer and chunk indices used.

        Expected format: 

        Answer text here...

        [CHUNKS_USED: 1, 5, 7]

        

        Returns: (answer, list of chunk info dicts with chunk_index and document_id)

        """

        # Look for [CHUNKS_USED: ...] pattern

        match = re.search(r'\[CHUNKS_USED:\s*([\d,\s]+)\]', full_response, re.IGNORECASE)

        

        if match:

            # Extract chunk numbers

            chunk_str = match.group(1)

            chunk_indices = [int(x.strip()) for x in chunk_str.split(',') if x.strip().isdigit()]

            

            # Map chunk indices to chunk info with document_id

            chunks_used = []

            for chunk_idx in chunk_indices:

                # Find corresponding metadata

                for chunk_meta in chunk_metadata_list:

                    if chunk_meta.get("chunk_index") == chunk_idx:

                        chunks_used.append({

                            "chunk_index": chunk_idx,

                            "document_id": chunk_meta.get("document_id")

                        })

                        break

                else:

                    # Nếu không tìm thấy metadata, vẫn thêm chunk_index

                    chunks_used.append({"chunk_index": chunk_idx, "document_id": None})

            

            # Remove the [CHUNKS_USED: ...] part from answer

            answer = re.sub(r'\[CHUNKS_USED:.*?\]', '', full_response, flags=re.IGNORECASE).strip()

            

            return answer, chunks_used

        else:

            # Fallback: try to infer from content

            # Look for "Chunk X" mentions in the response

            chunks_mentioned = re.findall(r'[Cc]hunk\s+(\d+)', full_response)

            chunk_indices = list(set(int(x) for x in chunks_mentioned))

            

            # Map to chunk info

            chunks_used = []

            for chunk_idx in chunk_indices:

                for chunk_meta in chunk_metadata_list:

                    if chunk_meta.get("chunk_index") == chunk_idx:

                        chunks_used.append({

                            "chunk_index": chunk_idx,

                            "document_id": chunk_meta.get("document_id")

                        })

                        break

                else:

                    chunks_used.append({"chunk_index": chunk_idx, "document_id": None})

            

            return full_response.strip(), chunks_used





rag_service = RAGService()
