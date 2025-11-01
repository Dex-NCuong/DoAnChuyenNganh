from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field


class HistoryReference(BaseModel):
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    chunk_index: Optional[int] = None
    score: Optional[float] = None
    content_preview: Optional[str] = None


class HistoryInDB(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    question: str
    answer: str
    references: List[HistoryReference] = []
    document_id: Optional[str] = None
    conversation_id: Optional[str] = None  # Group Q&As in the same conversation
    created_at: datetime


class HistoryPublic(BaseModel):
    id: str
    user_id: str
    question: str
    answer: str
    references: List[HistoryReference] = []
    document_id: Optional[str] = None
    conversation_id: Optional[str] = None  # Group Q&As in the same conversation
    created_at: datetime


async def create_history(
    db: AsyncIOMotorDatabase,
    user_id: str,
    question: str,
    answer: str,
    references: List[HistoryReference],
    document_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> HistoryInDB:
    payload = {
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "references": [ref.model_dump() for ref in references],
        "document_id": document_id,
        "conversation_id": conversation_id,
        "created_at": datetime.utcnow(),
    }
    result = await db["histories"].insert_one(payload)
    payload["_id"] = str(result.inserted_id)
    return HistoryInDB.model_validate(payload)


async def list_history_by_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 20,
    document_id: Optional[str] = None,
) -> List[HistoryInDB]:
    query = {"user_id": user_id}
    if document_id:
        query["document_id"] = document_id
    cursor = (
        db["histories"].find(query).sort("created_at", -1).limit(limit)
    )
    records = await cursor.to_list(length=limit)
    for record in records:
        record["_id"] = str(record["_id"])
    return [HistoryInDB.model_validate(record) for record in records]


async def clear_history_for_document(
    db: AsyncIOMotorDatabase,
    user_id: str,
    document_id: str,
) -> None:
    query = {"user_id": user_id, "document_id": document_id}
    await db["histories"].delete_many(query)
 

async def delete_history_record(
    db: AsyncIOMotorDatabase,
    user_id: str,
    history_id: str,
) -> bool:
    try:
        oid = ObjectId(history_id)
    except Exception:
        return False
    result = await db["histories"].delete_one({"_id": oid, "user_id": user_id})
    return result.deleted_count > 0


async def clear_history_for_user(db: AsyncIOMotorDatabase, user_id: str) -> None:
    await db["histories"].delete_many({"user_id": user_id})


async def delete_history_by_conversation(
    db: AsyncIOMotorDatabase,
    user_id: str,
    conversation_id: str,
) -> int:
    """Delete all history records in a conversation. Returns number of deleted records."""
    from bson import ObjectId
    
    # Try to find records by conversation_id
    query = {"user_id": user_id, "conversation_id": conversation_id}
    result = await db["histories"].delete_many(query)
    
    # If no records found with conversation_id, check if conversation_id is actually a history_id
    # (for backward compatibility - old conversations might use history_id as conversation_id)
    if result.deleted_count == 0:
        try:
            oid = ObjectId(conversation_id)
            # Try to find a record with this ID as conversation_id
            record = await db["histories"].find_one({"_id": oid, "user_id": user_id})
            if record:
                # If found, this ID is actually a history_id that was used as conversation_id
                # Delete all records with this conversation_id (which equals this history_id)
                result = await db["histories"].delete_many(
                    {"user_id": user_id, "conversation_id": conversation_id}
                )
        except Exception:
            pass
    
    return result.deleted_count

