import asyncio
import json
import re
from typing import List, Optional
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..core.config import settings
from ..models.document import get_document_by_id
from ..models.quiz import QuizQuestion


class QuizGeneratorService:
    """Generate quiz questions from documents using LLM"""
    
    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.model = settings.llm_model
        self.max_tokens = 2000  # Enough for generating quiz questions
        
        self._openai_client = None
        self._gemini_api_key = None
        self._gemini_base_url = "https://generativelanguage.googleapis.com/v1/models"
        
        # Initialize OpenAI if needed
        if self.provider == "openai" and settings.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.openai_api_key)
                print(f"[QuizGen] OpenAI client initialized")
            except Exception as e:
                print(f"[QuizGen] Failed to initialize OpenAI: {e}")
                self._openai_client = None
        
        # Initialize Gemini if needed
        if self.provider == "gemini":
            self._gemini_api_key = settings.gemini_api_key
            if self._gemini_api_key:
                print(f"[QuizGen] Gemini API initialized")
            else:
                print("[QuizGen] Gemini API key not found")
                self.provider = "local"
        
        if self.provider == "openai" and self._openai_client is None:
            print("[QuizGen] Falling back to Gemini or error")
            self.provider = "gemini"
    
    async def generate_quiz(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        document_id: str,
        num_questions: int = 5,
        difficulty: str = "medium",
        question_types: List[str] = ["multiple_choice", "true_false"],
    ) -> List[QuizQuestion]:
        """Generate quiz questions from a document using LLM"""
        
        print(f"[QuizGen] Generating {num_questions} questions for document {document_id}")
        print(f"[QuizGen] Difficulty: {difficulty}, Types: {question_types}")
        
        # Get document
        doc = await get_document_by_id(db, document_id)
        if not doc or doc.user_id != user_id:
            raise ValueError("Document not found or not accessible")
        
        # Get chunks from the document - OPTIMIZED: only get first 20 chunks
        chunks = await db["chunks"].find(
            {"document_id": document_id}
        ).sort("chunk_index", 1).to_list(length=20)
        
        if not chunks:
            raise ValueError("No content found in document to generate quiz")
        
        # Build context from chunks - Điều chỉnh context dựa trên số câu hỏi (5-20)
        context_parts = []
        current_length = 0
        # Tăng context dựa trên số câu hỏi: 5 câu = 3000, 10 câu = 5000, 15 câu = 7000, 20 câu = 9000
        max_context_length = min(2000 + (num_questions * 350), 10000)
        
        # Tăng số chunks: 5 câu = 15 chunks, 10 câu = 20 chunks, 15-20 câu = 20 chunks
        max_chunks = min(10 + num_questions, 20)
        for chunk in chunks[:max_chunks]:
            content = chunk.get("content", "")
            if content:
                # Check if adding this chunk would exceed limit
                if current_length + len(content) > max_context_length:
                    break
                context_parts.append(content)
                current_length += len(content)
        
        context_text = "\n\n".join(context_parts)
        
        # Final safety limit
        if len(context_text) > max_context_length:
            context_text = context_text[:max_context_length] + "..."
        
        print(f"[QuizGen] OPTIMIZED Context: {len(context_text)} chars from {len(context_parts)} chunks (limit: {max_context_length})")
        
        # Calculate how many of each type
        if "multiple_choice" in question_types and "true_false" in question_types:
            # Mix: 70% multiple choice, 30% true/false
            num_mc = int(num_questions * 0.7)
            num_tf = num_questions - num_mc
        elif "multiple_choice" in question_types:
            num_mc = num_questions
            num_tf = 0
        elif "true_false" in question_types:
            num_mc = 0
            num_tf = num_questions
        else:
            num_mc = num_questions
            num_tf = 0
        
        # Build prompt
        prompt = self._build_quiz_prompt(
            context_text,
            doc.filename,
            num_mc,
            num_tf,
            difficulty
        )
        
        # Generate quiz using LLM - retry if not enough questions
        max_attempts = 3
        questions = []
        
        for attempt in range(max_attempts):
            try:
                generated = await self._generate_with_llm(prompt, num_questions)
                questions = generated
                
                # Nếu đã tạo đủ hoặc gần đủ số câu hỏi (>= 80%), chấp nhận
                if len(questions) >= num_questions * 0.8:
                    print(f"[QuizGen] ✅ Generated {len(questions)}/{num_questions} questions (attempt {attempt + 1})")
                    break
                else:
                    print(f"[QuizGen] ⚠️ Only generated {len(questions)}/{num_questions} questions, retrying... (attempt {attempt + 1}/{max_attempts})")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2)  # Wait 2 seconds before retry
            except Exception as e:
                print(f"[QuizGen] ❌ Attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                else:
                    raise
        
        print(f"[QuizGen] Final result: Generated {len(questions)}/{num_questions} questions")
        return questions
    
    def _build_quiz_prompt(
        self,
        context: str,
        filename: str,
        num_mc: int,
        num_tf: int,
        difficulty: str,
    ) -> str:
        """Build prompt for LLM to generate quiz"""
        
        difficulty_guide = {
            "easy": """Câu hỏi DỄ (nhớ & hiểu):
- Hỏi về định nghĩa, thuật ngữ cơ bản
- "X là gì?", "Khai báo X bằng từ khóa nào?"
- Đáp án sai rõ ràng, dễ loại trừ
- Học sinh chỉ cần NHỚ để trả lời""",
            "medium": """Câu hỏi TRUNG BÌNH (hiểu & áp dụng):
- Hỏi về cách hoạt động, so sánh khái niệm
- "Khác biệt giữa X và Y?", "Khi nào dùng X?"
- Đáp án sai hợp lý hơn, cần suy nghĩ
- Học sinh cần HIỂU để trả lời""",
            "hard": """Câu hỏi KHÓ (phân tích & tổng hợp):
- Hỏi về nguyên lý, cơ chế hoạt động sâu
- "Tại sao X hoạt động như vậy?", "Phân tích ưu/nhược điểm"
- Đáp án sai rất tinh vi, dễ nhầm
- Học sinh cần PHÂN TÍCH SÂU để trả lời"""
        }
        
        # Tối ưu prompt: ngắn gọn hơn, rõ ràng hơn
        difficulty_short = {
            "easy": "DỄ: định nghĩa, thuật ngữ cơ bản",
            "medium": "TRUNG BÌNH: cách hoạt động, so sánh",
            "hard": "KHÓ: nguyên lý, phân tích sâu"
        }
        
        prompt = f"""Tạo {num_mc + num_tf} câu hỏi từ tài liệu.

NỘI DUNG:
{context}

YÊU CẦU:
- {num_mc} câu TRẮC NGHIỆM (2 đáp án A, B)
- {num_tf} câu ĐÚNG/SAI
- Độ khó: {difficulty_short.get(difficulty, difficulty_short["medium"])}

ĐỊNH DẠNG:
[MC]
Question: [Câu hỏi]
A) [Đáp án A]
B) [Đáp án B]
Correct: A
Explanation: [Giải thích ngắn]
---

[TF]
Question: [Câu hỏi]
Correct: Đúng
Explanation: [Giải thích ngắn]
---

Tạo {num_mc + num_tf} câu hỏi:"""
        
        return prompt
    
    async def _generate_with_llm(self, prompt: str, num_questions: int) -> List[QuizQuestion]:
        """Generate questions using LLM"""
        
        # Try Gemini first with retry logic
        if self.provider == "gemini" and self._gemini_api_key:
            max_retries = 3
            for attempt in range(max_retries):
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
                            "temperature": 0.7,
                            # Tăng tokens để tạo đủ số câu: 5 câu = 3000, 10 câu = 5000, 15 câu = 7000, 20 câu = 8000
                            "maxOutputTokens": min(2000 + (num_questions * 300), 8000),
                            "topK": 40,
                            "topP": 0.95,
                        }
                    }
                    
                    print(f"[QuizGen] Calling Gemini API (attempt {attempt + 1}/{max_retries}) to generate {num_questions} questions")
                    print(f"[QuizGen] Prompt length: {len(prompt)} chars")
                    
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(url, params=params, json=payload)
                        response.raise_for_status()
                        data = response.json()
                        
                        print(f"[QuizGen] Gemini response keys: {data.keys()}")
                        
                        if "candidates" in data and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            print(f"[QuizGen] Candidate keys: {candidate.keys()}")
                            
                            # Check finishReason
                            finish_reason = None
                            if "finishReason" in candidate:
                                finish_reason = candidate["finishReason"]
                                print(f"[QuizGen] Finish reason: {finish_reason}")
                                if finish_reason in ["SAFETY", "RECITATION", "OTHER"]:
                                    print(f"[QuizGen] ⚠️ Request blocked by Gemini: {finish_reason}")
                                    raise Exception(f"Gemini blocked request: {finish_reason}")
                                # MAX_TOKENS is OK - we can still try to parse partial response
                                if finish_reason == "MAX_TOKENS":
                                    print(f"[QuizGen] ⚠️ Response truncated (MAX_TOKENS), but will try to parse partial response")
                            
                            # Handle different response formats - improved parsing
                            full_response = None
                            
                            # Debug: print full candidate structure (truncated for readability)
                            candidate_str = json.dumps(candidate, indent=2, ensure_ascii=False)
                            print(f"[QuizGen] Full candidate: {candidate_str[:1000]}")
                            
                            # Try to extract text from various locations in the response
                            def extract_text_recursive(obj, depth=0, max_depth=5):
                                """Recursively search for text in nested structures"""
                                if depth > max_depth:
                                    return None
                                
                                if isinstance(obj, str) and len(obj.strip()) > 10:
                                    return obj.strip()
                                
                                if isinstance(obj, dict):
                                    # Check common text fields
                                    for key in ["text", "content", "parts"]:
                                        if key in obj:
                                            result = extract_text_recursive(obj[key], depth + 1, max_depth)
                                            if result:
                                                return result
                                    # Recursively check all values
                                    for value in obj.values():
                                        result = extract_text_recursive(value, depth + 1, max_depth)
                                        if result:
                                            return result
                                
                                if isinstance(obj, list):
                                    for item in obj:
                                        result = extract_text_recursive(item, depth + 1, max_depth)
                                        if result:
                                            return result
                                
                                return None
                            
                            # Try standard parsing first
                            if "content" in candidate:
                                content = candidate["content"]
                                print(f"[QuizGen] Content type: {type(content)}, keys: {content.keys() if isinstance(content, dict) else 'N/A'}")
                                
                                # Case 1: Standard format - content.parts[0].text
                                if isinstance(content, dict) and "parts" in content:
                                    if isinstance(content["parts"], list) and len(content["parts"]) > 0:
                                        part = content["parts"][0]
                                        if isinstance(part, dict) and "text" in part:
                                            full_response = part["text"]
                                        elif isinstance(part, str):
                                            full_response = part
                                
                                # Case 2: content chỉ có role, không có parts - thử recursive search
                                elif isinstance(content, dict) and "role" in content and "parts" not in content:
                                    print(f"[QuizGen] ⚠️ Content only has 'role', trying recursive search...")
                                    full_response = extract_text_recursive(candidate)
                                
                                # Case 3: content is a dict with "text" directly
                                elif isinstance(content, dict) and "text" in content:
                                    full_response = content["text"]
                                
                                # Case 4: content is a string
                                elif isinstance(content, str):
                                    full_response = content
                                
                                # Case 5: content might be a list
                                elif isinstance(content, list) and len(content) > 0:
                                    first_item = content[0]
                                    if isinstance(first_item, dict) and "text" in first_item:
                                        full_response = first_item["text"]
                                    elif isinstance(first_item, str):
                                        full_response = first_item
                            
                            # Fallback: recursive search in entire candidate
                            if not full_response:
                                print(f"[QuizGen] Trying recursive search in candidate...")
                                full_response = extract_text_recursive(candidate)
                            
                            # Final fallback: check candidate directly
                            if not full_response:
                                if "text" in candidate:
                                    full_response = candidate["text"]
                                elif isinstance(candidate, str):
                                    full_response = candidate
                            
                            if not full_response:
                                print(f"[QuizGen] ❌ Could not extract text from candidate")
                                print(f"[QuizGen] Full candidate structure: {json.dumps(candidate, indent=2, ensure_ascii=False)}")
                                raise Exception("Could not extract text from Gemini response")
                            
                            print(f"[QuizGen] ✅ Extracted response: {len(full_response)} chars")
                            
                            questions = self._parse_quiz_response(full_response)
                            print(f"[QuizGen] ✅ Gemini generated {len(questions)} questions successfully")
                            
                            if len(questions) == 0:
                                print(f"[QuizGen] ⚠️ No questions parsed from response")
                                print(f"[QuizGen] Response preview: {full_response[:500]}")
                                raise Exception("Failed to parse questions from Gemini response")
                            
                            return questions
                        else:
                            print(f"[QuizGen] Gemini API returned unexpected format: {data}")
                            raise Exception("Unexpected response format from Gemini")
                    
                except httpx.HTTPStatusError as e:
                    # Check if it's a 503 (Service Unavailable) or 429 (Rate Limit)
                    if e.response.status_code in [503, 429] and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                        print(f"[QuizGen] Gemini {e.response.status_code} error, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"[QuizGen] Gemini API call failed after {attempt + 1} attempts: {e}")
                        import traceback
                        print(f"[QuizGen] Traceback: {traceback.format_exc()}")
                        break
                except Exception as e:
                    print(f"[QuizGen] Gemini API call failed: {e}")
                    import traceback
                    print(f"[QuizGen] Traceback: {traceback.format_exc()}")
                    break
        
        # Try OpenAI
        if self.provider == "openai" and self._openai_client:
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "Bạn là giáo viên chuyên nghiệp tạo câu hỏi trắc nghiệm từ tài liệu học tập."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ]
                
                print(f"[QuizGen] Calling OpenAI API to generate questions")
                response = await asyncio.to_thread(
                    self._openai_client.chat.completions.create,
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.7,
                )
                
                full_response = response.choices[0].message.content
                questions = self._parse_quiz_response(full_response)
                print(f"[QuizGen] OpenAI generated {len(questions)} questions")
                return questions
                
            except Exception as e:
                print(f"[QuizGen] OpenAI API call failed: {e}")
        
        # Fallback error
        raise Exception(
            "Không thể tạo quiz. Hệ thống AI đang gặp lỗi hoặc chưa được cấu hình đúng."
        )
    
    def _parse_quiz_response(self, response: str) -> List[QuizQuestion]:
        """Parse LLM response to extract quiz questions"""
        
        questions = []
        
        # Try multiple delimiters
        delimiters = ["---", "\n---\n", "---\n"]
        parts = []
        for delimiter in delimiters:
            if delimiter in response:
                parts = response.split(delimiter)
                print(f"[QuizGen] Split by '{delimiter}': {len(parts)} parts")
                break
        
        # If no delimiter, try to find [MC] and [TF] markers
        if not parts or len(parts) == 1:
            print(f"[QuizGen] No delimiter found, searching for [MC] and [TF] markers")
            mc_positions = [m.start() for m in re.finditer(r'\[MC\]', response)]
            tf_positions = [m.start() for m in re.finditer(r'\[TF\]', response)]
            all_positions = sorted([(pos, 'MC') for pos in mc_positions] + [(pos, 'TF') for pos in tf_positions])
            
            if all_positions:
                parts = []
                for i, (pos, qtype) in enumerate(all_positions):
                    start = pos
                    end = all_positions[i + 1][0] if i + 1 < len(all_positions) else len(response)
                    parts.append(response[start:end])
                print(f"[QuizGen] Found {len(parts)} questions by markers")
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part or len(part) < 20:  # Skip very short parts
                continue
            
            print(f"[QuizGen] Parsing part {i+1}/{len(parts)} (length: {len(part)} chars)")
            
            # Detect question type (more flexible)
            if "[MC]" in part or ("Question:" in part and ("A)" in part or "B)" in part)):
                question = self._parse_multiple_choice(part)
                if question:
                    questions.append(question)
                    print(f"[QuizGen] ✅ Parsed MC question {len(questions)}")
                else:
                    print(f"[QuizGen] ❌ Failed to parse MC question from part {i+1}")
            elif "[TF]" in part or "Đúng" in part or "Sai" in part:
                question = self._parse_true_false(part)
                if question:
                    questions.append(question)
                    print(f"[QuizGen] ✅ Parsed TF question {len(questions)}")
                else:
                    print(f"[QuizGen] ❌ Failed to parse TF question from part {i+1}")
        
        print(f"[QuizGen] Total parsed: {len(questions)} questions")
        return questions
    
    def _parse_multiple_choice(self, text: str) -> Optional[QuizQuestion]:
        """Parse multiple choice question (2 đáp án A, B)"""
        try:
            # Extract question - more flexible patterns
            question_patterns = [
                r'Question:\s*(.+?)(?=\n[A-B][\)\.])',
                r'Q:\s*(.+?)(?=\n[A-B][\)\.])',
                r'(.+?)(?=\nA\)|A\.)',
            ]
            
            question_text = None
            for pattern in question_patterns:
                question_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if question_match:
                    question_text = question_match.group(1).strip()
                    # Clean up [MC] prefix
                    question_text = re.sub(r'^\[MC\]\s*', '', question_text, flags=re.IGNORECASE)
                    break
            
            if not question_text:
                print(f"[QuizGen] Could not extract question from: {text[:200]}")
                return None
            
            # Extract options - chỉ tìm A và B
            options = []
            for letter in ['A', 'B']:
                option_patterns = [
                    rf'{letter}[\)\.]\s*(.+?)(?=\n[A-B][\)\.]|Correct:|Explanation:|$)',
                    rf'{letter}\)\s*(.+?)(?=\n[A-B]\)|Correct:|$)',
                ]
                
                option_text = None
                for pattern in option_patterns:
                    option_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                    if option_match:
                        option_text = option_match.group(1).strip()
                        break
                
                if option_text:
                    options.append(option_text)
            
            if len(options) < 2:
                print(f"[QuizGen] Only found {len(options)} options, need 2")
                return None
            
            # Extract correct answer - chỉ A hoặc B
            correct_patterns = [
                r'Correct:\s*([A-B])',
                r'Answer:\s*([A-B])',
                r'Đáp án:\s*([A-B])',
            ]
            
            correct_letter = None
            for pattern in correct_patterns:
                correct_match = re.search(pattern, text, re.IGNORECASE)
                if correct_match:
                    correct_letter = correct_match.group(1).upper()
                    break
            
            if not correct_letter or correct_letter not in ['A', 'B']:
                print(f"[QuizGen] Could not find valid correct answer (A or B)")
                return None
            
            correct_index = ord(correct_letter) - ord('A')
            correct_answer = options[correct_index] if 0 <= correct_index < len(options) else options[0]
            
            # Extract explanation
            explanation_patterns = [
                r'Explanation:\s*(.+?)(?=Section:|$)',
                r'Giải thích:\s*(.+?)(?=Section:|$)',
            ]
            
            explanation = "Không có giải thích"
            for pattern in explanation_patterns:
                explanation_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if explanation_match:
                    explanation = explanation_match.group(1).strip()
                    break
            
            # Extract section (optional)
            section_match = re.search(r'Section:\s*(.+?)(?=\n|$)', text, re.IGNORECASE)
            section = section_match.group(1).strip() if section_match else None
            
            return QuizQuestion(
                question_type="multiple_choice",
                question_text=question_text,
                options=options[:2],  # Chỉ lấy 2 đáp án
                correct_answer=correct_answer,
                explanation=explanation,
                section=section,
            )
        except Exception as e:
            print(f"[QuizGen] Error parsing MC question: {e}")
            import traceback
            print(f"[QuizGen] Traceback: {traceback.format_exc()}")
            return None
    
    def _parse_true_false(self, text: str) -> Optional[QuizQuestion]:
        """Parse true/false question"""
        try:
            # Extract question - more flexible
            question_patterns = [
                r'Question:\s*(.+?)(?=Correct:|Answer:|Đáp án:)',
                r'Q:\s*(.+?)(?=Correct:|Answer:)',
                r'(.+?)(?=Correct:|Answer:)',
            ]
            
            question_text = None
            for pattern in question_patterns:
                question_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if question_match:
                    question_text = question_match.group(1).strip()
                    # Clean up [TF] prefix
                    question_text = re.sub(r'^\[TF\]\s*', '', question_text, flags=re.IGNORECASE)
                    break
            
            if not question_text:
                print(f"[QuizGen] Could not extract TF question from: {text[:200]}")
                return None
            
            # Extract correct answer - more flexible
            correct_patterns = [
                r'Correct:\s*(Đúng|Sai|True|False|T|F)',
                r'Answer:\s*(Đúng|Sai|True|False)',
                r'Đáp án:\s*(Đúng|Sai)',
            ]
            
            correct_text = None
            for pattern in correct_patterns:
                correct_match = re.search(pattern, text, re.IGNORECASE)
                if correct_match:
                    correct_text = correct_match.group(1)
                    break
            
            if not correct_text:
                print(f"[QuizGen] Could not find TF correct answer")
                return None
            
            # Normalize to Vietnamese
            correct_text_lower = correct_text.lower().strip()
            if correct_text_lower in ['đúng', 'true', 't']:
                correct_answer = "Đúng"
            else:
                correct_answer = "Sai"
            
            # Extract explanation
            explanation_patterns = [
                r'Explanation:\s*(.+?)(?=Section:|$)',
                r'Giải thích:\s*(.+?)(?=Section:|$)',
            ]
            
            explanation = "Không có giải thích"
            for pattern in explanation_patterns:
                explanation_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if explanation_match:
                    explanation = explanation_match.group(1).strip()
                    break
            
            # Extract section (optional)
            section_match = re.search(r'Section:\s*(.+?)(?=\n|$)', text, re.IGNORECASE)
            section = section_match.group(1).strip() if section_match else None
            
            return QuizQuestion(
                question_type="true_false",
                question_text=question_text,
                options=["Đúng", "Sai"],
                correct_answer=correct_answer,
                explanation=explanation,
                section=section,
            )
        except Exception as e:
            print(f"[QuizGen] Error parsing TF question: {e}")
            import traceback
            print(f"[QuizGen] Traceback: {traceback.format_exc()}")
            return None


quiz_generator_service = QuizGeneratorService()

