from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field


class CalendarEventInDB(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    google_event_id: str
    summary: str
    start: datetime
    end: datetime
    timezone: str
    description: Optional[str] = None
    event_type: Optional[str] = None
    question_id: Optional[str] = None
    document_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


async def upsert_calendar_event(
    db: AsyncIOMotorDatabase,
    user_id: str,
    google_event_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    timezone: str,
    description: Optional[str] = None,
    event_type: Optional[str] = None,
    question_id: Optional[str] = None,
    document_ids: Optional[list[str]] = None,
) -> None:
    """Create or update a stored calendar event reference for a user."""
    document_ids = document_ids or []
    now = datetime.utcnow()
    await db["calendar_events"].update_one(
        {"user_id": user_id, "google_event_id": google_event_id},
        {
            "$set": {
                "summary": summary,
                "start": start,
                "end": end,
                "timezone": timezone,
                "description": description,
                "event_type": event_type,
                "question_id": question_id,
                "document_ids": document_ids,
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "google_event_id": google_event_id,
                "created_at": now,
            },
        },
        upsert=True,
    )


async def delete_calendar_event(
    db: AsyncIOMotorDatabase,
    user_id: str,
    google_event_id: str,
) -> None:
    await db["calendar_events"].delete_one(
        {"user_id": user_id, "google_event_id": google_event_id}
    )


async def list_calendar_events(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 20,
) -> list[CalendarEventInDB]:
    cursor = (
        db["calendar_events"]
        .find({"user_id": user_id})
        .sort("start", 1)
        .limit(limit)
    )
    results: list[CalendarEventInDB] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["created_at"] = doc.get("created_at") or datetime.utcnow()
        doc["updated_at"] = doc.get("updated_at") or datetime.utcnow()
        results.append(CalendarEventInDB.model_validate(doc))
    return results

