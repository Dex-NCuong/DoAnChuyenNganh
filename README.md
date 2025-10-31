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
