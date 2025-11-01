from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId


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
    })
    return UserInDB.model_validate({
        "_id": str(res.inserted_id),
        "email": email,
        "hashed_password": hashed_password,
        "full_name": full_name,
        "is_admin": is_admin,
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
    return UserInDB.model_validate(doc)

