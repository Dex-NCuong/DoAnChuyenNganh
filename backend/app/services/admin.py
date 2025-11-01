from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


async def fetch_user_overview(db: AsyncIOMotorDatabase, limit: int = 200) -> List[Dict[str, Any]]:
    cursor = db["users"].find({}, {"email": 1, "full_name": 1, "is_admin": 1}).sort("email", 1)
    users = await cursor.to_list(length=limit)

    overview: List[Dict[str, Any]] = []
    for user in users:
        user_id = str(user.get("_id"))
        documents_count = await db["documents"].count_documents({"user_id": user_id})
        histories_count = await db["histories"].count_documents({"user_id": user_id})
        last_history_doc = await db["histories"].find({"user_id": user_id}).sort("created_at", -1).limit(1).to_list(length=1)
        last_history = last_history_doc[0]["created_at"] if last_history_doc else None

        overview.append(
            {
                "id": user_id,
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "is_admin": bool(user.get("is_admin", False)),
                "documents_count": documents_count,
                "histories_count": histories_count,
                "last_activity": last_history,
            }
        )

    return overview


async def fetch_document_overview(db: AsyncIOMotorDatabase, limit: int = 200) -> List[Dict[str, Any]]:
    cursor = db["documents"].find().sort("upload_date", -1)
    documents = await cursor.to_list(length=limit)

    user_cache: Dict[str, Dict[str, Any]] = {}
    result: List[Dict[str, Any]] = []

    for doc in documents:
        raw_user_id = doc.get("user_id")
        user_id = str(raw_user_id) if raw_user_id is not None else None
        cache_key = user_id or "__unknown__"

        if cache_key not in user_cache:
            user_doc = None
            if user_id:
                try:
                    user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
                except Exception:
                    user_doc = await db["users"].find_one({"_id": user_id})
            user_cache[cache_key] = user_doc or {}

        owner = user_cache.get(cache_key, {})

        document_id = doc.get("_id")
        if isinstance(document_id, ObjectId):
            document_id = str(document_id)

        result.append(
            {
                "id": document_id or "",
                "user_id": user_id,
                "owner_email": owner.get("email"),
                "filename": doc.get("filename"),
                "file_size": doc.get("file_size"),
                "file_type": doc.get("file_type"),
                "upload_date": doc.get("upload_date"),
                "chunk_count": doc.get("chunk_count"),
                "is_embedded": doc.get("is_embedded", False),
                "embedded_at": doc.get("embedded_at"),
            }
        )

    return result


async def fetch_system_stats(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    total_users = await db["users"].count_documents({})
    total_documents = await db["documents"].count_documents({})
    total_histories = await db["histories"].count_documents({})

    total_storage = 0
    async for doc in db["documents"].find({}, {"file_size": 1}):
        total_storage += doc.get("file_size", 0)

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_questions = await db["histories"].count_documents({"created_at": {"$gte": seven_days_ago}})

    pipeline = [
        {"$match": {"created_at": {"$gte": seven_days_ago}}},
        {"$group": {"_id": "$user_id"}},
        {"$count": "active_users"},
    ]
    agg_result = await db["histories"].aggregate(pipeline).to_list(length=1)
    active_users = agg_result[0]["active_users"] if agg_result else 0

    return {
        "total_users": total_users,
        "total_documents": total_documents,
        "total_histories": total_histories,
        "recent_questions": recent_questions,
        "active_users_7d": active_users,
        "total_storage_bytes": total_storage,
    }

