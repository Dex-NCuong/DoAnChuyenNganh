from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from ..core.database import get_database
from ..core.security import decode_token
from ..models.user import get_user_by_id, UserPublic
from ..models.history import HistoryPublic, list_history_by_user, HistoryReference
from ..services.rag import rag_service


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


class AskRequest(BaseModel):
    question: str
    document_id: Optional[str] = None
    conversation_id: Optional[str] = None  # To group Q&As in the same conversation
    # top_k removed - now auto-calculated based on context length


class AskResponse(BaseModel):
    answer: str
    references: List[HistoryReference]
    documents: List[str]
    conversation_id: Optional[str] = None
    history_id: Optional[str] = None


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest, current_user: UserPublic = Depends(get_current_user)):
    db = get_database()
    try:
        result = await rag_service.ask(
            db=db,
            user_id=current_user.id,
            question=payload.question,
            document_id=payload.document_id,
            conversation_id=payload.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        # Catch any other exceptions and return proper error response with CORS headers
        error_msg = str(exc)
        print(f"[Query] Error in ask_question: {error_msg}")
        import traceback
        print(f"[Query] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý câu hỏi: {error_msg}"
        )

    return AskResponse(
        answer=result["answer"],
        references=result["references"],
        documents=result.get("documents", []),
        conversation_id=result.get("conversation_id"),
        history_id=result.get("history_id"),
    )


@router.get("/history", response_model=List[HistoryPublic])
async def get_history(
    document_id: Optional[str] = None,
    limit: int = 20,
    current_user: UserPublic = Depends(get_current_user),
):
    db = get_database()
    records = await list_history_by_user(
        db=db,
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


