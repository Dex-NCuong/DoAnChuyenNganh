from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field


class UserInCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserInDB(BaseModel):
    id: str = Field(alias="_id")
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    is_admin: bool = False
    google_calendar_connected: bool = False
    google_calendar_token: Optional[str] = None
    calendar_connected_at: Optional[datetime] = None


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_admin: bool = False


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[UserInDB]:
    doc = await db["users"].find_one({"email": email})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])  # stringify ObjectId
    doc.setdefault("is_admin", False)
    doc.setdefault("google_calendar_connected", False)
    doc.setdefault("google_calendar_token", None)
    doc.setdefault("calendar_connected_at", None)
    return UserInDB.model_validate(doc)


async def create_user(
    db: AsyncIOMotorDatabase,
    email: str,
    hashed_password: str,
    full_name: Optional[str] = None,
    is_admin: bool = False,
) -> UserInDB:
    res = await db["users"].insert_one({
        "email": email,
        "hashed_password": hashed_password,
        "full_name": full_name,
        "is_admin": is_admin,
        "google_calendar_connected": False,
        "google_calendar_token": None,
        "calendar_connected_at": None,
    })
    return UserInDB.model_validate({
        "_id": str(res.inserted_id),
        "email": email,
        "hashed_password": hashed_password,
        "full_name": full_name,
        "is_admin": is_admin,
        "google_calendar_connected": False,
        "google_calendar_token": None,
        "calendar_connected_at": None,
    })


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[UserInDB]:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    doc = await db["users"].find_one({"_id": oid})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])  # stringify ObjectId
    doc.setdefault("is_admin", False)
    doc.setdefault("google_calendar_connected", False)
    doc.setdefault("google_calendar_token", None)
    doc.setdefault("calendar_connected_at", None)
    return UserInDB.model_validate(doc)


async def set_user_calendar_credentials(
    db: AsyncIOMotorDatabase,
    user_id: str,
    encrypted_token: str,
) -> None:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return
    await db["users"].update_one(
        {"_id": oid},
        {
            "$set": {
                "google_calendar_connected": True,
                "google_calendar_token": encrypted_token,
                "calendar_connected_at": datetime.now(tz=timezone.utc),
            }
        },
    )


async def clear_user_calendar_credentials(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> None:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return
    await db["users"].update_one(
        {"_id": oid},
        {
            "$set": {
                "google_calendar_connected": False,
                "google_calendar_token": None,
                "calendar_connected_at": None,
            }
        },
    )


async def get_user_calendar_token(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> Optional[str]:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    doc = await db["users"].find_one({"_id": oid}, {"google_calendar_token": 1})
    if not doc:
        return None
    token = doc.get("google_calendar_token")
    if not token:
        return None
    return token

