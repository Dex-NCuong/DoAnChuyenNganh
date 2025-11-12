from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pymongo import UpdateOne


class DocumentInDB(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    filename: str
    file_type: str  # pdf, docx, md, txt
    file_path: str  # đường dẫn lưu file trên server
    file_size: int  # bytes
    upload_date: datetime
    chunk_count: int = 0
    content_preview: Optional[str] = None  # 200 ký tự đầu
    is_embedded: bool = False
    embedded_at: Optional[datetime] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    faiss_namespace: Optional[str] = None


class DocumentPublic(BaseModel):
    id: str
    user_id: str
    filename: str
    file_type: str
    file_size: int
    upload_date: datetime
    chunk_count: int
    content_preview: Optional[str] = None
    is_embedded: bool = False
    embedded_at: Optional[datetime] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    faiss_namespace: Optional[str] = None


class DocumentDetail(DocumentPublic):
    chunks: list[dict] = []  # [{chunk_index, content, metadata}]


async def create_document(
    db: AsyncIOMotorDatabase,
    user_id: str,
    filename: str,
    file_type: str,
    file_path: str,
    file_size: int,
    chunk_count: int = 0,
    content_preview: Optional[str] = None,
) -> DocumentInDB:
    doc_data = {
        "user_id": user_id,
        "filename": filename,
        "file_type": file_type,
        "file_path": file_path,
        "file_size": file_size,
        "upload_date": datetime.now(tz=timezone.utc),
        "chunk_count": chunk_count,
        "content_preview": content_preview,
        "is_embedded": False,
        "embedded_at": None,
        "embedding_model": None,
        "embedding_dimension": None,
        "faiss_namespace": None,
    }
    result = await db["documents"].insert_one(doc_data)
    doc_data["_id"] = str(result.inserted_id)
    namespace = f"user_{user_id}_doc_{doc_data['_id']}"
    doc_data["faiss_namespace"] = namespace

    await db["documents"].update_one(
        {"_id": ObjectId(result.inserted_id)},
        {"$set": {"faiss_namespace": namespace}},
    )

    return DocumentInDB.model_validate(doc_data)


async def get_document_by_id(db: AsyncIOMotorDatabase, document_id: str) -> Optional[DocumentInDB]:
    try:
        oid = ObjectId(document_id)
    except Exception:
        return None
    doc = await db["documents"].find_one({"_id": oid})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    doc.setdefault("faiss_namespace", f"user_{doc['user_id']}_doc_{doc['_id']}")
    return DocumentInDB.model_validate(doc)


async def get_documents_by_user(db: AsyncIOMotorDatabase, user_id: str) -> list[DocumentInDB]:
    cursor = db["documents"].find({"user_id": user_id}).sort("upload_date", -1)
    docs = await cursor.to_list(length=None)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        doc.setdefault("faiss_namespace", f"user_{doc['user_id']}_doc_{doc['_id']}")
    return [DocumentInDB.model_validate(doc) for doc in docs]


async def delete_document(db: AsyncIOMotorDatabase, document_id: str) -> bool:
    try:
        oid = ObjectId(document_id)
    except Exception:
        return False
    result = await db["documents"].delete_one({"_id": oid})
    # Xóa cả chunks liên quan
    await db["chunks"].delete_many({"document_id": document_id})
    return result.deleted_count > 0


async def get_chunks_by_document(db: AsyncIOMotorDatabase, document_id: str) -> list[dict]:
    cursor = db["chunks"].find({"document_id": document_id}).sort("chunk_index", 1)
    chunks = await cursor.to_list(length=None)
    for chunk in chunks:
        chunk["_id"] = str(chunk.get("_id", ""))
    return chunks


async def save_chunks(db: AsyncIOMotorDatabase, document_id: str, chunks: list[dict]) -> list[dict]:
    """Lưu chunks vào collection chunks. Mỗi chunk có: document_id, chunk_index, content, metadata."""
    if not chunks:
        return []
    chunk_docs = []
    for idx, chunk_data in enumerate(chunks):
        chunk_docs.append({
            "document_id": document_id,
            "chunk_index": idx,
            "content": chunk_data.get("content", ""),
            "metadata": chunk_data.get("metadata", {}),
            "has_embedding": False,
            "embedding_index": None,
            "embedding_model": None,
            "embedded_at": None,
        })
    saved_chunks: list[dict] = []
    if chunk_docs:
        result = await db["chunks"].insert_many(chunk_docs)
        for inserted_id, chunk_doc in zip(result.inserted_ids, chunk_docs):
            chunk_doc["_id"] = str(inserted_id)
            saved_chunks.append(chunk_doc)
    return saved_chunks


async def mark_document_embedded(
    db: AsyncIOMotorDatabase,
    document_id: str,
    embedding_model: str,
    embedding_dimension: int,
) -> None:
    try:
        oid = ObjectId(document_id)
    except Exception:
        return
    await db["documents"].update_one(
        {"_id": oid},
        {
            "$set": {
                "is_embedded": True,
                "embedded_at": datetime.now(tz=timezone.utc),
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
            }
        },
    )


async def mark_chunks_embedded(
    db: AsyncIOMotorDatabase,
    chunk_updates: list[dict],
) -> None:
    if not chunk_updates:
        return
    bulk_ops = []
    now = datetime.now(tz=timezone.utc)
    for update in chunk_updates:
        chunk_id = update.get("chunk_id")
        if not chunk_id:
            continue
        try:
            oid = ObjectId(chunk_id)
        except Exception:
            continue
        bulk_ops.append(
            UpdateOne(
                {"_id": oid},
                {
                    "$set": {
                        "has_embedding": True,
                        "embedding_index": update.get("embedding_index"),
                        "embedding_model": update.get("embedding_model"),
                        "embedded_at": now,
                    }
                },
            )
        )
    if bulk_ops:
        await db["chunks"].bulk_write(bulk_ops)

