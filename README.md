AI Study QnA

Quick start for Modules 1-2

Backend

- Create and activate venv, then install requirements:

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
```

- Optional env:

```bash
set MONGODB_URI=mongodb://localhost:27017
set MONGODB_DB=studyqna
set FAISS_INDEX_DIR=./data/faiss
set API_PORT=8000
```

- Run API:

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/health` and `/hello`

Frontend (placeholder)

- From `frontend/` install and run after Node setup:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`

Notes

- MongoDB is required locally (or provide a remote URI)
- FAISS index directory will be created under `data/faiss`

Backend quick commands (Windows)

PowerShell

```powershell
cd "D:\dữ liệu đồ án\StudyQnA\backend"
.# activate venv
 .\.venv\Scripts\Activate.ps1
.# optional env for this session
 $env:MONGODB_URI="mongodb://localhost:27017"
 $env:MONGODB_DB="studyqna"
 $env:FAISS_INDEX_DIR=".\data\faiss"
 $env:API_PORT="8000"
.# run API
 python -m uvicorn app.main:app --reload --port 8000
```

Git Bash

```bash
cd "/d/dữ liệu đồ án/StudyQnA/backend"
source .venv/Scripts/activate
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB="studyqna"
export FAISS_INDEX_DIR="./data/faiss"
export API_PORT="8000"
python -m uvicorn app.main:app --reload --port 8000
```

Using .env file

```bash
# backend/.env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=studyqna
FAISS_INDEX_DIR=./data/faiss
API_PORT=8000

# run with env file
python -m uvicorn app.main:app --reload --port 8000 --env-file .env
```

> Nếu muốn chỉ định email được cấp quyền admin ngay khi đăng ký, thêm biến `ADMIN_EMAILS` (danh sách email, phân tách bởi dấu phẩy) trong `.env`.

## Module 3 – Auth (POSTMAN test quick ref)

1. **Đăng ký**
   - POST `http://localhost:8000/auth/register`
   - JSON body: `{ "email": "abc@example.com", "password": "123456", "full_name": "ABC" }`
2. **Đăng nhập**
   - POST `http://localhost:8000/auth/login-json`
   - JSON body: `{ "email": "abc@example.com", "password": "123456" }`
   - Lấy `access_token`
3. **Me**
   - GET `http://localhost:8000/auth/me`
   - Header `Authorization: Bearer <access_token>`

## Module 4 – Upload & Parse tài liệu

1. **Upload**
   - POST `http://localhost:8000/documents/upload`
   - Header `Authorization: Bearer <token>`
   - Body `form-data`: key `file` (type File) → chọn PDF/DOCX/MD/TXT
2. **Danh sách**: GET `http://localhost:8000/documents/`
3. **Chi tiết**: GET `http://localhost:8000/documents/<document_id>`
4. **Xoá**: DELETE `http://localhost:8000/documents/<document_id>`

Sau upload, file gốc lưu tại `data/uploads/<user_id>/`. MongoDB lưu metadata ở `documents`, chunks ở `chunks`.

## Module 5 – Embedding & FAISS

Chức năng:

- Sinh embedding cho các chunk (OpenAI `text-embedding-3-small` hoặc local `sentence-transformers/all-MiniLM-L6-v2`).
- Lưu vector vào FAISS index (mỗi tài liệu 1 index file dưới `data/faiss`).
- Lưu metadata mapping trong MongoDB collection `embeddings` và cập nhật `documents`, `chunks`.

Config thêm (mặc định đã set):

```
EMBEDDING_PROVIDER=openai  # hoặc local
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_LOCAL_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_BATCH_SIZE=32
```

Test nhanh sau khi upload thành công:

1. Upload tài liệu → response chứa `is_embedded=true`, `embedding_model`, `embedding_dimension`.
2. Kiểm tra MongoDB:
   - `documents`: trường `is_embedded`, `embedded_at`, `faiss_namespace`
   - `chunks`: `has_embedding`, `embedding_index`
   - `embeddings`: metadata vector
3. FAISS file: `data/faiss/user_<user_id>_doc_<document_id>.faiss`

## Module 6 – RAG (Retrieval-Augmented Generation)

