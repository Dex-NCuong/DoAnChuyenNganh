import asyncio
import json
from datetime import datetime

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


def detect_query_type_fast(question: str) -> str:
    """Enhanced query type detection với support cho code và reasoning."""
    q = question.lower()
    
    # PRIORITY 1: Code analysis questions (Tầng 3)
    code_patterns = [
        r'phân\s*tích.*?(code|đoạn\s*code|lỗi)',
        r'sửa.*?(code|lỗi|bug)',
        r'đoạn\s*code.*?(sai|lỗi|bug|đúng)',
        r'chấm\s*điểm.*?code',
        r'code.*?(có\s*vấn\s*đề|sai|lỗi)',
        r'tìm\s*lỗi.*?code',
    ]
    if any(re.search(p, q) for p in code_patterns):
        return "CODE_ANALYSIS"
    
    # PRIORITY 2: Exercise generation (Tầng 3)
    exercise_patterns = [
        r'tạo.*?bài\s*tập',
        r'viết.*?(function|hàm).*?dựa\s*trên',
        r'áp\s*dụng.*?(vào|để.*?viết).*?code',
        r'cho.*?ví\s*dụ.*?code',
        r'viết.*?code.*?theo',
    ]
    if any(re.search(p, q) for p in exercise_patterns):
        return "EXERCISE_GENERATION"
    
    # PRIORITY 3: Multi-concept reasoning (Tầng 4)
    reasoning_patterns = [
        r'dựa\s*trên.*?(và|,).*?(hãy|viết|giải\s*thích)',
        r'kết\s*hợp.*?(và|,)',
        r'áp\s*dụng.*?(và|,)',
        r'(hoisting|scope|closure).*?(và|,).*(function|loop|variable)',
        r'giải\s*thích.*?cơ\s*chế.*?(và|,)',
    ]
    if any(re.search(p, q) for p in reasoning_patterns):
        return "MULTI_CONCEPT_REASONING"
    
    # PRIORITY 4: Section query - CRITICAL FIX: More comprehensive patterns
    section_patterns = [
        r'(phần|chương|part)\s+\d+\s+(có|nói|là|gồm)',
        r'nội\s*dung\s+(phần|chương|part)\s+\d+',
        r'chi\s*tiết.*?(phần|chương|part)\s+\d+',
        r'rõ\s+hơn.*?(phần|chương|part)\s+\d+',
        # NEW PATTERNS - More comprehensive
        r'nội\s*dung.*?(phần|chương|part)\s+\d+',
        r'(phần|chương|part)\s+\d+.*?(gì|nào|những\s*gì)',
        r'trong\s+(phần|chương|part)\s+\d+',
        r'(phần|chương|part)\s+\d+\s+bao\s*gồm',
        r'tìm\s*hiểu.*?(phần|chương|part)\s+\d+',
        r'giới\s*thiệu.*?(phần|chương|part)\s+\d+',
    ]
    if any(re.search(p, q) for p in section_patterns):
        return "SECTION_OVERVIEW"
    
    # PRIORITY 5: Document overview
    overview_patterns = [
        r'trong\s+(file|tài\s*liệu)\s+này\s+có\s+gì',
        r'(file|tài\s*liệu)\s+này\s+(nói|viết|đề\s*cập)\s+về\s+gì',
        r'tổng\s*quan\s+(file|tài\s*liệu)',
        r'mục\s*lục',
    ]
    if any(re.search(p, q) for p in overview_patterns):
        return "DOCUMENT_OVERVIEW"
    
    # PRIORITY 6: Comparative/synthesis questions (Tầng 2)
    comparative_patterns = [
        r'so\s*sánh',
        r'khác.*?gì',
        r'giống.*?gì',
        r'phân\s*biệt',
        r'(sự\s*)?khác\s*nhau.*?giữa',
        r'gộp.*?kiến\s*thức',
        r'kết\s*hợp.*?từ',
    ]
    if any(re.search(p, q) for p in comparative_patterns):
        return "COMPARE_SYNTHESIZE"
    
    # PRIORITY 7: List/enumerate questions
    if any(kw in q for kw in ["liệt kê", "cho ví dụ", "ví dụ cho", "bao nhiêu"]):
        if "hãy liệt kê" in q or "cho ví dụ" in q or "liệt kê" in q:
            return "EXPAND"
    
    # PRIORITY 8: Existence check
    if any(kw in q for kw in ["có đề cập", "có nói", "tài liệu có"]):
        return "EXISTENCE"
    
    # PRIORITY 9: Explanation/elaboration
    if any(kw in q for kw in ["giải thích", "rõ hơn", "tại sao", "ví dụ"]):
        return "EXPAND"
    
    return "DIRECT"


