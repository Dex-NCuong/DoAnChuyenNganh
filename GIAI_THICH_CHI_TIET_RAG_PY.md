# GIẢI THÍCH CHI TIẾT FILE RAG.PY

File này giải thích chi tiết tất cả các hàm và code trong `backend/app/services/rag.py` - file xử lý RAG (Retrieval-Augmented Generation) chính của dự án StudyQnA.

---

## MỤC LỤC

1. [Các hàm độc lập (Standalone Functions)](#1-các-hàm-độc-lập-standalone-functions)
2. [Class RAGService](#2-class-ragservice)
   - [2.1. Hàm khởi tạo (__init__)](#21-hàm-khởi-tạo-__init__)
   - [2.2. Các phương thức xử lý query](#22-các-phương-thức-xử-lý-query)
   - [2.3. Các phương thức xử lý text](#23-các-phương-thức-xử-lý-text)
   - [2.4. Các phương thức xử lý JSON](#24-các-phương-thức-xử-lý-json)
   - [2.5. Các phương thức chính (ask, _generate_answer_with_tracking)](#25-các-phương-thức-chính)

---

## 1. CÁC HÀM ĐỘC LẬP (Standalone Functions)

### 1.1. `detect_query_type_fast(question: str) -> str`

**Tên tiếng Việt:** Phát hiện loại câu hỏi nhanh

**Mục đích:** Phân loại câu hỏi của người dùng thành các loại khác nhau để xử lý phù hợp.

**Tham số:**
- `question: str` - Câu hỏi của người dùng (chuỗi ký tự)

**Giá trị trả về:**
- `str` - Loại câu hỏi được phát hiện (ví dụ: "SECTION_OVERVIEW", "DOCUMENT_OVERVIEW", "DIRECT", ...)

**Logic chính:**
1. Chuyển câu hỏi về chữ thường để dễ so khớp
2. Kiểm tra theo thứ tự ưu tiên:
   - **PRIORITY 1: SECTION_OVERVIEW** - Nếu câu hỏi có đề cập đến "PHẦN X", "Chương X" → trả về "SECTION_OVERVIEW"
   - **PRIORITY 2: DOCUMENT_OVERVIEW** - Nếu câu hỏi hỏi về "bao nhiêu phần", "mục lục", "tổng quan" → trả về "DOCUMENT_OVERVIEW"
   - **PRIORITY 3: COMPARE_SYNTHESIZE** - Nếu có từ "so sánh", "khác gì" → trả về "COMPARE_SYNTHESIZE"
   - **PRIORITY 4: CODE_ANALYSIS** - Nếu có "phân tích code", "sửa lỗi" → trả về "CODE_ANALYSIS"
   - **PRIORITY 5: EXERCISE_GENERATION** - Nếu có "tạo bài tập", "viết function" → trả về "EXERCISE_GENERATION"
   - **PRIORITY 6: MULTI_CONCEPT_REASONING** - Nếu có "dựa trên... và..." → trả về "MULTI_CONCEPT_REASONING"
   - **PRIORITY 7: EXPAND** - Nếu có "liệt kê", "giải thích" → trả về "EXPAND"
   - **PRIORITY 8: EXISTENCE** - Nếu có "có đề cập" → trả về "EXISTENCE"
   - **Mặc định: DIRECT** - Câu hỏi đơn giản, trả lời trực tiếp

**Ví dụ:**
```python
detect_query_type_fast("PHẦN 8 nói gì?")  # → "SECTION_OVERVIEW"
detect_query_type_fast("Tài liệu có bao nhiêu phần?")  # → "DOCUMENT_OVERVIEW"
detect_query_type_fast("So sánh var và let")  # → "COMPARE_SYNTHESIZE"
detect_query_type_fast("Closure là gì?")  # → "DIRECT"
```

**Vị trí trong code:** Dòng 30-135

---

### 1.2. `build_gemini_optimized_prompt(...) -> str`

**Tên tiếng Việt:** Xây dựng prompt tối ưu cho Gemini

**Mục đích:** Tạo prompt (hướng dẫn) chi tiết cho LLM (Gemini) dựa trên loại câu hỏi và ngữ cảnh đã chọn.

**Tham số:**
- `question: str` - Câu hỏi của người dùng
- `context_text: str` - Ngữ cảnh (các chunk đã chọn, có format `[Chunk X] [Filename] [Page Y] [Section Z] [Sim:0.XX]`)
- `chunk_similarities: List[float]` - Danh sách độ tương đồng của các chunk
- `query_type: str = "DIRECT"` - Loại câu hỏi (mặc định là "DIRECT")
- `selected_documents: Optional[List[Dict[str, str]]] = None` - Danh sách tài liệu được chọn (tùy chọn)

**Giá trị trả về:**
- `str` - Prompt đầy đủ để gửi cho LLM

**Logic chính:**
1. **Phát hiện loại câu hỏi chi tiết:** Kiểm tra lại query_type và các pattern đặc biệt (như SECTION_OVERVIEW)
2. **Kiểm tra ngưỡng độ tương đồng:**
   - DOCUMENT_OVERVIEW: threshold = 0.25 (25%)
   - Các loại khác: threshold = 0.4 (40%)
   - Nếu max_similarity < threshold → thêm cảnh báo FALLBACK
3. **Xây dựng hướng dẫn theo loại câu hỏi (mode_instructions):**
   - **DOCUMENT_OVERVIEW:** Hướng dẫn quét toàn bộ tài liệu, tìm tất cả các phần, sử dụng mục lục
   - **SECTION_OVERVIEW:** Hướng dẫn tìm nội dung của phần cụ thể, liệt kê chi tiết
   - **CODE_ANALYSIS:** Hướng dẫn phân tích code dựa trên khái niệm từ tài liệu
   - **EXERCISE_GENERATION:** Hướng dẫn tạo bài tập mới dựa trên khái niệm
   - **MULTI_CONCEPT_REASONING:** Hướng dẫn kết hợp nhiều khái niệm để lý luận
   - **COMPARE_SYNTHESIZE:** Hướng dẫn so sánh và tổng hợp, trả về dạng bảng
   - **DIRECT:** Hướng dẫn trả lời trực tiếp từ tài liệu
   - **EXPAND:** Hướng dẫn liệt kê hoặc giải thích chi tiết
   - **EXISTENCE:** Hướng dẫn kiểm tra xem có đề cập hay không
4. **Xử lý đa tài liệu:** Nếu có nhiều tài liệu, thêm hướng dẫn trích dẫn rõ ràng từ tài liệu nào
5. **Định dạng output:** Yêu cầu LLM trả về JSON với các trường: `answer`, `answer_type`, `chunks_used`, `confidence`, `sentence_mapping`, `sources`
6. **Ghép tất cả thành prompt hoàn chỉnh:** System rules + Mode instructions + Multi-doc instructions + Context chunks + Question

**Ví dụ prompt được tạo:**
```
# SYSTEM RULES
## 📚 DOCUMENT OVERVIEW MODE
User is asking for a complete overview...
[Chunk 1] [file.pdf] [Page 1] [PHẦN 1] [Sim:0.85]
Nội dung chunk 1...

[Chunk 2] [file.pdf] [Page 2] [PHẦN 2] [Sim:0.82]
Nội dung chunk 2...

## QUESTION
Tài liệu có bao nhiêu phần?
```

**Vị trí trong code:** Dòng 138-896

---

## 2. CLASS RAGService

Class chính xử lý toàn bộ quy trình RAG, từ nhận câu hỏi đến trả về câu trả lời.

### 2.1. Hàm khởi tạo (__init__)

**Tên tiếng Việt:** Khởi tạo dịch vụ RAG

**Mục đích:** Thiết lập các cấu hình và khởi tạo các client API (OpenAI, Gemini).

**Logic chính:**
1. **Khởi tạo EmbeddingService:** Dịch vụ tạo vector embedding cho văn bản
2. **Cấu hình LLM:**
   - `self.provider`: Nhà cung cấp LLM (gemini hoặc openai)
   - `self.model`: Tên model (ví dụ: "gemini-2.5-flash")
   - `self.max_tokens`: Số token tối đa (từ config, nhưng không dùng cho Gemini)
   - `self.max_context_length`: Độ dài ngữ cảnh tối đa = min(12000, 20000) = 12000 ký tự
   - `self.max_output_tokens`: Token đầu ra tối đa = 12000 (cho Gemini)
3. **Khởi tạo OpenAI client (nếu cần):**
   - Nếu provider = "openai" và có API key → tạo OpenAI client
   - Nếu lỗi → fallback về "local"
4. **Khởi tạo Gemini (nếu cần):**
   - Nếu provider = "gemini" và có API key → lưu API key
   - Nếu không có API key → fallback về "local"
5. **Fallback:** Nếu không khởi tạo được client nào → provider = "local"

**Vị trí trong code:** Dòng 904-975

---

### 2.2. Các phương thức xử lý query

#### 2.2.1. `_determine_max_chunks_for_query(question: str, query_type: str, num_docs: int = 1) -> int`

**Tên tiếng Việt:** Xác định số chunk tối đa cho câu hỏi

**Mục đích:** Tính toán số lượng chunk tối đa cần lấy từ vector database dựa trên độ phức tạp của câu hỏi và số lượng tài liệu.

**Tham số:**
- `question: str` - Câu hỏi của người dùng
- `query_type: str` - Loại câu hỏi (SECTION_OVERVIEW, DOCUMENT_OVERVIEW, ...)
- `num_docs: int = 1` - Số lượng tài liệu được chọn (mặc định 1)

**Giá trị trả về:**
- `int` - Số chunk tối đa cần lấy

**Logic chính:**
1. **Tính hệ số nhân (multiplier) dựa trên số tài liệu:**
   - 1 file: multiplier = 1.0x
   - 2 files: multiplier = 1.5x
   - 3+ files: multiplier = 2.0x
2. **Xác định base chunks theo query_type:**
   - **DOCUMENT_OVERVIEW:** base = 150 chunks (cần nhiều nhất để quét toàn bộ)
   - **SECTION_OVERVIEW:** base = 45 chunks
   - **MULTI_CONCEPT_REASONING/CODE_ANALYSIS/EXERCISE_GENERATION:**
     - Nếu có ≥3 concepts: base = 30 chunks
     - Nếu có 2 concepts: base = 25 chunks
     - Nếu có 1 concept: base = 20 chunks
   - **COMPARE_SYNTHESIZE:**
     - Nếu so sánh 2+ items: base = 35 chunks
     - Nếu không: base = 30 chunks
   - **EXPAND:** base = 20 chunks
   - **DIRECT:** base = 15 chunks (ít nhất)
3. **Trả về:** base * multiplier

**Ví dụ:**
```python
# DOCUMENT_OVERVIEW với 2 files
_determine_max_chunks_for_query("Có bao nhiêu phần?", "DOCUMENT_OVERVIEW", 2)
# → 150 * 1.5 = 225 chunks

# DIRECT với 1 file
_determine_max_chunks_for_query("Closure là gì?", "DIRECT", 1)
# → 15 * 1.0 = 15 chunks
```

**Vị trí trong code:** Dòng 977-1034

---

#### 2.2.2. `_extract_section_from_content(content: str, file_type: str) -> Optional[str]`

**Tên tiếng Việt:** Trích xuất phần/tiêu đề từ nội dung

**Mục đích:** Cố gắng tìm và trích xuất tiêu đề phần từ nội dung chunk nếu metadata không có.

**Tham số:**
- `content: str` - Nội dung của chunk
- `file_type: str` - Loại file (docx, md, txt, pdf)

**Giá trị trả về:**
- `Optional[str]` - Tiêu đề phần nếu tìm thấy, None nếu không

**Logic chính:**
1. **Kiểm tra điều kiện:** Chỉ xử lý docx, md, txt (không xử lý PDF vì đã có metadata)
2. **Kiểm tra độ dài:** Nếu content > 150 ký tự → không phải heading → return None
3. **Pattern 1: Numbered sections** (Tiêu đề có số):
   - Regex: `^(\d+\.)+\s*\d+[\.\s]+(.+)$`
   - Ví dụ: "7.1.2. Section Name" → trả về toàn bộ content
4. **Pattern 2: Short lines** (Dòng ngắn có thể là heading):
   - Độ dài < 80 ký tự
   - Không kết thúc bằng dấu chấm
   - Có dấu hai chấm `:` HOẶC viết hoa toàn bộ HOẶC có ≤ 10 từ
   - → Trả về content
5. **Pattern 3: Markdown headings** (Tiêu đề markdown):
   - Bắt đầu bằng `#` → loại bỏ `#` và trả về phần còn lại
6. **Không tìm thấy:** return None

**Ví dụ:**
```python
_extract_section_from_content("7.1.2. Arrow Function", "txt")
# → "7.1.2. Arrow Function"

_extract_section_from_content("Closure:", "docx")
# → "Closure:"

_extract_section_from_content("Đây là một đoạn văn dài...", "txt")
# → None
```

**Vị trí trong code:** Dòng 1036-1070

---

#### 2.2.3. `_is_numbered_section(text: str) -> bool`

**Tên tiếng Việt:** Kiểm tra xem có phải tiêu đề phần có số không

**Mục đích:** Kiểm tra xem một đoạn văn bản có phải là tiêu đề dạng số (ví dụ: '7.2.2. Section Name') hay không.

**Tham số:**
- `text: str` - Đoạn văn bản cần kiểm tra

**Giá trị trả về:**
- `bool` - True nếu là tiêu đề có số, False nếu không

**Logic chính:**
1. Kiểm tra text có rỗng không
2. Sử dụng regex: `^(\d+\.)+\s*\d+[\.\s]+`
   - Bắt đầu bằng một hoặc nhiều số và dấu chấm (ví dụ: "7.2.")
   - Tiếp theo là số và dấu chấm hoặc khoảng trắng
3. Trả về True nếu khớp, False nếu không

**Ví dụ:**
```python
_is_numbered_section("7.2.2. Section Name")  # → True
_is_numbered_section("PHẦN 8: Title")  # → False
_is_numbered_section("Đây là đoạn văn bình thường")  # → False
```

**Vị trí trong code:** Dòng 1072-1079

---

### 2.3. Các phương thức xử lý text

#### 2.3.1. `_fix_numbered_list_formatting(text: str) -> str`

**Tên tiếng Việt:** Sửa định dạng danh sách có số

**Mục đích:** Sửa lỗi định dạng danh sách có số và bảng trong câu trả lời của LLM để đảm bảo hiển thị đúng trên frontend.

**Tham số:**
- `text: str` - Văn bản cần sửa

**Giá trị trả về:**
- `str` - Văn bản đã được sửa định dạng

**Logic chính:**
1. **Pattern 1: Sửa danh sách trên cùng một dòng:**
   - Tìm: "1. Item 1 2. Item 2"
   - Thay: "1. Item 1\n\n2. Item 2"
   - Loại trừ sub-numbering (ví dụ: "3.1. " không bị ảnh hưởng)
2. **Pattern 2: Sửa danh sách chỉ có 1 newline:**
   - Tìm: "1. Item 1\n2. Item 2"
   - Thay: "1. Item 1\n\n2. Item 2"
3. **Pattern 3: Sửa khoảng trắng trước số:**
   - Tìm: "... 2. Item"
   - Thay: "...\n\n2. Item"
4. **Pattern 4: Sửa bảng (table rows):**
   - Đảm bảo có newline giữa các hàng bảng
   - Tìm: "| col1 | col2 | | col3 | col4 |"
   - Thay: "| col1 | col2 |\n| col3 | col4 |"
5. **Dọn dẹp:**
   - Loại bỏ 3+ newlines liên tiếp (chỉ giữ 2)
   - Loại bỏ khoảng trắng trước newline
6. **Log số lượng items:** Ghi log số lượng mục đã tìm thấy

**Ví dụ:**
```python
_fix_numbered_list_formatting("1. Item 1 2. Item 2 3. Item 3")
# → "1. Item 1\n\n2. Item 2\n\n3. Item 3"

_fix_numbered_list_formatting("| A | B | | C | D |")
# → "| A | B |\n| C | D |"
```

**Vị trí trong code:** Dòng 1081-1139

---

#### 2.3.2. `_clean_table_citations(text: str) -> str`

**Tên tiếng Việt:** Làm sạch trích dẫn trong bảng

**Mục đích:** Loại bỏ các dòng "Nguồn tham khảo" và các trích dẫn chunk không mong muốn trong bảng so sánh.

**Tham số:**
- `text: str` - Văn bản chứa bảng cần làm sạch

**Giá trị trả về:**
- `str` - Văn bản đã loại bỏ trích dẫn

**Logic chính:**
1. **Kiểm tra:** Nếu không có ký tự `|` (không phải bảng) → trả về nguyên văn
2. **Loại bỏ dòng "Nguồn tham khảo":**
   - Tìm: "Nguồn tham khảo: ... chunk X, Y, Z"
   - Xóa toàn bộ dòng này
3. **Xử lý từng dòng:**
   - Phát hiện dòng bảng (có `|` nhưng không phải separator row)
   - **Trong ô bảng:** Loại bỏ:
     - "(từ filename.pdf, chunk X)"
     - "(từ chunk X)"
     - "chunk X" ở cuối ô
   - **Sau bảng (conclusion):** Cũng loại bỏ các trích dẫn tương tự
4. **Dọn dẹp:**
   - Loại bỏ khoảng trắng thừa
   - Loại bỏ 3+ newlines liên tiếp

**Ví dụ:**
```python
_clean_table_citations("| A | B (từ chunk 5) |\nNguồn tham khảo: chunk 1, 2")
# → "| A | B |"
```

**Vị trí trong code:** Dòng 1141-1207

---

#### 2.3.3. `_is_fallback_answer(answer: str) -> bool`

**Tên tiếng Việt:** Kiểm tra xem có phải câu trả lời dự phòng không

**Mục đích:** Phát hiện các câu trả lời "fallback" (không tìm thấy thông tin) dựa trên các từ khóa tiếng Việt.

**Tham số:**
- `answer: str` - Câu trả lời cần kiểm tra

**Giá trị trả về:**
- `bool` - True nếu là fallback answer, False nếu không

**Logic chính:**
1. **Kiểm tra độ dài:** Nếu answer rỗng hoặc < 20 ký tự → return True
2. **Chuyển về chữ thường:** Để so khớp dễ hơn
3. **Kiểm tra các pattern fallback:**
   - "không đủ thông tin"
   - "không tìm thấy"
   - "không thể trả lời"
   - "tài liệu không đề cập"
   - "không có dữ liệu"
   - "không có trong tài liệu"
   - "tài liệu không cung cấp"
   - "không được đề cập"
   - "không nằm trong nội dung"
   - "không có thông tin về"
   - "chưa có đủ dữ liệu"
   - "không nói về"
   - "không nhắc đến"
   - "document does not"
   - "no information"
   - "cannot answer"
4. **Trả về:** True nếu tìm thấy bất kỳ pattern nào, False nếu không

**Ví dụ:**
```python
_is_fallback_answer("Không tìm thấy thông tin trong tài liệu")  # → True
_is_fallback_answer("Closure là một khái niệm...")  # → False
```

**Vị trí trong code:** Dòng 1209-1234

---

### 2.4. Các phương thức xử lý JSON

#### 2.4.1. `_safe_parse_json(raw: str, query_type: str = "DIRECT") -> dict`

**Tên tiếng Việt:** Parse JSON an toàn

**Mục đích:** Xử lý việc parse JSON từ phản hồi của LLM một cách an toàn, bao gồm việc trích xuất JSON từ các khối markdown, sửa lỗi JSON phổ biến, và tự động điều chỉnh answer_type nếu LLM trả về không chính xác.

**Tham số:**
- `raw: str` - Văn bản thô từ LLM (có thể chứa JSON hoặc markdown)
- `query_type: str = "DIRECT"` - Loại câu hỏi (để điều chỉnh answer_type nếu cần)

**Giá trị trả về:**
- `dict` - Dictionary chứa các trường: `answer`, `answer_type`, `chunks_used`, `confidence`, `sentence_mapping`, `sources`

**Logic chính:**
1. **Trích xuất JSON từ markdown blocks:**
   - Tìm pattern: ` ```json ... ``` ` hoặc ` ``` ... ``` `
   - Trích xuất nội dung bên trong
2. **Thử parse JSON:**
   - Dùng `json.loads()` để parse
   - Nếu thành công → trả về kết quả
3. **Nếu parse thất bại, thử các cách khác:**
   - **Cách 1:** Trích xuất JSON có multiline string (dùng `_extract_json_with_multiline_string`)
   - **Cách 2:** Sửa JSON có bảng (dùng `_fix_json_with_table`)
   - **Cách 3:** Tái tạo JSON từ văn bản thuần túy (dùng `_reconstruct_json_from_text`)
4. **Validate answer_type:**
   - Kiểm tra answer_type có hợp lệ không (trong danh sách VALID_ANSWER_TYPES)
   - Nếu không hợp lệ → tự động điều chỉnh dựa trên nội dung và giảm confidence
5. **Trả về kết quả:** Dictionary với các trường đã được validate

**Vị trí trong code:** Dòng 1236-1399

---

#### 2.4.2. `_extract_json_with_multiline_string(text: str)`

**Tên tiếng Việt:** Trích xuất JSON có chuỗi đa dòng

**Mục đích:** Trích xuất JSON có thể chứa các chuỗi đa dòng (như bảng markdown).

**Tham số:**
- `text: str` - Văn bản chứa JSON

**Giá trị trả về:**
- JSON string hoặc None

**Logic chính:**
1. Tìm các khối markdown code (```json ... ```)
2. Trích xuất nội dung
3. Xử lý các chuỗi đa dòng trong JSON
4. Trả về JSON string nếu thành công

**Vị trí trong code:** Dòng 1401-1432

---

#### 2.4.3. `_fix_json_with_table(json_str: str) -> str`

**Tên tiếng Việt:** Sửa JSON có bảng

**Mục đích:** Cố gắng sửa các vấn đề JSON khi câu trả lời chứa bảng markdown.

**Tham số:**
- `json_str: str` - Chuỗi JSON cần sửa

**Giá trị trả về:**
- `str` - JSON string đã được sửa (hoặc nguyên văn nếu không sửa được)

**Logic chính:**
1. Tìm các chuỗi trong dấu ngoặc kép có chứa newline
2. Escape các newline trong chuỗi
3. Thử parse lại JSON
4. Trả về JSON string đã sửa

**Vị trí trong code:** Dòng 1434-1462

---

#### 2.4.4. `_reconstruct_json_from_text(text: str, query_type: str) -> dict`

**Tên tiếng Việt:** Tái tạo JSON từ văn bản

**Mục đích:** Nếu không thể parse JSON, cố gắng tái tạo JSON từ văn bản thuần túy, bao gồm việc phát hiện bảng và trích xuất chunks_found và answer_type.

**Tham số:**
- `text: str` - Văn bản thuần túy từ LLM
- `query_type: str` - Loại câu hỏi

**Giá trị trả về:**
- `dict` - Dictionary tái tạo với các trường: `answer`, `answer_type`, `chunks_used`, `confidence`, `sentence_mapping`, `sources`

**Logic chính:**
1. **Trích xuất chunks từ text:**
   - Tìm pattern: "chunk X" hoặc "[Chunk X]"
   - Lưu vào `chunks_found`
2. **Xác định answer_type:**
   - Dựa trên query_type và nội dung text
   - SECTION_OVERVIEW nếu có "phần", "nội dung chính"
   - COMPARE_SYNTHESIZE nếu có "|" (bảng) hoặc "so sánh"
   - CODE_ANALYSIS nếu có "phân tích"
   - MULTI_CONCEPT_REASONING nếu query_type là MULTI_CONCEPT_REASONING
   - EXERCISE_GENERATION nếu có "bài tập", "function"
   - DIRECT nếu có chunks
   - FALLBACK nếu không có gì
3. **Xác định confidence:**
   - SECTION_OVERVIEW: 0.75 nếu có chunks, 0.5 nếu không
   - COMPARE_SYNTHESIZE: 0.85 nếu có bảng, 0.75 nếu không
   - CODE_ANALYSIS: 0.7
   - MULTI_CONCEPT_REASONING: 0.65
   - EXERCISE_GENERATION: 0.7
   - DIRECT: 0.6
4. **Trích xuất answer:**
   - Nếu có bảng → giữ toàn bộ (tối đa 10,000 ký tự)
   - Nếu không có bảng → lấy đoạn đầu (tối đa 2,000 ký tự)
5. **Tạo sentence_mapping:**
   - Chia answer thành các câu
   - Tìm chunk liên quan cho mỗi câu (dựa trên chunk references gần đó)
6. **Trả về dictionary:** Với tất cả các trường đã tái tạo

**Vị trí trong code:** Dòng 1464-1648

---

#### 2.4.5. `_get_fallback_response() -> tuple`

**Tên tiếng Việt:** Lấy câu trả lời dự phòng

**Mục đích:** Trả về một câu trả lời mặc định khi hệ thống không thể tạo ra câu trả lời hữu ích.

**Tham số:** Không có

**Giá trị trả về:**
- `tuple` - (answer, chunks_used, answer_type, confidence, sentence_mapping)
  - answer: "Hiện tại không thể trả lời câu hỏi này. Vui lòng thử lại."
  - chunks_used: []
  - answer_type: "FALLBACK"
  - confidence: 0.0
  - sentence_mapping: []

**Vị trí trong code:** Dòng 1650-1658

---

### 2.5. Các phương thức chính

#### 2.5.1. `ask(...) -> dict`

**Tên tiếng Việt:** Xử lý câu hỏi (hàm chính)

**Mục đích:** Hàm chính xử lý toàn bộ quy trình RAG, từ nhận câu hỏi đến trả về câu trả lời đầy đủ.

**Tham số:**
- `db: AsyncIOMotorDatabase` - Database MongoDB
- `user_id: str` - ID người dùng
- `question: str` - Câu hỏi của người dùng
- `document_ids: Optional[List[str]] = None` - Danh sách ID tài liệu được chọn (tối đa 5)
- `top_k: Optional[int] = None` - Không dùng (tương thích ngược)
- `conversation_id: Optional[str] = None` - ID cuộc trò chuyện (để duy trì ngữ cảnh)

**Giá trị trả về:**
- `dict` - Dictionary chứa:
  - `answer: str` - Câu trả lời
  - `references: List[HistoryReference]` - Danh sách tham chiếu
  - `documents: List[str]` - ID các tài liệu có references
  - `documents_searched: List[str]` - ID các tài liệu đã được tìm kiếm
  - `conversation_id: Optional[str]` - ID cuộc trò chuyện
  - `history_id: Optional[str]` - ID bản ghi lịch sử
  - `metadata: dict` - Metadata về query (query_type, confidence, chunks_selected, ...)

**Logic chính (theo thứ tự):**

1. **Lấy danh sách tài liệu:**
   - Nếu có `document_ids` → chỉ lấy các tài liệu được chọn
   - Nếu không → lấy TẤT CẢ tài liệu của user
   - Validate: phải có ít nhất 1 tài liệu, tối đa 5 tài liệu

2. **Xử lý câu chào hỏi/small-talk:**
   - Nếu câu hỏi là lời chào ("hi", "xin chào", "cảm ơn", ...) → trả lời thân thiện, không gọi RAG
   - Lưu vào history và trả về

3. **Tạo embedding cho câu hỏi:**
   - Dùng `EmbeddingService` để tạo vector embedding
   - Chuyển đổi thành numpy array

4. **Phát hiện loại câu hỏi:**
   - Gọi `detect_query_type_fast(question)` để xác định loại

5. **Xác định số chunk tối đa:**
   - Gọi `_determine_max_chunks_for_query()` để tính số chunk cần lấy

6. **Tìm kiếm vector trong FAISS:**
   - Với mỗi tài liệu:
     - Load FAISS index theo namespace
     - Xác định `search_k` dựa trên query_type:
       - DOCUMENT_OVERVIEW: 150
       - SECTION_OVERVIEW: 100
       - COMPARE_SYNTHESIZE: 75
       - MULTI_CONCEPT_REASONING/CODE_ANALYSIS: 50
       - Khác: 30
     - Gọi `index.search(query_vector, search_k)` để tìm vector lân cận
     - Tính similarity: `1.0 / (1.0 + distance)`
     - Lưu vào `results`

7. **Kiểm tra kết quả:**
   - Nếu không có results → trả về fallback answer

8. **Re-ranking & Boosting:**
   - **Trích xuất từ khóa:** Loại bỏ stop words, lấy từ khóa dài > 2 ký tự
   - **Với mỗi chunk trong results:**
     - **Keyword boosting:** Tăng similarity nếu chunk chứa từ khóa từ câu hỏi
       - Quoted terms (từ khóa trong ngoặc kép): x3 weight
       - Section number match: +3 keyword_matches
       - Subsection match: +8 keyword_matches
       - Công thức: `boost = min(0.3, keyword_matches * 0.08)`
     - **Section boosting:**
       - Main section (PHẦN X, CHƯƠNG X): +0.5
     - **Table of Contents boosting:**
       - Chứa "MỤC LỤC": +0.8
     - **Overview boosting:**
       - Chứa ≥3 "PHẦN X": `min(0.6, section_count * 0.15)`
     - **Áp dụng boost:** `similarity = min(1.0, similarity + total_boost)`
   - **Sắp xếp lại:** Sort theo similarity sau boost (giảm dần)

9. **Phân loại chunk ưu tiên:**
   - **Priority chunks:** Chunk có section match hoặc concept match (similarity > 0.4)
   - **Regular chunks:** Các chunk còn lại
   - **Kết hợp:** `all_chunks_ordered = priority_chunks + regular_chunks`

10. **Xác định giới hạn ngữ cảnh:**
    - DOCUMENT_OVERVIEW:
      - 1 file: 50,000 ký tự
      - 2 files: 55,000 ký tự
      - 3+ files: 60,000 ký tự
    - Các loại khác: 12,000 ký tự

11. **Cân bằng đa tài liệu (nếu DOCUMENT_OVERVIEW và multi-doc):**
    - Chọn top chunks từ MỖI tài liệu
    - `chunks_per_doc = max(40, int(max_selected_chunks * 0.6))`
    - Re-sort theo similarity

12. **Tiền lọc section coverage (nếu DOCUMENT_OVERVIEW):**
    - Nhóm chunks theo section
    - Chọn 1 chunk đại diện cho mỗi section (similarity cao nhất)
    - Thêm vào `selected_results` trước

13. **Chọn chunks cho ngữ cảnh:**
    - Duyệt qua `all_chunks_ordered`
    - Dừng khi:
      - Đã đủ `max_selected_chunks` HOẶC
      - `current_context_length + content_length > context_limit` (cho phép vượt 5-20% với DOCUMENT_OVERVIEW)
    - Lưu metadata của mỗi chunk (chunk_index, document_id, page_number, section, heading, content, similarity)

14. **Gọi LLM để sinh câu trả lời:**
    - Gọi `_generate_answer_with_tracking()` với:
      - question
      - chunk_metadata_list
      - query_type
      - selected_documents
    - Nhận về: `(answer, chunks_actually_used, answer_type, confidence, sentence_mapping)`

15. **Xây dựng references:**
    - Tạo metadata_map để tra cứu nhanh
    - Điền các section/heading bị thiếu bằng cách tìm ngược trong các chunk trước đó
    - Xử lý FALLBACK/TOO_BROAD: không có references
    - Nếu không có chunks_actually_used nhưng không phải fallback → cố gắng khôi phục từ sentence_mapping
    - Gọi `_build_references_from_chunks()` để xây dựng danh sách references
    - Lọc và giới hạn số lượng:
      - DOCUMENT_OVERVIEW: 10 references
      - Các loại khác: 5 references

16. **Lưu lịch sử:**
    - Gọi `create_history()` để lưu vào database
    - Xử lý conversation_id (tạo mới hoặc dùng conversation_id có sẵn)

17. **Trả về kết quả:**
    - Dictionary với đầy đủ thông tin

**Vị trí trong code:** Dòng 1662-3221

---

#### 2.5.2. `_generate_answer_with_tracking(...) -> tuple`

**Tên tiếng Việt:** Sinh câu trả lời và theo dõi chunks được sử dụng

**Mục đích:** Gọi LLM để sinh câu trả lời và theo dõi các chunk thực sự được LLM sử dụng trong câu trả lời.

**Tham số:**
- `question: str` - Câu hỏi
- `chunk_metadata_list: List[dict]` - Danh sách metadata của các chunk đã chọn
- `query_type: str = "DIRECT"` - Loại câu hỏi
- `selected_documents: Optional[List[DocumentInDB]] = None` - Danh sách tài liệu được chọn

**Giá trị trả về:**
- `tuple[str, List[dict], str, float, List[dict]]` - (answer, chunks_used, answer_type, confidence, sentence_mapping)

**Logic chính:**

1. **Xây dựng context_text:**
   - Với mỗi chunk trong `chunk_metadata_list`:
     - Tạo marker: `[Chunk X] [Filename] [Page Y] [Section Z] [Sim:0.XX]`
     - Ghép với content: `{marker}\n{content}`
   - Nối các chunk bằng `\n\n---\n\n`
   - Lưu danh sách similarity vào `chunk_similarities`

2. **Xây dựng prompt:**
   - Gọi `build_gemini_optimized_prompt()` với:
     - question
     - context_text
     - chunk_similarities
     - query_type
     - selected_documents

3. **Cấu hình generation:**
   ```python
   generation_config = {
       "temperature": 0.0,  # Nhất quán, ít sáng tạo
       "maxOutputTokens": 12000,  # Token đầu ra tối đa
       "candidateCount": 1,  # Chỉ lấy 1 câu trả lời
   }
   ```

4. **Gọi Gemini API:**
   - URL: `https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent`
   - Method: POST
   - Payload: `{"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation_config}`
   - Timeout: 60 giây

5. **Trích xuất text từ response:**
   - Parse JSON response
   - Lấy text từ `candidates[0].content.parts[0].text`
   - Xử lý nested structure nếu cần

6. **Parse JSON từ response:**
   - Gọi `_safe_parse_json(raw, query_type)` để parse
   - Nhận về: `parsed` dictionary

7. **Xử lý answer nếu là JSON string bị escape:**
   - Nếu `answer` là JSON string (có `"answer": "..."`) → parse lại
   - Nếu `answer` chứa escaped JSON → trích xuất text thực tế

8. **Post-process answer:**
   - Gọi `_fix_numbered_list_formatting(answer)` để sửa định dạng danh sách
   - Gọi `_clean_table_citations(answer)` để làm sạch trích dẫn trong bảng

9. **Validation layer (Lớp kiểm tra):**
   - **TOO_BROAD:** Nếu answer_type = "TOO_BROAD" → chunks_used = [], confidence = 0.0
   - **Reasoning queries:** Nếu query_type là CODE_ANALYSIS/EXERCISE_GENERATION/MULTI_CONCEPT_REASONING:
     - Nếu answer < 50 ký tự → FALLBACK
     - Nếu confidence < 0.4 → FALLBACK
   - **Fallback detection:** Nếu phát hiện fallback keywords nhưng answer có chất lượng tốt (> 500 chars, có citations) → giữ lại và điều chỉnh
   - **Low confidence:** Nếu confidence < 0.3 nhưng answer có chất lượng tốt → giữ lại và tăng confidence
   - **SECTION_OVERVIEW validation:** Kiểm tra cấu trúc và độ dài
   - **DOCUMENT_OVERVIEW validation:** Tương tự SECTION_OVERVIEW
   - **Confidence-Chunks Paradox:** Nếu confidence > 0.7 nhưng chunks_used = 0 → nghi ngờ, điều chỉnh

10. **Map chunks_used:**
    - Chuyển đổi chunk indices thành dict với document_id

11. **Trả về:** (answer, chunks_used, answer_type, confidence, sentence_mapping)

**Vị trí trong code:** Dòng 3225-3772

---

#### 2.5.3. `_parse_answer_and_chunks(full_response: str, chunk_metadata_list: List[dict]) -> tuple`

**Tên tiếng Việt:** Parse câu trả lời và chunks từ phản hồi đầy đủ

**Mục đích:** Trích xuất answer và chunks_used từ phản hồi của LLM (hàm helper).

**Tham số:**
- `full_response: str` - Phản hồi đầy đủ từ LLM
- `chunk_metadata_list: List[dict]` - Danh sách metadata chunk

**Giá trị trả về:**
- `tuple[str, List[dict]]` - (answer, chunks_used)

**Vị trí trong code:** Dòng 3776-3890

---

#### 2.5.4. `_build_references_from_chunks(...) -> List[HistoryReference]`

**Tên tiếng Việt:** Xây dựng tham chiếu từ chunks

**Mục đích:** Xây dựng danh sách `HistoryReference` từ các chunk thực sự được LLM sử dụng.

**Tham số:**
- `chunks_used: List[dict]` - Danh sách chunks được sử dụng (có chunk_index và document_id)
- `selected_results: List[dict]` - Danh sách kết quả đã chọn (có đầy đủ thông tin)
- `chunk_metadata_for_context: List[dict]` - Metadata chunk đã gửi cho LLM

**Giá trị trả về:**
- `List[HistoryReference]` - Danh sách tham chiếu

**Logic chính:**
1. **Với mỗi chunk trong chunks_used:**
   - Tìm chunk tương ứng trong `selected_results` (dựa trên chunk_index và document_id)
   - Lấy thông tin: document, chunk_doc, content, metadata
   - Trích xuất: page_number, section, heading
   - Tạo preview: 160 ký tự đầu của content
   - Tạo `HistoryReference` object với:
     - document_id, document_filename, document_file_type
     - chunk_id, chunk_index
     - page_number, section
     - score (similarity), content_preview
2. **Loại bỏ trùng lặp:**
   - Dựa trên key: `{document_id}_{chunk_index}`
3. **Giới hạn số lượng dựa trên độ phức tạp:**
   - Nếu chunks_used ≥ 5: max_refs = 5
   - Nếu chunks_used ≥ 3: max_refs = 4
   - Nếu chunks_used < 3: max_refs = 2
4. **Trả về:** Danh sách references đã được giới hạn

**Vị trí trong code:** Dòng 3892-3966

---

## 3. TỔNG KẾT QUY TRÌNH RAG

### Flow tổng thể từ câu hỏi đến câu trả lời:

1. **User gửi câu hỏi** → `ask()` được gọi
2. **Lấy tài liệu** → Validate và load documents
3. **Xử lý small-talk** → Nếu là lời chào, trả lời ngay
4. **Tạo embedding** → Chuyển câu hỏi thành vector
5. **Phát hiện loại câu hỏi** → `detect_query_type_fast()`
6. **Xác định số chunk tối đa** → `_determine_max_chunks_for_query()`
7. **Tìm kiếm vector** → Search trong FAISS với search_k phù hợp
8. **Re-ranking & Boosting** → Tăng điểm cho chunks quan trọng
9. **Chọn chunks** → Dựa trên priority, similarity, context length
10. **Xây dựng prompt** → `build_gemini_optimized_prompt()`
11. **Gọi LLM** → `_generate_answer_with_tracking()`
12. **Parse response** → `_safe_parse_json()`
13. **Validation** → Kiểm tra confidence, answer length, chunks_used
14. **Xây dựng references** → `_build_references_from_chunks()`
15. **Lưu lịch sử** → `create_history()`
16. **Trả về kết quả** → Dictionary đầy đủ

---

## 4. CÁC BIẾN VÀ HẰNG SỐ QUAN TRỌNG

### Trong class RAGService:

- `self.embedding_service`: Dịch vụ tạo embedding
- `self.provider`: Nhà cung cấp LLM ("gemini" hoặc "openai")
- `self.model`: Tên model LLM
- `self.max_context_length`: Độ dài ngữ cảnh tối đa (12,000 ký tự)
- `self.max_output_tokens`: Token đầu ra tối đa (12,000 tokens)
- `self._openai_client`: OpenAI client (nếu dùng OpenAI)
- `self._gemini_api_key`: Gemini API key (nếu dùng Gemini)
- `self._gemini_base_url`: URL base của Gemini API

### Các query types (Loại câu hỏi):

- `SECTION_OVERVIEW`: Tổng quan phần
- `DOCUMENT_OVERVIEW`: Tổng quan tài liệu
- `DIRECT`: Trực tiếp
- `COMPARE_SYNTHESIZE`: So sánh tổng hợp
- `CODE_ANALYSIS`: Phân tích code
- `EXERCISE_GENERATION`: Tạo bài tập
- `MULTI_CONCEPT_REASONING`: Lý luận đa khái niệm
- `EXPAND`: Mở rộng
- `EXISTENCE`: Tồn tại
- `FALLBACK`: Dự phòng
- `TOO_BROAD`: Quá rộng

---

## 5. LƯU Ý QUAN TRỌNG

1. **File rất lớn (3970 dòng):** Chứa toàn bộ logic RAG phức tạp
2. **Xử lý nhiều edge cases:** Fallback, JSON parsing, validation, ...
3. **Tối ưu cho Gemini 2.5 Flash:** Prompt được tối ưu cho model này
4. **Hỗ trợ đa tài liệu:** Có thể xử lý tối đa 5 tài liệu cùng lúc
5. **Validation nhiều lớp:** Kiểm tra confidence, answer length, chunks_used, ...
6. **Error handling:** Xử lý lỗi API, parse JSON, fallback, ...

---

**File này được tạo để giải thích chi tiết tất cả các hàm trong `rag.py`. Nếu cần giải thích thêm phần nào, vui lòng yêu cầu!**