- Endpoint chính: `POST /query/ask`
  - Body JSON: `{ "question": "...", "document_id": "<optional>", "top_k": 5 }`
  - Header: `Authorization: Bearer <token>`
  - Kết quả: `{ "answer": "...", "references": [...], "documents": [...] }`
- Lịch sử: `GET /query/history?document_id=<optional>&limit=20`

### Luồng xử lý

1. Embed câu hỏi bằng cùng model (OpenAI hoặc SentenceTransformer) → truy FAISS.
2. Lấy top-k chunk gần nhất, ghép ngữ cảnh → gọi LLM sinh câu trả lời.
3. Lưu lịch sử vào collection `histories` (question, answer, references).

### Cấu hình LLM

```
LLM_PROVIDER=openai           # hoặc local
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=512
RAG_TOP_K=5
```

- Nếu dùng OpenAI: cần `OPENAI_API_KEY`.
- Nếu `LLM_PROVIDER=local`, câu trả lời fallback tóm tắt theo context (không gọi API ngoài).

### Test nhanh (Postman)

1. Đảm bảo đã upload và embed tài liệu (Module 5).
2. `POST /query/ask` với câu hỏi liên quan tới tài liệu.
3. Kiểm tra response tham chiếu chunk (`references`), nội dung `answer`.
4. `GET /query/history` để xem lại phiên hỏi đáp.

## Module 7 – History

- **Xem lịch sử**
  - `GET /history?limit=20` – trả về tối đa 20 bản ghi gần nhất (có thể chỉnh `limit=1..100`).
  - Thêm `document_id=<id>` để lọc theo tài liệu: `GET /history?document_id=...&limit=10`.
  - Header: `Authorization: Bearer <token>`.
- **Xóa lịch sử**
  - `DELETE /history/{history_id}` – xóa một bản ghi cụ thể.
  - `DELETE /history/document/{document_id}` – xóa lịch sử của tài liệu.
  - `DELETE /history/all` – xóa toàn bộ lịch sử của user (cẩn trọng).

Mỗi bản ghi lịch sử chứa `question`, `answer`, danh sách `references` (chunk nguồn, điểm tương đồng), `document_id`, `created_at`. Dữ liệu này phục vụ trang lịch sử (frontend) và dashboard quản trị (Module 8).

## Module 8 – Admin Dashboard

- **Kích hoạt quyền admin**
  - Thêm email vào biến môi trường `ADMIN_EMAILS` (ví dụ `ADMIN_EMAILS=admin@example.com`). Khi người dùng đăng ký với email này sẽ có `is_admin=true`.
  - Hoặc cập nhật trực tiếp trong MongoDB (`users` → field `is_admin` = true).
- **API chính** (yêu cầu Bearer token của admin):
  - `GET /admin/users` – danh sách người dùng + số lượng tài liệu/câu hỏi.
  - `GET /admin/documents` – danh sách tài liệu, dung lượng, trạng thái embedding.
  - `GET /admin/stats` – thống kê hệ thống (người dùng, tài liệu, lịch sử, dung lượng...).
- **Frontend**
  - Trang `Admin` đã được scaffold (`/admin`) hiển thị bảng người dùng, tài liệu và thống kê cơ bản.
  - Đặt token sau khi đăng nhập vào `localStorage.setItem('token', '<access_token>')` để dashboard gọi API.
- **Phân quyền**
  - Các endpoint `/admin/*` yêu cầu user có `is_admin=true`. Nếu token không có quyền, API trả 403.

## Module 9 – Frontend-Backend Integration

- **Đã hoàn thiện các trang:**
  - `/login` – Form đăng nhập, lưu token vào localStorage
  - `/upload` – Upload tài liệu, hiển thị danh sách và trạng thái embedding
  - `/chat` – Giao diện hỏi đáp với tài liệu, hiển thị answer và references
  - `/history` – Xem và quản lý lịch sử hỏi đáp
  - `/admin` – Dashboard quản trị (yêu cầu quyền admin)
- **Bảo vệ route:** `ProtectedRoute` component tự động redirect về `/login` nếu chưa đăng nhập
- **API service:** `src/services/api.js` chứa tất cả functions gọi API (auth, documents, query, history, admin)
- **Chạy frontend:**
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
  Mở `http://localhost:5173` → đăng nhập và sử dụng các chức năng.