def build_gemini_optimized_prompt(
    question: str,
    context_text: str,
    chunk_similarities: List[float],
    query_type: str = "DIRECT"
) -> str:
    """
    Gemini 2.5 Flash optimized prompt - SHORT, STRICT, STRUCTURED.
    Target: <1000 tokens for system instructions.
    """
    
    # Auto-detect query type
    q_lower = question.lower()
    
    # CRITICAL FIX: Mở rộng patterns cho SECTION_OVERVIEW detection
    section_query_patterns = [
        r'(phần|chương|part)\s+(\d+)\s+(có|nói|là|gồm)',  # "phần 8 có gì"
        r'nội\s*dung\s+(phần|chương|part)\s+(\d+)',      # "nội dung phần 8"
        r'(phần|chương|part)\s+(\d+)\s+.*?(gì|nào)',      # "phần 8 nói gì"
        # THÊM CÁC PATTERN MỚI
        r'chi\s*tiết.*?(phần|chương|part)\s+(\d+)',       # "chi tiết về phần 8"
        r'(phần|chương|part)\s+(\d+).*?chi\s*tiết',       # "phần 8 chi tiết"
        r'giải\s*thích.*?(phần|chương|part)\s+(\d+)',     # "giải thích phần 8"
        r'(phần|chương|part)\s+(\d+).*?giải\s*thích',     # "phần 8 giải thích"
        r'tìm\s*hiểu.*?(phần|chương|part)\s+(\d+)',       # "tìm hiểu phần 8"
        r'(phần|chương|part)\s+(\d+).*?tìm\s*hiểu',       # "phần 8 tìm hiểu"
        r'về\s+(phần|chương|part)\s+(\d+)',               # "về phần 8", "chi tiết hơn về phần 8"
        r'(phần|chương|part)\s+(\d+)\s+là\s+gì',          # "phần 8 là gì"
        r'(phần|chương|part)\s+(\d+)\s+nói\s+về',         # "phần 8 nói về"
        r'(phần|chương|part)\s+(\d+)\s+bao\s+gồm',        # "phần 8 bao gồm"
        # CRITICAL: Thêm patterns cho câu có "chi tiết hơn"
        r'chi\s*tiết\s+hơn.*?(phần|chương|part)\s+(\d+)',  # "chi tiết hơn PHẦN 8"
        r'rõ\s+hơn.*?(phần|chương|part)\s+(\d+)',          # "rõ hơn về PHẦN 8"
        r'nói\s+rõ.*?(phần|chương|part)\s+(\d+)',          # "nói rõ PHẦN 8"
        # Pattern đặc biệt: bắt cả format "PHẦN 8: Title"
        r'(phần|chương|part)\s+(\d+)[:：]',                 # "PHẦN 8:" or "PHẦN 8："
    ]
    
    is_section_query = False
    section_match = None
    section_num = None
    for pattern in section_query_patterns:
        match = re.search(pattern, q_lower)
        if match:
            is_section_query = True
            section_match = match
            # Lấy section number từ group phù hợp (có thể là group 1 hoặc 2 tùy pattern)
            groups = match.groups()
            for i, group in enumerate(groups, 1):
                if group and group.isdigit():
                    section_num = group
                    break
            # Fallback: nếu không tìm thấy số trong groups, thử extract từ match string
            if not section_num:
                # Extract số từ toàn bộ match
                num_match = re.search(r'\d+', match.group(0))
                if num_match:
                    section_num = num_match.group(0)
            break
    
    # Detect other query modes
    is_overview = any(re.search(p, q_lower) for p in [
        r'trong\s+(file|tài\s*liệu)\s+này\s+có\s+gì',
        r'(file|tài\s*liệu)\s+này\s+(nói|viết|đề\s*cập)\s+về\s+gì',
        r'tổng\s*quan\s+(file|tài\s*liệu)',
        r'mục\s*lục',
    ])
    
    # Determine mode based on query_type
    if query_type == "CODE_ANALYSIS":
        mode = "CODE_ANALYSIS"
        existence_subtype = None
    elif query_type == "EXERCISE_GENERATION":
        mode = "EXERCISE_GENERATION"
        existence_subtype = None
    elif query_type == "MULTI_CONCEPT_REASONING":
        mode = "MULTI_CONCEPT_REASONING"
        existence_subtype = None
    elif query_type == "COMPARE_SYNTHESIZE":
        mode = "COMPARE_SYNTHESIZE"
        existence_subtype = None
    elif is_section_query:
        mode = "SECTION_OVERVIEW"
        existence_subtype = None
    elif is_overview:
        mode = "DOCUMENT_OVERVIEW"
        existence_subtype = None
    else:
        # Fallback to old detection logic
        is_too_broad = any(kw in q_lower for kw in [
            "toàn bộ", "tất cả mọi", "every", "all"
        ])
        is_list_all = any(kw in q_lower for kw in ["liệt kê", "cho ví dụ", "bao nhiêu"])
        is_expanded = is_list_all or any(kw in q_lower for kw in ["giải thích", "rõ hơn", "tại sao"])
        is_existence = any(kw in q_lower for kw in ["có đề cập", "có nói", "tài liệu có"])
        is_comparative = any(kw in q_lower for kw in ["so sánh", "khác", "giống"])
        
        if is_too_broad:
            mode = "TOO_BROAD"
            existence_subtype = None
        elif is_expanded:
            mode = "EXPAND"
            existence_subtype = None
        elif is_existence:
            mode = "EXISTENCE"
            is_mention_only = any(kw in q_lower for kw in ["có đề cập", "có nhắc đến", "có nói đến"])
            existence_subtype = "MENTION_ONLY" if is_mention_only else "EXPLAINS"
        elif is_comparative:
            mode = "COMPARE"
            existence_subtype = None
        else:
            mode = "DIRECT"
            existence_subtype = None
    
    # Check similarity threshold
    max_sim = max(chunk_similarities) if chunk_similarities else 0
    auto_fallback_warning = ""
    if max_sim < 0.4:
        auto_fallback_warning = "\n⚠️ WARNING: Max similarity < 0.4 → Must return FALLBACK."
    
    # Build mode-specific instructions
    mode_instructions = ""
    
    if mode == "DOCUMENT_OVERVIEW":
        mode_instructions = """

## 📚 DOCUMENT OVERVIEW MODE

User is asking for a complete overview of the entire document.

**MANDATORY STEPS:**
1. **Find TABLE OF CONTENTS chunk:** Look for chunks containing "MỤC LỤC" or multiple "PHẦN X"
2. **List ALL main sections:** Extract all section headings (PHẦN 1, PHẦN 2, ..., PHẦN 10)
3. **Describe each section:** Provide 1-2 sentences describing what each section covers
4. **Use subsection info:** If available, mention key subsections (e.g., "8.1 String, 8.2 Function")

**OUTPUT FORMAT:**
```
Tài liệu này bao gồm các phần sau:

1. **PHẦN 1: [Title from document]** - [2-3 sentences describing content]

2. **PHẦN 2: [Title]** - [2-3 sentences describing content]

3. **PHẦN 3: [Title]** - [2-3 sentences describing content]

...

10. **PHẦN 10: [Title]** - [2-3 sentences describing content]

[Cite chunks used]
```

**CRITICAL RULES:**
- MUST list ALL main sections (don't skip any)
- Use section titles from document (don't invent titles)
- If TABLE OF CONTENTS chunk exists, prioritize it
- Confidence should be 0.95 if TABLE OF CONTENTS found, 0.85 otherwise

**CRITICAL OUTPUT FORMAT (MUST BE VALID JSON):**
```json
{{
  "answer": "Tài liệu này bao gồm các phần sau:\\n\\n1. **PHẦN 1: [Title]** - [description]\\n\\n2. **PHẦN 2: [Title]** - [description]\\n\\n...",
  "answer_type": "DOCUMENT_OVERVIEW",
  "chunks_used": [chunk_numbers],
  "confidence": 0.90-0.95,
  "sentence_mapping": [...],
  "sources": {{"from_document": true, "from_external_knowledge": false}}
}}
```

⚠️ CRITICAL: Output MUST be valid JSON. NO markdown blocks, NO extra text.

"""
    elif mode == "CODE_ANALYSIS":
        mode_instructions = """

## 🔍 CODE ANALYSIS MODE (Tầng 3)

User is asking to analyze code based on document knowledge.

**MANDATORY STEPS:**
1. **Extract Concepts**: Identify relevant concepts from chunks (e.g., "scope", "hoisting", "closure")
2. **Apply to Code**: Apply these concepts to analyze the provided code
3. **Step-by-step Reasoning**: 
   - What does each line do?
   - What concept from the document applies here?
   - What's the issue/what works correctly?
4. **Explanation**: Explain clearly with references to document

**OUTPUT FORMAT:**
```
Phân tích code:

[Code snippet với line numbers]

1. Dòng X: [Giải thích dựa trên concept từ document]
2. Dòng Y: [Vấn đề/Điểm đúng + tại sao]

Kết luận: [Tóm tắt + đề xuất sửa nếu có lỗi]

[Cite chunks used]
```

**CRITICAL RULES:**
- DO NOT just quote chunks - apply concepts to analyze
- Show reasoning process clearly
- If code has errors, explain WHY based on document knowledge
- Confidence should be 0.8-0.95 if concepts found in document

**CRITICAL OUTPUT FORMAT (MUST BE VALID JSON):**
```json
{{
  "answer": "Phân tích code:\\n\\n1. Dòng X: [explanation]\\n2. Problem: [explanation]",
  "answer_type": "CODE_ANALYSIS",
  "chunks_used": [chunk_numbers],
  "confidence": 0.75-0.85,
  "reasoning_steps": [
    "Step 1: Identify concepts used",
    "Step 2: Apply to code",
    "Step 3: Explain issue"
  ],
  "sentence_mapping": [...],
  "sources": {{"from_document": true, "from_external_knowledge": false}}
}}
```

⚠️ CRITICAL: Output MUST be valid JSON. NO markdown blocks, NO extra text.

"""
    elif mode == "EXERCISE_GENERATION":
        mode_instructions = """

## 📝 EXERCISE GENERATION MODE (Tầng 3)

User wants to create code/exercises based on document concepts.

**MANDATORY STEPS:**
1. **Understand Concepts**: Extract relevant concepts from chunks
2. **Synthesize**: Combine concepts to create new examples
3. **Create Code**: Write NEW code (not from document) applying these concepts
4. **Explain**: Link each part of code to concepts in document

**OUTPUT FORMAT:**
```
Dựa trên kiến thức về [concepts] trong tài liệu:

[New code here]

Giải thích từng phần:
- Line X-Y: Áp dụng [concept from chunk Z]
- Line A-B: Kết hợp [concept 1] và [concept 2]

[Cite chunks used]
```

**CRITICAL RULES:**
- Code must be NEW, not copied from document
- MUST explain how each part relates to document concepts
- If combining multiple concepts, cite multiple chunks
- Confidence: 0.8-0.9 if concepts clearly found

"""
    elif mode == "MULTI_CONCEPT_REASONING":
        mode_instructions = """

## 🧠 MULTI-CONCEPT REASONING MODE (Tầng 4)

User asks question requiring reasoning across multiple concepts.

**MANDATORY STEPS:**
1. **Identify Concepts**: List all concepts mentioned in question
2. **Extract from Document**: Find chunks for EACH concept
3. **Connect**: Show how concepts relate to each other
4. **Synthesize**: Combine understanding to answer question
5. **Reason**: Apply logic beyond just quoting

**OUTPUT FORMAT:**
```
Để trả lời câu hỏi này, cần kết hợp các khái niệm:

1. [Concept 1] (từ chunk X): [Brief explanation]
2. [Concept 2] (từ chunk Y): [Brief explanation]

Kết nối các khái niệm:
[Explain how they relate, with reasoning]

Áp dụng vào câu hỏi:
[Answer with synthesis of concepts]

[Cite all chunks used]
```

**CRITICAL RULES:**
- MUST cite chunks for EACH concept
- Show reasoning process, not just quotes
- If concepts from different sections, cite both
- Confidence: 0.7-0.85 (reasoning adds uncertainty)
- If any concept missing from document → note it explicitly

**CRITICAL OUTPUT FORMAT (MUST BE VALID JSON):**
```json
{{
  "answer": "Để trả lời câu hỏi này, cần kết hợp các khái niệm:\\n\\n1. [Concept 1] (từ chunk X): [Brief explanation]\\n2. [Concept 2] (từ chunk Y): [Brief explanation]\\n\\nKết nối các khái niệm:\\n[Explain how they relate, with reasoning]\\n\\nÁp dụng vào câu hỏi:\\n[Answer with synthesis of concepts]",
  "answer_type": "MULTI_CONCEPT_REASONING",
  "chunks_used": [chunk_numbers],
  "confidence": 0.7-0.85,
  "reasoning_steps": [
    "Step 1: Identify all concepts",
    "Step 2: Extract from document",
    "Step 3: Connect concepts",
    "Step 4: Synthesize answer"
  ],
  "sentence_mapping": [...],
  "sources": {{"from_document": true, "from_external_knowledge": false}}
}}
```

⚠️ CRITICAL: Output MUST be valid JSON. NO markdown blocks, NO extra text.

"""
    elif mode == "COMPARE_SYNTHESIZE":
        mode_instructions = """

## 🔀 COMPARE & SYNTHESIZE MODE (Tầng 2)

User wants to compare concepts or synthesize knowledge from multiple sections.

**MANDATORY STEPS:**
1. **Find All Relevant Chunks**: Search for ALL mentioned concepts/items
2. **Extract Key Points**: For each concept, list main points
3. **Compare**: Show similarities and differences
4. **Synthesize**: Create coherent understanding

**OUTPUT FORMAT (for comparison):**
```
So sánh [A] và [B]:

**Giống nhau:**
- [Point from chunks X, Y]

**Khác nhau:**
| Aspect | [A] | [B] |
|--------|-----|-----|
| [Aspect 1] | [from chunk X] | [from chunk Y] |

[Cite chunks used]
```

**CRITICAL RULES:**
- MUST find chunks for ALL items being compared
- If one item has more chunks, it's OK - use what's available
- Show explicit citations for each point
- Confidence: 0.7-0.9 depending on chunk coverage

"""
    elif is_section_query and section_num:
        mode_instructions = f"""

## 🎯 SECTION OVERVIEW QUERY DETECTED (MANDATORY FORMAT)

User is asking: "PHẦN {section_num} nói về gì?"

**CRITICAL RULES - VIOLATION = SYSTEM FAILURE:**
1. ✅ YOU MUST return answer_type = "SECTION_OVERVIEW"
2. ✅ YOU MUST NOT return "FALLBACK" or "TOO_BROAD"
3. ✅ Chunks about PHẦN {section_num} ARE AVAILABLE - use them!

**MANDATORY OUTPUT STRUCTURE:**
```
PHẦN {section_num}: [Extract FULL section title from chunks]

Nội dung chính bao gồm:

1. **[Topic 1 name]** - [2-3 sentences explaining this topic using info from chunks]

2. **[Topic 2 name]** - [2-3 sentences explaining this topic]

3. **[Topic 3 name]** - [2-3 sentences explaining this topic]

...

[Minimum 4-6 topics, cite chunk numbers used]
```

**EXTRACTION RULES:**
- Search chunks for heading markers: "PHẦN {section_num}:", section titles, etc.
- Extract section title from heading chunk
- Extract **ALL subsection headings** (e.g., 8.1, 8.2, 8.3...) as topics
- For each topic, synthesize 2-3 sentences from related chunks
- **CRITICAL:** Don't stop at 2 topics - find ALL subsections

**CONFIDENCE RULES:**
- If you found chunks with "PHẦN {section_num}" → confidence = 0.90-0.95
- If chunks contain subsection numbers (8.1, 8.2) → confidence = 0.95
- NEVER return confidence < 0.85 for section queries

**DEBUG CHECK:**
- Did I extract the section title? ✅/❌
- Did I list ALL subsections (not just 2)? ✅/❌
- Did I write 2-3 sentences per topic? ✅/❌
- Did I cite chunk numbers? ✅/❌

"""
    
    prompt = f"""# SYSTEM RULES (DO NOT describe these rules, just follow them)

{mode_instructions}

## HARD FAILS (Violate any → immediate FALLBACK)
1. DO NOT answer if info not in chunks
2. DO NOT synthesize meaning from multiple unrelated chunks UNLESS in REASONING mode
3. DO NOT infer from headings/numbering EXCEPT for SECTION_OVERVIEW
4. If similarity < 0.4 for ALL chunks → FALLBACK required{auto_fallback_warning}

## MODE: {mode}
- CODE_ANALYSIS: Extract concepts → Apply to code → Step-by-step reasoning → Cite chunks
- EXERCISE_GENERATION: Understand concepts → Create NEW code → Explain links to document
- MULTI_CONCEPT_REASONING: Identify concepts → Extract from doc → Connect → Synthesize → Reason
- COMPARE_SYNTHESIZE: Find all chunks → Extract points → Compare/synthesize → Cite all
- SECTION_OVERVIEW: Full title + detailed numbered list (4-6 items, 2-3 sentences each)
- DOCUMENT_OVERVIEW: List main sections with descriptions
- DIRECT: Use only document text (4-6 sentences max)
- EXPAND: List ALL items if "liệt kê", or explain with examples
- COMPARE: Bullet list format
- EXISTENCE: Check if mentioned vs. explained in detail
- TOO_BROAD: Return "Câu hỏi quá rộng. Vui lòng hỏi về chủ đề cụ thể."

## REASONING GUIDELINES (for Tier 3-4 questions)
For CODE_ANALYSIS, EXERCISE_GENERATION, MULTI_CONCEPT_REASONING modes:
1. **You MAY use logical reasoning** beyond just quoting chunks
2. **You MAY create new examples** based on concepts from document
3. **You MUST cite** which chunks provided the base knowledge
4. **Mark synthesis**: Use phrases like "Áp dụng [concept từ chunk X]" or "Dựa trên [concept], ta suy ra..."

Example (CODE_ANALYSIS):
```
❌ BAD: "Chunk 5 nói về scope. Đoạn code này có lỗi scope."
✅ GOOD: "Dựa trên khái niệm scope trong chunk 5 (biến var có function scope), ta thấy dòng `console.log(i)` sẽ báo lỗi vì `i` được khai báo với `let` trong vòng for (block scope), không truy cập được bên ngoài."
```

## SELF-CHECK (MANDATORY before output)
1. Does answer directly address the question type?
2. For CODE/EXERCISE/REASONING: Did I show reasoning process?
3. For COMPARE: Did I find chunks for ALL items?
4. Are all citations correct and specific?
5. If FALLBACK → chunks_used MUST be []

## CHUNKS

{context_text}

## QUESTION

{question}

## OUTPUT (JSON ONLY - no markdown, no comments, no extra text)

⚠️ CRITICAL: You MUST return ONLY a valid JSON object. NO text before or after JSON.
⚠️ DO NOT include markdown code blocks (```json).
⚠️ DO NOT include any explanation outside the JSON object.

Example of CORRECT output:
{{
  "answer": "PHẦN 8: CÚ PHÁP ES6\\n\\nNội dung chính bao gồm:\\n\\n1. **String** - Template Literals...",
  "answer_type": "SECTION_OVERVIEW",
  "chunks_used": [204, 205, 208],
  "confidence": 0.95,
  "sentence_mapping": [{{"sentence": "first sentence", "chunk": 204, "external": false}}],
  "sources": {{"from_document": true, "from_external_knowledge": false}}
}}

Example of WRONG output (NEVER do this):
"Here is the answer: PHẦN 8..." ← NO! This is not JSON!

{{
  "answer": "string",
  "answer_type": "CODE_ANALYSIS|EXERCISE_GENERATION|MULTI_CONCEPT_REASONING|COMPARE_SYNTHESIZE|SECTION_OVERVIEW|DOCUMENT_OVERVIEW|DIRECT|EXPAND|COMPARE|EXISTENCE|TOO_BROAD|FALLBACK",
  "chunks_used": [integers],
  "confidence": 0.0-1.0,
  "sentence_mapping": [
    {{"sentence": "first sentence of answer", "chunk": 1, "external": false}},
    {{"sentence": "second sentence", "chunk": 3, "external": false}}
  ],
  "sources": {{"from_document": bool, "from_external_knowledge": bool}}
}}

CRITICAL: 
- If FALLBACK → chunks_used=[], confidence=0.0
- If CODE_ANALYSIS/REASONING → include reasoning_steps
- If COMPARE_SYNTHESIZE with missing concept → note in answer, confidence < 0.7
"""
    return prompt





