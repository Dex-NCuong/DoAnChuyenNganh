from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..core.database import get_database
from ..core.security import decode_token
from ..models.user import get_user_by_id, UserPublic
from ..models.history import (
    HistoryPublic,
    list_history_by_user,
    delete_history_record,
    clear_history_for_document,
    clear_history_for_user,
    delete_history_by_conversation,
)


router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    db = get_database()
    user = await get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name)


@router.get("/", response_model=List[HistoryPublic])
async def list_history(
    limit: int = 20,
    document_id: Optional[str] = None,
    current_user: UserPublic = Depends(get_current_user),
):
    db = get_database()
    records = await list_history_by_user(
        db,
        user_id=current_user.id,
        limit=min(max(limit, 1), 100),
        document_id=document_id,
    )
    return [
        HistoryPublic(
            id=record.id,
            user_id=record.user_id,
            question=record.question,
            answer=record.answer,
            references=record.references,
            document_id=record.document_id,
            conversation_id=record.conversation_id,
            created_at=record.created_at,
        )
        for record in records
    ]


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(
    history_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    db = get_database()
    deleted = await delete_history_record(db, current_user.id, history_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History not found")
    return None


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_by_document(
    document_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    db = get_database()
    await clear_history_for_document(db, current_user.id, document_id)
    return None


@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_history(current_user: UserPublic = Depends(get_current_user)):
    db = get_database()
    await clear_history_for_user(db, current_user.id)
    return None


@router.delete("/conversation/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """Delete all history records in a conversation (identified by conversation_id)."""
    db = get_database()
    deleted_count = await delete_history_by_conversation(
        db, current_user.id, conversation_id
    )
    if deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or already deleted"
        )
    return None


