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
    document_ids: Optional[List[str]] = None  # ← THAY ĐỔI: List thay vì single str
    conversation_id: Optional[str] = None
    
    # BACKWARD COMPATIBILITY: Vẫn accept document_id (single) cho old clients
    document_id: Optional[str] = None
    
    class Config:
        # Example payload
        json_schema_extra = {  # ← FIX: Pydantic V2 uses json_schema_extra instead of schema_extra
            "example": {
                "question": "So sánh let và var trong JavaScript",
                "document_ids": ["doc_id_1", "doc_id_2"],  # Chọn 2 files
                "conversation_id": None
            }
        }


class AskResponse(BaseModel):
    answer: str
    references: List[HistoryReference]
    documents: List[str]  # IDs của documents có references
    documents_searched: List[str]  # ← THÊM: IDs của documents đã search
    conversation_id: Optional[str] = None
    history_id: Optional[str] = None


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest, current_user: UserPublic = Depends(get_current_user)):
    db = get_database()
    
    # ===== BACKWARD COMPATIBILITY LAYER =====
    # Nếu client gửi document_id (single), convert thành list
    document_ids_to_use = payload.document_ids
    if not document_ids_to_use and payload.document_id:
        document_ids_to_use = [payload.document_id]
        print(f"[Query] Converted single document_id to list: {document_ids_to_use}")
    
    # ===== VALIDATION =====
    # CRITICAL: Frontend validation đã có, nhưng backend cũng nên check
    if not document_ids_to_use or len(document_ids_to_use) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất 1 tài liệu"
        )
    
    # Check limit: tối đa 5 documents cùng lúc (để tránh overload)
    if len(document_ids_to_use) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ có thể chọn tối đa 5 tài liệu (đã chọn: {len(document_ids_to_use)})"
        )
    
    print(f"[Query] Processing question with {len(document_ids_to_use)} document(s): {document_ids_to_use}")
    
    try:
        result = await rag_service.ask(
            db=db,
            user_id=current_user.id,
            question=payload.question,
            document_ids=document_ids_to_use,  # ← THAY ĐỔI: Pass list
            conversation_id=payload.conversation_id,
        )
    except ValueError as exc:
        # ValueError from RAG service (e.g., document not found)
        error_msg = str(exc)
        print(f"[Query] ValueError: {error_msg}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    except Exception as exc:
        # Catch any other exceptions
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
        documents=result.get("documents", []),  # Documents có references
        documents_searched=result.get("documents_searched", document_ids_to_use),  # ← THÊM
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


