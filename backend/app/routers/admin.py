from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from ..core.database import get_database
from ..core.security import decode_token, hash_password
from ..models.user import get_user_by_id, get_user_by_email, create_user, UserPublic
from ..services.admin import fetch_user_overview, fetch_document_overview, fetch_system_stats


router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_admin(token: str = Depends(oauth2_scheme)) -> UserPublic:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    db = get_database()
    user = await get_user_by_id(db, payload["sub"])
    if not user or not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name, is_admin=user.is_admin)


class AdminUserSummary(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_admin: bool = False
    documents_count: int
    histories_count: int
    last_activity: datetime | None = None


class AdminDocumentSummary(BaseModel):
    id: str
    user_id: str | None = None
    owner_email: str | None = None
    filename: str | None = None
    file_size: int | None = None
    file_type: str | None = None
    upload_date: datetime | None = None
    chunk_count: int | None = None
    is_embedded: bool = False
    embedded_at: datetime | None = None


class AdminStats(BaseModel):
    total_users: int
    total_documents: int
    total_histories: int
    recent_questions: int
    active_users_7d: int
    total_storage_bytes: int


@router.get("/users", response_model=List[AdminUserSummary])
async def list_users_admin(current_admin: UserPublic = Depends(get_current_admin)):
    db = get_database()
    overview = await fetch_user_overview(db)
    return [AdminUserSummary(**item) for item in overview]


@router.get("/documents", response_model=List[AdminDocumentSummary])
async def list_documents_admin(current_admin: UserPublic = Depends(get_current_admin)):
    db = get_database()
    docs = await fetch_document_overview(db)
    return [AdminDocumentSummary(**doc) for doc in docs]


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(current_admin: UserPublic = Depends(get_current_admin)):
    db = get_database()
    stats = await fetch_system_stats(db)
    return AdminStats(**stats)


class UserCreateRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    is_admin: bool = False


class UserUpdateRequest(BaseModel):
    email: str | None = None
    password: str | None = None
    full_name: str | None = None
    is_admin: bool | None = None


@router.post("/users", response_model=UserPublic)
async def create_user_admin(
    payload: UserCreateRequest,
    current_admin: UserPublic = Depends(get_current_admin)
):
    """Create a new user (admin only)"""
    db = get_database()
    
    # Check if email already exists
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = await create_user(
        db,
        payload.email,
        hash_password(payload.password),
        payload.full_name,
        is_admin=payload.is_admin,
    )
    
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_admin=user.is_admin
    )


@router.put("/users/{user_id}", response_model=UserPublic)
async def update_user_admin(
    user_id: str,
    payload: UserUpdateRequest,
    current_admin: UserPublic = Depends(get_current_admin)
):
    """Update a user (admin only)"""
    db = get_database()
    
    # Get user to update
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from removing their own admin status
    if user.id == current_admin.id and payload.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin privileges"
        )
    
    # Check if email is being changed and already exists
    if payload.email and payload.email != user.email:
        existing = await get_user_by_email(db, payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Build update dict
    update_data = {}
    if payload.email is not None:
        update_data["email"] = payload.email
    if payload.password is not None:
        update_data["hashed_password"] = hash_password(payload.password)
    if payload.full_name is not None:
        update_data["full_name"] = payload.full_name
    if payload.is_admin is not None:
        update_data["is_admin"] = payload.is_admin
    
    # Update user
    from bson import ObjectId
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )
    
    await db["users"].update_one(
        {"_id": oid},
        {"$set": update_data}
    )
    
    # Fetch updated user
    updated_user = await get_user_by_id(db, user_id)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch updated user"
        )
    
    return UserPublic(
        id=updated_user.id,
        email=updated_user.email,
        full_name=updated_user.full_name,
        is_admin=updated_user.is_admin
    )


@router.delete("/users/{user_id}")
async def delete_user_admin(
    user_id: str,
    current_admin: UserPublic = Depends(get_current_admin)
):
    """Delete a user (admin only)"""
    db = get_database()
    
    # Get user to delete
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deleting themselves
    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Delete user
    from bson import ObjectId
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID"
        )
    
    result = await db["users"].delete_one({"_id": oid})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )
    
    return {"message": "User deleted successfully"}

