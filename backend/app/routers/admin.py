from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from ..core.database import get_database
from ..core.security import decode_token
from ..models.user import get_user_by_id, UserPublic
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