class RAGService:

    def __init__(self):

        self.embedding_service = EmbeddingService()

        self.provider = settings.llm_provider.lower()

        self.model = settings.llm_model

        self.max_tokens = settings.llm_max_tokens

        # CRITICAL FIX: Giảm max_context_length để tránh MAX_TOKENS error
        self.max_context_length = min(12000, settings.rag_max_context_length)
        
        # CRITICAL FIX: Tăng max_output_tokens cho Gemini
        # CRITICAL FIX: Tăng max_output_tokens cho câu trả lời dài
        self.max_output_tokens = 12000  # Increased from 8192

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
    
    def _determine_max_chunks_for_query(self, question: str, query_type: str) -> int:
        """Dynamically determine max chunks based on query complexity."""
        q_lower = question.lower()
        
        # CRITICAL FIX: DOCUMENT_OVERVIEW cần NHIỀU chunks nhất
        if query_type == "DOCUMENT_OVERVIEW":
            return 50  # Đủ để cover toàn bộ mục lục + overview chunks
        
        # CRITICAL FIX: SECTION_OVERVIEW cần chunks vừa phải
        if query_type == "SECTION_OVERVIEW":
            return 30  # Đủ để cover toàn bộ subsections của 1 phần
        
        # Tier 4 (Reasoning): Cần nhiều chunks
        if query_type in ["MULTI_CONCEPT_REASONING", "CODE_ANALYSIS", "EXERCISE_GENERATION"]:
            # Count concepts mentioned
            concept_keywords = [
                "hoisting", "scope", "closure", "function", "arrow", "class",
                "object", "array", "loop", "for", "while", "if", "variable",
                "const", "let", "var", "promise", "async", "callback"
            ]
            concepts_found = sum(1 for kw in concept_keywords if kw in q_lower)
            
            if concepts_found >= 3:
                return 30
            elif concepts_found >= 2:
                return 25
            else:
                return 20
        
        # Tier 2 (Compare/Synthesize): Cần chunks từ nhiều sections
        if query_type in ["COMPARE_SYNTHESIZE", "COMPARE"]:
            # Check if comparing 2+ items
            if any(word in q_lower for word in ["và", "với", "so với", ","]):
                return 25  # Need chunks for multiple items
            return 20
        
        # Tier 3 (List all / Enumerate)
        if any(kw in q_lower for kw in ["liệt kê", "tất cả", "bao nhiêu", "cho ví dụ"]):
            return 20  # Need more chunks to find all items
        
        # Tier 1 (Basic retrieval)
        return 15  # Default
    
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

    def _is_fallback_answer(self, answer: str) -> bool:
        """Enhanced fallback detection."""
        if not answer or len(answer.strip()) < 20:
            return True
        
        answer_lower = answer.lower()
        fallback_patterns = [
            "không đủ thông tin",
            "không tìm thấy",
            "không thể trả lời",
            "tài liệu không đề cập",
            "không có dữ liệu",
            "không có trong tài liệu",
            "tài liệu không cung cấp",
            "không được đề cập",
            "không nằm trong nội dung",
            "không có thông tin về",
            "chưa có đủ dữ liệu",
            "không nói về",
            "không nhắc đến",
            "document does not",
            "no information",
            "cannot answer",
        ]
        
        return any(pattern in answer_lower for pattern in fallback_patterns)
    
    def _safe_parse_json(self, raw: str, query_type: str = "DIRECT") -> dict:
        """Safe JSON parsing với comprehensive fallback và text reconstruction."""
        cleaned = raw.strip()
        
        # CRITICAL FIX: If LLM returns plain text instead of JSON, try to extract
        # Check if response looks like plain text (doesn't start with {)
        if not cleaned.startswith('{'):
            print(f"[RAG] ⚠️ LLM returned plain text, not JSON. Attempting recovery...")
            print(f"[RAG] Raw text (first 200 chars): {cleaned[:200]}")
            
            # ENHANCED: Try multiple JSON extraction methods
            methods = [
                # Method 1: Find first { to last }
                lambda s: re.search(r'\{.*\}', s, re.DOTALL),
                # Method 2: Find ```json blocks
                lambda s: re.search(r'```json\s*(\{.*?\})\s*```', s, re.DOTALL),
                # Method 3: Find after "answer":" pattern
                lambda s: re.search(r'"answer"\s*:\s*".*?".*?\}', s, re.DOTALL),
            ]
            
            for method in methods:
                match = method(cleaned)
                if match:
                    try:
                        json_str = match.group(1) if match.lastindex else match.group(0)
                        parsed = json.loads(json_str)
                        print(f"[RAG] ✅ Extracted JSON using method")
                        return parsed
                    except Exception as e:
                        print(f"[RAG] Method failed: {e}")
                        continue
            
            # Method 4: Reconstruct JSON from text
            print(f"[RAG] Attempting text-to-JSON reconstruction...")
            return self._reconstruct_json_from_text(cleaned, query_type)
        
        # Remove markdown blocks
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```json?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            cleaned = cleaned.strip()
        
        # Try direct parse
        try:
            parsed = json.loads(cleaned)
            # NEW: Validate SECTION_OVERVIEW responses
            if parsed.get("answer_type") == "SECTION_OVERVIEW":
                answer = parsed.get("answer", "")
                has_title = bool(re.search(r'PHẦN\s+\d+:', answer))
                has_list_intro = "Nội dung chính bao gồm" in answer or "bao gồm:" in answer
                topic_count = len(re.findall(r'\d+\.\s+\*\*', answer))
                
                if not has_title or not has_list_intro or topic_count < 3:
                    print(f"[RAG] ⚠️ SECTION_OVERVIEW format invalid:")
                    print(f"  - Has title: {has_title}")
                    print(f"  - Has list intro: {has_list_intro}")
                    print(f"  - Topic count: {topic_count}")
                    # Don't fail, but log warning
            return parsed
        except json.JSONDecodeError as e:
            print(f"[RAG] JSON decode error: {e}")
            pass
        
        # Try to extract JSON object
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception as e:
                print(f"[RAG] Extracted JSON parse failed: {e}")
                pass
        
        # Final fallback: reconstruct from text
        print(f"[RAG] All parsing attempts failed. Attempting reconstruction...")
        return self._reconstruct_json_from_text(cleaned, query_type)
    
    def _reconstruct_json_from_text(self, text: str, query_type: str) -> dict:
        """Reconstruct JSON from plain text answer (fallback)."""
        
        # Extract chunks mentioned in text
        chunk_pattern = r'\[Chunk\s+(\d+)\]|chunk\s+(\d+)'
        chunks_found = []
        for match in re.finditer(chunk_pattern, text, re.IGNORECASE):
            chunk_num = match.group(1) or match.group(2)
            if chunk_num:
                chunks_found.append(int(chunk_num))
        chunks_found = list(set(chunks_found))  # Deduplicate
        
        # Determine answer type from content
        text_lower = text.lower()
        answer_type = "FALLBACK"
        confidence = 0.0
        
        if query_type == "SECTION_OVERVIEW" or any(marker in text_lower for marker in ['phần', 'nội dung chính', 'bao gồm']):
            answer_type = "SECTION_OVERVIEW"
            confidence = 0.75 if chunks_found else 0.5
        elif query_type == "CODE_ANALYSIS" and "phân tích" in text_lower:
            answer_type = "CODE_ANALYSIS"
            confidence = 0.7
        elif query_type == "MULTI_CONCEPT_REASONING":
            answer_type = "MULTI_CONCEPT_REASONING"
            confidence = 0.65
        elif query_type == "EXERCISE_GENERATION" and ("bài tập" in text_lower or "function" in text_lower):
            answer_type = "EXERCISE_GENERATION"
            confidence = 0.7
        elif chunks_found:
            answer_type = "DIRECT"
            confidence = 0.6
        
        # Extract main answer (first 1000 chars or until double newline)
        answer_match = re.search(r'^(.+?)(?:\n\n|$)', text, re.DOTALL)
        answer = answer_match.group(1) if answer_match else text[:1000]
        answer = answer.strip()
        
        print(f"[RAG] Reconstructed JSON: answer_type={answer_type}, confidence={confidence:.2f}, chunks={len(chunks_found)}")
        
        return {
            "answer": answer,
            "answer_type": answer_type,
            "chunks_used": chunks_found[:10] if chunks_found else [],
            "confidence": confidence,
            "sentence_mapping": [],
            "sources": {
                "from_document": bool(chunks_found),
                "from_external_knowledge": False
            },
            "_reconstructed": True  # Flag for debugging
        }
    
    def _get_fallback_response(self) -> tuple:
        """Safe fallback response."""
        return (
            "Hiện tại không thể trả lời câu hỏi này. Vui lòng thử lại.",
            [],
            "FALLBACK",
            0.0,
            []
        )



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

        # Handle các câu chào / small-talk không liên quan đến tài liệu
        normalized_question = question.strip().lower()
        small_talk_phrases = [
            "hi",
            "hello",
            "xin chào",
            "chào",
            "chao",
            "chào bạn",
            "chào ad",
            "chào admin",
            "good morning",
            "good afternoon",
            "good evening",
            "bye",
            "tạm biệt",
            "cảm ơn",
            "thank you",
        ]

        # Nếu câu hỏi rất ngắn và chỉ là lời chào / cảm ơn thì không gọi RAG
        if len(normalized_question) <= 40 and any(
            normalized_question == p or normalized_question.startswith(p + " ")
            for p in small_talk_phrases
        ):
            # Trả lời thân thiện, không trích dẫn tài liệu
            if any(
                kw in normalized_question
                for kw in ["cảm ơn", "cam on", "thank", "tks", "thanks"]
            ):
                answer = (
                    "Cảm ơn bạn! Nếu cần mình hỗ trợ giải bài hoặc tóm tắt nội dung trong tài liệu, "
                    "hãy gửi câu hỏi nhé."
                )
            elif any(
                kw in normalized_question
                for kw in ["bye", "tạm biệt", "tam biet", "good night"]
            ):
                answer = (
                    "Tạm biệt bạn, hẹn gặp lại! Khi nào cần hỏi bài hoặc tra cứu tài liệu, cứ quay lại nhé."
                )
            else:
                answer = (
                    "Xin chào! Mình là trợ lý StudyQnA, mình sẽ giúp bạn trả lời các câu hỏi dựa trên tài liệu "
                    "bạn đã tải lên. Bạn cứ gửi câu hỏi về nội dung cần học nhé."
                )

            # Lưu lịch sử nhưng không có references
            history_record = await create_history(
                db, user_id, question, answer, [], document_id, conversation_id
            )

            final_conversation_id = conversation_id

            # Giữ logic conversation_id tương tự nhánh bình thường
            if not final_conversation_id:
                final_conversation_id = history_record.id
                try:
                    from bson import ObjectId

                    await db["histories"].update_one(
                        {"_id": ObjectId(history_record.id)},
                        {"$set": {"conversation_id": history_record.id}},
                    )
                    history_record.conversation_id = history_record.id
                except Exception as e:
                    print(
                        f"[RAG] Warning: Failed to update conversation_id for small-talk history {history_record.id}: {e}"
                    )

            return {
                "answer": answer,
                "references": [],
                "documents": [],
                "conversation_id": final_conversation_id,
                "history_id": history_record.id,
            }

        question_embeddings = await self.embedding_service.embed_texts([question])

        if not question_embeddings:
            # ENHANCED: Detect query type even for error cases
            query_type = detect_query_type_fast(question)
            return {
                "answer": "Không thể tạo embedding cho câu hỏi.",
                "references": [],
                "documents": [],
                "metadata": {
                    "answer_type": "FALLBACK",
                    "confidence": 0.0,
                    "query_type": query_type,
                    "chunks_selected": 0,
                    "chunks_used": 0,
                }
            }

        # ENHANCED: Detect query type FIRST để điều chỉnh search
        query_type = detect_query_type_fast(question)
        print(f"[RAG] Detected query type: {query_type}")

        query_vector = np.array(question_embeddings, dtype="float32")

        results = []

        # ENHANCED: Dynamic max_chunks
        max_chunks_for_query = self._determine_max_chunks_for_query(question, query_type)
        print(f"[RAG] Max chunks for this query: {max_chunks_for_query}")

        # Search with larger initial top_k for more candidates
        for doc in documents:

            namespace = doc.faiss_namespace or f"user_{doc.user_id}_doc_{doc.id}"

            index = load_faiss_index(namespace)

            if index is None or index.ntotal == 0:

                continue

            if index.d != query_vector.shape[1]:

                continue

            try:

                # ENHANCED: Tăng search_k cho reasoning queries
                if query_type in ["MULTI_CONCEPT_REASONING", "COMPARE_SYNTHESIZE", "CODE_ANALYSIS"]:
                    search_k = min(50, index.ntotal)  # Increased from 30
                else:
                    search_k = min(30, index.ntotal)

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
            # ENHANCED: Detect query type even for error cases
            query_type = detect_query_type_fast(question)
            
            # Nếu người dùng đã chọn 1 tài liệu cụ thể mà không tìm được đoạn văn nào
            # thì trả lời rõ ràng là câu hỏi không nằm trong nội dung tài liệu đó
            if document_id:
                answer = (
                    "Câu hỏi này không nằm trong nội dung của tài liệu bạn đã chọn. "
                    'Bạn có thể thử lại với chế độ "Tất cả tài liệu" hoặc chọn một tài liệu khác phù hợp hơn.'
                )
            else:
                answer = "Không tìm thấy đoạn văn phù hợp trong tài liệu của bạn."

            return {
                "answer": answer,
                "references": [],
                "documents": [doc.id for doc in documents],
                "metadata": {
                    "answer_type": "FALLBACK",
                    "confidence": 0.0,
                    "query_type": query_type,
                    "chunks_selected": 0,
                    "chunks_used": 0,
                }
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



            # CRITICAL FIX: Boost main sections (PHẦN, CHƯƠNG) for section questions
            is_main_section = False
            section_boost = 0.0
            
            # Check if this is a main section (PHẦN X, CHƯƠNG X)
            if chunk_doc:
                chunk_metadata = chunk_doc.get("metadata", {}) or {}
                section = chunk_metadata.get("section") or chunk_metadata.get("heading") or ""
                section_lower = section.lower() if section else ""
                
                # Main section patterns
                main_section_patterns = [
                    r'^phần\s+\d+',  # PHẦN 5
                    r'^chương\s+\d+',  # CHƯƠNG 3
                    r'^phần\s+[ivx]+',  # PHẦN V
                ]
                
                for pattern in main_section_patterns:
                    if re.match(pattern, section_lower):
                        is_main_section = True
                        section_boost = 0.5  # Strong boost for main sections
                        print(f"[RAG] Main section detected: {section} (chunk {record.get('chunk_index')})")
                        break
            
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



            # Apply boosts (combine keyword boost + section boost)
            total_boost = 0.0
            boost_details = []
            
            if keyword_matches > 0:
                keyword_boost = min(0.3, keyword_matches * 0.08)
                total_boost += keyword_boost
                item["keyword_matches"] = keyword_matches
                boost_details.append(f"keywords({keyword_matches})")
            
            # CRITICAL FIX: Add section boost for main sections
            if is_main_section:
                total_boost += section_boost
                boost_details.append("main_section")
            
            # CRITICAL FIX: Boost chunks chứa MỤC LỤC hoặc headings chính
            # Pattern 1: Boost chunks chứa "MỤC LỤC"
            if "mục lục" in content_lower or "table of contents" in content_lower:
                toc_boost = 0.8
                total_boost += toc_boost
                boost_details.append("table_of_contents")
                print(f"[RAG] Boosted chunk {record.get('chunk_index')} - contains TABLE OF CONTENTS")
            
            # Pattern 2: Boost chunks chứa nhiều PHẦN X
            # Đếm số lượng "PHẦN X" trong content
            section_count = len(re.findall(r'PHẦN\s+\d+', content, re.IGNORECASE))
            if section_count >= 3:  # Nếu có từ 3 PHẦN trở lên → đây là chunk overview
                overview_boost = min(0.6, section_count * 0.15)
                total_boost += overview_boost
                boost_details.append(f"overview({section_count}_sections)")
                print(f"[RAG] Boosted chunk {record.get('chunk_index')} - contains {section_count} section headings")
            
            if total_boost > 0:
                item["similarity"] = min(1.0, item["similarity"] + total_boost)
                print(f"[RAG] Boosted chunk {record.get('chunk_index', '?')} by {total_boost:.3f} ({', '.join(boost_details)})")



        # Sort by boosted similarity

        sorted_results = sorted(results, key=lambda r: r["similarity"], reverse=True)



        # ENHANCED: Smart chunk selection based on query type
        selected_results = []
        priority_chunks = []
        regular_chunks = []

        # For reasoning queries, also prioritize chunks with related concepts
        if query_type in ["MULTI_CONCEPT_REASONING", "CODE_ANALYSIS", "COMPARE_SYNTHESIZE"]:
            concept_keywords = [
                "hoisting", "scope", "closure", "function", "arrow", "class",
                "object", "array", "loop", "for", "while", "if", "variable",
                "const", "let", "var", "promise", "async", "callback"
            ]
            
            for item in sorted_results:
                content_lower = (item.get("_content", "") or "").lower()
                has_concept = any(kw in content_lower for kw in concept_keywords)
                
                # Check section match
                has_section_match = False
                if any(kw in ["phần", "chương", "part"] for kw in question_keywords):
                    question_numbers = re.findall(r'\d+', question_lower)
                    for num in question_numbers:
                        if (f"phần {num}" in content_lower or 
                            f"chương {num}" in content_lower):
                            has_section_match = True
                            break
                
                if has_section_match or (has_concept and item["similarity"] > 0.4):
                    priority_chunks.append(item)
                else:
                    regular_chunks.append(item)
        else:
            # Original logic for other query types
            for item in sorted_results:
                content_lower = (item.get("_content", "") or "").lower()
                has_section_match = False
                
                if any(kw in ["phần", "chương", "part"] for kw in question_keywords):
                    question_numbers = re.findall(r'\d+', question_lower)
                    for num in question_numbers:
                        if (f"phần {num}" in content_lower or 
                            f"chương {num}" in content_lower or
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

        # ENHANCED: Use dynamic max_chunks based on query type
        max_selected_chunks = max_chunks_for_query

        for item in all_chunks_ordered:

            content = item.get("_content", "")

            content_length = len(content) if content else 0

            # CRITICAL FIX: Check cả context length VÀ số chunks
            if (current_context_length + content_length + 500 > self.max_context_length) or \
               (len(selected_results) >= max_selected_chunks):
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



        # Add similarity to chunk metadata
        for item in selected_results:
            record = item.get("_record")
            if record:
                chunk_idx = record.get("chunk_index")
                for chunk_meta in chunk_metadata_for_context:
                    if chunk_meta.get("chunk_index") == chunk_idx:
                        chunk_meta["similarity"] = item.get("similarity", 0.5)
                        break
        
        # ENHANCED: Generate answer with query_type passed to prompt builder
        answer, chunks_actually_used, answer_type, confidence, sentence_mapping = \
            await self._generate_answer_with_tracking(
                question, 
                chunk_metadata_for_context,
                query_type  # Pass query type to generation
            )

        print(f"[RAG] LLM used {len(chunks_actually_used)} chunks in answer")
        print(f"[RAG] Chunks used: {chunks_actually_used}")
        print(f"[RAG] Answer type: {answer_type}, Confidence: {confidence:.2f}")



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
        
        # === CRITICAL: Reference Logic ===
        final_references = []
        
        if answer_type in ["FALLBACK", "TOO_BROAD"]:
            # STRICT RULE: FALLBACK/TOO_BROAD = 0 references
            final_references = []
            print(f"[RAG] ✓ {answer_type} detected → 0 references enforced")
            
        elif not chunks_actually_used:
            # No chunks but not fallback → suspicious
            if confidence > 0.5 and len(answer) > 100:
                # Try to infer from sentence mapping
                if sentence_mapping:
                    chunk_indices_from_mapping = [
                        s.get("chunk") for s in sentence_mapping 
                        if s.get("chunk") and not s.get("external", False)
                    ]
                    if chunk_indices_from_mapping:
                        print(f"[RAG] Recovered chunks from sentence_mapping: {chunk_indices_from_mapping}")
                        # Rebuild chunks_used
                        for idx in set(chunk_indices_from_mapping):
                            for item in selected_results:
                                record = item.get("_record")
                                if record and record.get("chunk_index") == idx:
                                    chunks_actually_used.append({
                                        "chunk_index": idx,
                                        "document_id": record.get("document_id")
                                    })
                                    break
                
                # If still no chunks, suspicious → no refs
                if not chunks_actually_used:
                    print(f"[RAG] ⚠ High confidence but no chunks → suspicious, no refs")
                    final_references = []
            else:
                final_references = []
                print(f"[RAG] Low confidence + no chunks → no references")
        
        if chunks_actually_used:
            # Build references from chunks_used
            final_references = self._build_references_from_chunks(
                chunks_actually_used, selected_results, chunk_metadata_for_context
            )
            print(f"[RAG] ✓ Built {len(final_references)} references from chunks")
        
        # OLD LOGIC - REMOVED: If chunks_actually_used is empty, use top selected_results chunks
        # This is now handled above with strict fallback rules
        if False and not chunks_actually_used and selected_results:
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

        # OLD REFERENCE BUILDING CODE - Skip if we've already built references using new method
        # This old code manually builds references with detailed metadata extraction
        # We keep it as fallback but skip it when using the new _build_references_from_chunks method
        # Note: The new _build_references_from_chunks is called above, so this old code should rarely execute
        # Only execute if final_references is still empty (shouldn't happen with new logic)
        if not final_references and chunks_actually_used:
            # Old manual reference building code (kept for compatibility/fallback)
            # This should rarely execute since _build_references_from_chunks is called above
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



        # Filter references based on document_id
        filtered_refs = deduplicated_refs
        
        if document_id:
            # Only keep references from the specified document
            filtered_refs = [ref for ref in deduplicated_refs if ref.document_id == document_id]
            print(f"[RAG] Filtered references to document {document_id}: {len(filtered_refs)} references")
        else:
            # Ở chế độ "Tất cả tài liệu" thì giữ mọi tài liệu mà LLM đã sử dụng,
            # không lọc bớt theo chunks_by_document để có thể trích dẫn từ nhiều file khác nhau.
            if len(chunks_by_document) > 1:
                print(f"[RAG] Multiple documents used in answer, keeping references from all {len(chunks_by_document)} documents")
            elif len(chunks_by_document) == 1:
                print(f"[RAG] Single document used in answer, keeping all references")
        
        # Smart filtering: If there are multiple sections, prioritize the section(s) với nhiều chunk nhất.
        # Chỉ áp dụng khi tất cả references đều thuộc 1 tài liệu; nếu nhiều tài liệu thì giữ nguyên.
        # CRITICAL FIX: Skip filtering for DOCUMENT_OVERVIEW
        if (
            len(filtered_refs) > 2
            and chunks_actually_used
            and answer_type != "DOCUMENT_OVERVIEW"  # ← ADD THIS CHECK
            and len({ref.document_id for ref in filtered_refs if ref.document_id}) == 1
        ):
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

        # CRITICAL: For DOCUMENT_OVERVIEW, keep more references
        if answer_type == "DOCUMENT_OVERVIEW":
            final_references = filtered_refs[:10]  # Keep up to 10 refs instead of 5
        else:
            final_references = filtered_refs[:5]  # Limit to 5 references



        print(f"[RAG] Final references: {len(final_references)} chunks")

        print(f"[RAG] Reference details:")

        for ref in final_references:

            print(f"  - File: {ref.document_filename}, Page: {ref.page_number}, Section: {ref.section}, Chunk: {ref.chunk_index}")



        # === ENHANCED LOGGING ===
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "question": question[:100],
            "document_id": document_id,
            "query_type": detect_query_type_fast(question),
            "answer_type": answer_type,
            "confidence": confidence,
            "chunks_retrieved": len(results) if 'results' in locals() else 0,
            "chunks_selected": len(selected_results) if 'selected_results' in locals() else 0,
            "chunks_used": [c.get("chunk_index") for c in chunks_actually_used],
            "references_count": len(final_references),
            "answer_length": len(answer),
            "sentence_mapping_count": len(sentence_mapping),
            "max_similarity": max(
                [item.get("similarity", 0) for item in selected_results]
            ) if selected_results else 0
        }
        print(f"[RAG] Query Log: {json.dumps(log_entry, ensure_ascii=False)}")
        
        # Ensure conversation_id is set - use provided conversation_id or create new one
        # If conversation_id is provided, use it (for continuing existing conversation)
        # If not provided, we'll set it to history_id after creating the record
        final_conversation_id = conversation_id

        # Create history with conversation_id (may be None for new conversation)
        print(f"[RAG] ===== Creating history record =====")
        print(f"[RAG] Question: {question[:100]}...")
        print(f"[RAG] Answer: {answer[:100]}...")
        print(f"[RAG] Conversation ID: {final_conversation_id}")
        print(f"[RAG] Document ID: {document_id}")
        print(f"[RAG] References count: {len(final_references)}")
        
        history_record = await create_history(
            db, user_id, question, answer, final_references, document_id, final_conversation_id
        )
        
        print(f"[RAG] ✅ History record created - ID: {history_record.id}")
        print(f"[RAG] ===================================")

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
            "metadata": {
                "answer_type": answer_type,
                "confidence": confidence,
                "query_type": query_type,
                "chunks_selected": len(selected_results),
                "chunks_used": len(chunks_actually_used),
            }
        }



    async def _generate_answer_with_tracking(
        self, 
        question: str, 
        chunk_metadata_list: List[dict],
        query_type: str = "DIRECT"
    ) -> tuple[str, List[dict], str, float, List[dict]]:
        """
        Generate answer and track which chunks were actually used.
        Returns: (answer, chunks_used, answer_type, confidence, sentence_mapping)
        """
        # Build context với similarity scores
        context_parts = []
        chunk_similarities = []

        for chunk_meta in chunk_metadata_list:
            idx = chunk_meta["chunk_index"]
            content = chunk_meta["content"]
            sim = chunk_meta.get("similarity", 0.5)
            chunk_similarities.append(sim)
            
            # Compact marker format
            parts = [f"[Chunk {idx}]"]
            if chunk_meta.get("document_filename"):
                parts.append(f"[{chunk_meta['document_filename']}]")
            if chunk_meta.get("page_number"):
                parts.append(f"[Page {chunk_meta['page_number']}]")
            if chunk_meta.get("section"):
                parts.append(f"[{chunk_meta['section']}]")
            parts.append(f"[Sim:{sim:.2f}]")
            
            marker = " ".join(parts)
            context_parts.append(f"{marker}\n{content}")
        
        context_text = "\n\n---\n\n".join(context_parts)
        
        # ENHANCED: Build prompt with query_type
        prompt = build_gemini_optimized_prompt(
            question=question,
            context_text=context_text,
            chunk_similarities=chunk_similarities,
            query_type=query_type
        )
        
        # Call Gemini API
        # Note: Gemini API uses camelCase, not snake_case
        # Note: responseMimeType is not supported by Gemini 2.5 Flash, so we parse JSON from text
        # CRITICAL FIX: Tăng maxOutputTokens lên 8192 để tránh MAX_TOKENS error
        generation_config = {
            "temperature": 0.0,
            "maxOutputTokens": self.max_output_tokens,  # 12000 tokens for long answers
            "candidateCount": 1,
            "stopSequences": [],
        }
        
        try:
            url = f"{self._gemini_base_url}/{self.model}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": generation_config
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    params={"key": self._gemini_api_key},
                    json=payload
                )
                
                # Log error details if request fails
                if response.status_code != 200:
                    error_detail = response.text
                    print(f"[RAG] Gemini API error ({response.status_code}): {error_detail[:500]}")
                    try:
                        error_json = response.json()
                        print(f"[RAG] Error JSON: {json.dumps(error_json, ensure_ascii=False, indent=2)}")
                    except:
                        pass
                    raise Exception(f"Gemini API returned {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                # Safely extract text from response (similar to quiz_generator)
                raw = None
                
                if "candidates" not in data or len(data["candidates"]) == 0:
                    print(f"[RAG] No candidates in response. Full response: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")
                    raise Exception("No candidates in Gemini response")
                
                candidate = data["candidates"][0]
                
                # Try multiple ways to extract text (like quiz_generator)
                # Case 1: Standard structure: candidates[0].content.parts[0].text
                if "content" in candidate:
                    content = candidate["content"]
                    if isinstance(content, dict) and "parts" in content:
                        parts = content["parts"]
                        if isinstance(parts, list) and len(parts) > 0:
                            if isinstance(parts[0], dict) and "text" in parts[0]:
                                raw = parts[0]["text"]
                            elif isinstance(parts[0], str):
                                raw = parts[0]
                    
                    # Case 2: content might be a string directly
                    elif isinstance(content, str):
                        raw = content
                    
                    # Case 3: content might be a list
                    elif isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and "text" in first_item:
                            raw = first_item["text"]
                        elif isinstance(first_item, str):
                            raw = first_item
                
                # Case 4: Check candidate directly
                if not raw:
                    if "text" in candidate:
                        raw = candidate["text"]
                    elif isinstance(candidate, str):
                        raw = candidate
                
                # Case 5: Recursive search (fallback)
                if not raw:
                    def extract_text_recursive(obj, depth=0):
                        if depth > 5:  # Prevent infinite recursion
                            return None
                        if isinstance(obj, str) and len(obj) > 10:
                            return obj
                        if isinstance(obj, dict):
                            if "text" in obj:
                                return obj["text"]
                            for value in obj.values():
                                result = extract_text_recursive(value, depth + 1)
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = extract_text_recursive(item, depth + 1)
                                if result:
                                    return result
                        return None
                    
                    raw = extract_text_recursive(candidate)
                
                if not raw:
                    print(f"[RAG] ❌ Could not extract text from candidate")
                    print(f"[RAG] Full candidate structure: {json.dumps(candidate, indent=2, ensure_ascii=False)[:2000]}")
                    raise Exception("Could not extract text from Gemini response")
                
                print(f"[RAG] ✅ Extracted response: {len(raw)} chars")
                parsed = self._safe_parse_json(raw, query_type)
                
                answer = parsed.get("answer", "")
                answer_type = parsed.get("answer_type", "FALLBACK")
                chunk_indices = parsed.get("chunks_used", [])
                confidence = parsed.get("confidence", 0.0)
                sentence_mapping = parsed.get("sentence_mapping", [])
                sources = parsed.get("sources", {})
                reasoning_steps = parsed.get("reasoning_steps", [])
                
                # === VALIDATION LAYER ===
                
                # Rule 0: TOO_BROAD detection
                if answer_type == "TOO_BROAD":
                    chunk_indices = []
                    sentence_mapping = []
                    confidence = 0.0
                    print(f"[RAG] TOO_BROAD detected → enforcing 0 chunks")
                
                # ENHANCED: Validation for reasoning queries - More lenient
                if query_type in ["CODE_ANALYSIS", "EXERCISE_GENERATION", "MULTI_CONCEPT_REASONING"]:
                    # NEW: More lenient - only reject if VERY short or VERY low confidence
                    if len(answer) < 50:  # Only reject if VERY short
                        print(f"[RAG] Reasoning query but answer too short ({len(answer)} chars)")
                        answer_type = "FALLBACK"
                        chunk_indices = []
                        confidence = 0.0
                    elif confidence < 0.4:  # Lower threshold (from 0.5 to 0.4)
                        print(f"[RAG] Low confidence for reasoning query ({confidence:.2f})")
                        answer_type = "FALLBACK"
                        chunk_indices = []
                        confidence = 0.0
                    else:
                        # Accept even without reasoning_steps field if answer is substantial
                        if not reasoning_steps:
                            print(f"[RAG] Reasoning answer accepted despite missing reasoning_steps field (answer length: {len(answer)})")
                else:
                    # Original validation for non-reasoning queries
                    # CRITICAL FIX: Don't apply fallback detection for SECTION_OVERVIEW or DOCUMENT_OVERVIEW
                    if answer_type not in ["SECTION_OVERVIEW", "DOCUMENT_OVERVIEW"]:
                        # Rule 1: Fallback detection via keywords
                        if self._is_fallback_answer(answer):
                            answer_type = "FALLBACK"
                            chunk_indices = []
                            confidence = 0.0
                            sentence_mapping = []
                            print(f"[RAG] Fallback detected via keywords")
                        
                        # Rule 2: Low confidence → force fallback (unless TOO_BROAD)
                        if confidence < settings.rag_low_confidence_threshold and answer_type != "TOO_BROAD":
                            answer_type = "FALLBACK"
                            chunk_indices = []
                            sentence_mapping = []
                            print(f"[RAG] Low confidence ({confidence:.2f}) → forced fallback")
                    else:
                        # SECTION_OVERVIEW or DOCUMENT_OVERVIEW: Only fallback if EXPLICITLY no chunks
                        if not chunk_indices:
                            answer_type = "FALLBACK"
                            confidence = 0.0
                            sentence_mapping = []
                            print(f"[RAG] {answer_type} but no chunks → fallback")
                        else:
                            print(f"[RAG] {answer_type} with {len(chunk_indices)} chunks → keeping answer")
                
                # Rule 3: CRITICAL - Enforce fallback=0 refs (and TOO_BROAD)
                if answer_type in ["FALLBACK", "TOO_BROAD"]:
                    chunk_indices = []
                    sentence_mapping = []
                    confidence = 0.0
                    print(f"[RAG] {answer_type} type → enforcing 0 chunks")
                
                # Rule 4: No chunks but claims document source → suspicious (skip for overviews)
                if not chunk_indices and sources.get("from_document") and answer_type not in ["SECTION_OVERVIEW", "DOCUMENT_OVERVIEW"]:
                    answer_type = "FALLBACK"
                    confidence = 0.0
                    print(f"[RAG] Suspicious: no chunks but claims document source")
                
                # Rule 5: Check sentence_mapping consistency (skip for overviews)
                if sentence_mapping and answer_type not in ["SECTION_OVERVIEW", "DOCUMENT_OVERVIEW"]:
                    external_count = sum(1 for s in sentence_mapping if s.get("external", False))
                    total_count = len(sentence_mapping)
                    if total_count > 0 and external_count / total_count > 0.5:
                        answer_type = "FALLBACK"
                        chunk_indices = []
                        sentence_mapping = []
                        print(f"[RAG] >50% external sentences → forced fallback")
                
                # Map to full chunk info
                chunks_used = []
                for idx in chunk_indices:
                    for meta in chunk_metadata_list:
                        if meta.get("chunk_index") == idx:
                            chunks_used.append({
                                "chunk_index": idx,
                                "document_id": meta.get("document_id")
                            })
                            break
                
                print(f"[RAG] Answer type: {answer_type}, Confidence: {confidence:.2f}")
                print(f"[RAG] Chunks: {chunk_indices}, Sentences mapped: {len(sentence_mapping)}")
                
                return answer, chunks_used, answer_type, confidence, sentence_mapping
                
        except Exception as e:
            print(f"[RAG] Error calling Gemini API: {e}")
            import traceback
            print(f"[RAG] Traceback: {traceback.format_exc()}")
            return self._get_fallback_response()

        # Fallback for OpenAI or other providers
        if self.provider == "openai" and self._openai_client:
            try:
                # For OpenAI, use similar approach but with different format
                messages = [
                    {
                        "role": "system",
                        "content": "You are a professional study assistant. Answer questions based on context. Always return JSON format with answer, answer_type, chunks_used, confidence, sentence_mapping, and sources fields.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ]

                response = await asyncio.to_thread(
                    self._openai_client.chat.completions.create,
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content
                parsed = self._safe_parse_json(raw)
                
                answer = parsed.get("answer", "")
                answer_type = parsed.get("answer_type", "FALLBACK")
                chunk_indices = parsed.get("chunks_used", [])
                confidence = parsed.get("confidence", 0.0)
                sentence_mapping = parsed.get("sentence_mapping", [])
                
                # Apply same validation rules
                if self._is_fallback_answer(answer):
                    answer_type = "FALLBACK"
                    chunk_indices = []
                    confidence = 0.0
                    sentence_mapping = []
                
                if confidence < settings.rag_low_confidence_threshold:
                    answer_type = "FALLBACK"
                    chunk_indices = []
                    sentence_mapping = []
                
                if answer_type == "FALLBACK":
                    chunk_indices = []
                    sentence_mapping = []
                    confidence = 0.0
                
                chunks_used = []
                for idx in chunk_indices:
                    for meta in chunk_metadata_list:
                        if meta.get("chunk_index") == idx:
                            chunks_used.append({
                                "chunk_index": idx,
                                "document_id": meta.get("document_id")
                            })
                            break
                
                return answer, chunks_used, answer_type, confidence, sentence_mapping
            except Exception as e:
                print(f"[RAG] OpenAI API call failed: {e}")
                return self._get_fallback_response()
        
        return self._get_fallback_response()



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





    def _build_references_from_chunks(
        self,
        chunks_used: List[dict],
        selected_results: List[dict],
        chunk_metadata_for_context: List[dict]
    ) -> List[HistoryReference]:
        """Build references from chunks actually used."""
        final_references = []
        
        for chunk_info in chunks_used:
            chunk_idx = chunk_info.get("chunk_index")
            doc_id = chunk_info.get("document_id")
            
            # Find in selected_results
            for item in selected_results:
                record = item.get("_record")
                if not record:
                    continue
                
                if record.get("chunk_index") == chunk_idx and \
                   record.get("document_id") == doc_id:
                    
                    doc = item["document"]
                    chunk_doc = item.get("_chunk_doc")
                    content = item.get("_content", "")
                    
                    # Get metadata
                    chunk_metadata = {}
                    if chunk_doc:
                        chunk_metadata = chunk_doc.get("metadata", {}) or {}
                    elif record:
                        chunk_metadata = record.get("metadata", {}) or {}
                    
                    page = chunk_metadata.get("page_number")
                    section = chunk_metadata.get("section")
                    heading = chunk_metadata.get("heading")
                    
                    preview = content[:160] if content else None
                    
                    final_references.append(
                        HistoryReference(
                            document_id=doc.id,
                            document_filename=doc.filename,
                            document_file_type=doc.file_type,
                            chunk_id=str(chunk_doc.get("_id")) if chunk_doc else None,
                            chunk_index=chunk_idx,
                            page_number=page,
                            section=section or heading,
                            score=item.get("similarity", 0.5),
                            content_preview=preview,
                        )
                    )
                    break
        
        # Deduplicate
        seen = set()
        deduplicated = []
        for ref in final_references:
            key = f"{ref.document_id}_{ref.chunk_index}"
            if key not in seen:
                seen.add(key)
                deduplicated.append(ref)
        
        # CRITICAL FIX: Adjust max references based on question complexity
        # Count how many chunks were actually used
        num_chunks_used = len(chunks_used)
        
        if num_chunks_used >= 5:  # Complex question - keep more refs
            max_refs = min(5, num_chunks_used)
        elif num_chunks_used >= 3:  # Medium complexity
            max_refs = min(4, num_chunks_used)
        else:  # Simple question
            max_refs = min(2, num_chunks_used)
        
        return deduplicated[:max_refs]


rag_service = RAGService()
