import os
import shutil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer

from ..core.database import get_database, get_faiss_index_path
from ..core.config import settings
from ..core.security import decode_token
from ..models.user import get_user_by_id, UserPublic
from ..models.document import (
    DocumentPublic,
    DocumentDetail,
    create_document,
    get_document_by_id,
    get_documents_by_user,
    delete_document as db_delete_document,
    get_chunks_by_document,
    save_chunks,
)
from ..services.embedding import EmbeddingService
from ..services.parser import parse_file, split_text, get_file_type_from_filename

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    """Lấy user hiện tại từ JWT token."""
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    db = get_database()
    user = await get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name)


def ensure_upload_dir(user_id: str) -> str:
    """Tạo thư mục upload cho user nếu chưa có."""
    user_dir = os.path.join(settings.upload_dir, user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


@router.post("/upload", response_model=DocumentPublic, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(get_current_user),
):
    """Upload và xử lý tài liệu."""
    # Kiểm tra loại file
    file_type = get_file_type_from_filename(file.filename)
    if file_type not in ["pdf", "docx", "md", "txt"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: PDF, DOCX, MD, TXT",
        )
    
    db = get_database()
    
    # Tạo thư mục cho user
    user_dir = ensure_upload_dir(current_user.id)
    
    # Lưu file tạm
    file_path = os.path.join(user_dir, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    file_size = os.path.getsize(file_path)
    
    try:
        # Parse nội dung file - trả về list chunks với metadata
        parsed_chunks = parse_file(file_path, file_type)
        
        # Chia nhỏ thành chunks (nếu cần) - giữ metadata
        # Tăng chunk_size lên 800 để giữ nguyên page content tốt hơn, chỉ chia khi thực sự cần
        chunks = split_text(parsed_chunks, chunk_size=800, chunk_overlap=100)
        
        # Lấy preview từ chunks đầu tiên
        content_preview = None
        if chunks and chunks[0].get("content"):
            content_preview = chunks[0]["content"][:200]
        
        # Lưu document vào DB
        document = await create_document(
            db=db,
            user_id=current_user.id,
            filename=file.filename,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size,
            chunk_count=len(chunks),
            content_preview=content_preview,
        )

        # Lưu chunks vào DB
        saved_chunks = await save_chunks(db, document.id, chunks)

        # Sinh embedding cho các chunks (nếu không có nội dung sẽ đánh dấu embedded = False)
        embedding_service = EmbeddingService()
        try:
            await embedding_service.embed_document_chunks(
                db=db,
                user_id=current_user.id,
                document=document,
                chunks=saved_chunks,
            )
            refreshed = await get_document_by_id(db, document.id)
            if refreshed:
                document = refreshed
        except Exception as exc:
            print(f"[embedding] failed for document {document.id}: {exc}")

        return DocumentPublic(
            id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            file_type=document.file_type,
            file_size=document.file_size,
            upload_date=document.upload_date,
            chunk_count=document.chunk_count,
            content_preview=document.content_preview,
            is_embedded=document.is_embedded,
            embedded_at=document.embedded_at,
            embedding_model=document.embedding_model,
            embedding_dimension=document.embedding_dimension,
            faiss_namespace=document.faiss_namespace,
        )
    except ValueError as e:
        # Xóa file nếu parse lỗi
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Xóa file nếu có lỗi
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}",
        )


@router.get("/", response_model=List[DocumentPublic])
async def list_documents(current_user: UserPublic = Depends(get_current_user)):
    """Lấy danh sách tài liệu của user hiện tại."""
    db = get_database()
    documents = await get_documents_by_user(db, current_user.id)
    return [
        DocumentPublic(
            id=doc.id,
            user_id=doc.user_id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            upload_date=doc.upload_date,
            chunk_count=doc.chunk_count,
            content_preview=doc.content_preview,
            is_embedded=doc.is_embedded,
            embedded_at=doc.embedded_at,
            embedding_model=doc.embedding_model,
            embedding_dimension=doc.embedding_dimension,
            faiss_namespace=doc.faiss_namespace,
        )
        for doc in documents
    ]


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """Lấy chi tiết 1 tài liệu (bao gồm chunks)."""
    db = get_database()
    document = await get_document_by_id(db, document_id)
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    # Kiểm tra quyền sở hữu
    if document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    # Lấy chunks
    chunks = await get_chunks_by_document(db, document_id)
    
    return DocumentDetail(
        id=document.id,
        user_id=document.user_id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        upload_date=document.upload_date,
        chunk_count=document.chunk_count,
        content_preview=document.content_preview,
        is_embedded=document.is_embedded,
        embedded_at=document.embedded_at,
        embedding_model=document.embedding_model,
        embedding_dimension=document.embedding_dimension,
        faiss_namespace=document.faiss_namespace,
        chunks=chunks,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """Xóa tài liệu (chỉ user sở hữu)."""
    db = get_database()
    document = await get_document_by_id(db, document_id)
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    if document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    # Xóa file trên disk
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception:
            pass  # Bỏ qua nếu không xóa được
    
    # Xóa metadata embedding
    await db["embeddings"].delete_many({"document_id": document_id})

    # Xóa FAISS index file
    namespace = document.faiss_namespace or f"user_{document.user_id}_doc_{document.id}"
    index_path = get_faiss_index_path(namespace)
    if os.path.exists(index_path):
        try:
            os.remove(index_path)
        except Exception:
            pass

    # Xóa trong DB
    await db_delete_document(db, document_id)
    
    return None
