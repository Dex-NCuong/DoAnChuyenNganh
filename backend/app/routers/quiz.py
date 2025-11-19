from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from ..core.database import get_database
from ..core.security import decode_token
from ..models.user import get_user_by_id, UserPublic
from ..models.quiz import (
    QuizQuestion,
    QuizPublic,
    QuizAttemptPublic,
    QuizAttemptAnswer,
    create_quiz,
    get_quiz_by_id,
    list_quizzes_by_user,
    delete_quiz,
    create_quiz_attempt,
    list_quiz_attempts_by_user,
)
from ..services.quiz_generator import quiz_generator_service


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    db = get_database()
    user = await get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name)


class GenerateQuizRequest(BaseModel):
    document_id: str
    num_questions: int = 5
    difficulty: str = "medium"  # "easy", "medium", "hard"
    question_types: List[str] = ["multiple_choice", "true_false"]


class SubmitQuizRequest(BaseModel):
    quiz_id: str
    mode: str  # "practice" or "test"
    answers: List[QuizAttemptAnswer]
    time_taken: Optional[int] = None


@router.post("/generate", response_model=QuizPublic)
async def generate_quiz(
    payload: GenerateQuizRequest,
    current_user: UserPublic = Depends(get_current_user),
):
    """Generate quiz from document using AI"""
    db = get_database()
    
    try:
        # Validate inputs - số câu hỏi phải từ 1-3
        if payload.num_questions < 1 or payload.num_questions > 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số câu hỏi phải từ 1 đến 3 câu"
            )
        
        if payload.difficulty not in ["easy", "medium", "hard"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Độ khó phải là 'easy', 'medium', hoặc 'hard'"
            )
        
        # Generate questions using AI
        questions = await quiz_generator_service.generate_quiz(
            db=db,
            user_id=current_user.id,
            document_id=payload.document_id,
            num_questions=payload.num_questions,
            difficulty=payload.difficulty,
            question_types=payload.question_types,
        )
        
        if not questions:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Không thể tạo câu hỏi từ tài liệu này"
            )
        
        # Validate số câu hỏi được tạo ra phải từ 1-3
        if len(questions) < 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI không tạo được câu hỏi nào. Vui lòng thử lại hoặc chọn tài liệu khác."
            )
        
        if len(questions) > 3:
            # Giới hạn tối đa 3 câu
            original_count = len(questions)
            questions = questions[:3]
            print(f"[Quiz Router] ⚠️ Limited questions to 3 (was {original_count})")
        
        # Get document info
        from ..models.document import get_document_by_id
        doc = await get_document_by_id(db, payload.document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Create quiz
        print(f"[Quiz Router] Creating quiz with {len(questions)} questions")
        quiz = await create_quiz(
            db=db,
            user_id=current_user.id,
            document_id=payload.document_id,
            document_filename=doc.filename,
            title=f"Quiz: {doc.filename}",
            questions=questions,
            difficulty=payload.difficulty,
        )
        
        print(f"[Quiz Router] ✅ Quiz created with ID: {quiz.id}")
        
        return QuizPublic(
            id=quiz.id,
            user_id=quiz.user_id,
            document_id=quiz.document_id,
            document_filename=quiz.document_filename,
            title=quiz.title,
            questions=quiz.questions,
            total_questions=quiz.total_questions,
            difficulty=quiz.difficulty,
            created_at=quiz.created_at,
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        print(f"[Quiz] Error generating quiz: {e}")
        import traceback
        print(f"[Quiz] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo quiz: {str(e)}"
        )


@router.get("/", response_model=List[QuizPublic])
async def list_quizzes(
    document_id: Optional[str] = None,
    limit: int = 20,
    current_user: UserPublic = Depends(get_current_user),
):
    """List quizzes created by user"""
    db = get_database()
    
    quizzes = await list_quizzes_by_user(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        limit=min(max(limit, 1), 100),
    )
    
    return [
        QuizPublic(
            id=q.id,
            user_id=q.user_id,
            document_id=q.document_id,
            document_filename=q.document_filename,
            title=q.title,
            questions=q.questions,
            total_questions=q.total_questions,
            difficulty=q.difficulty,
            created_at=q.created_at,
        )
        for q in quizzes
    ]


@router.get("/{quiz_id}", response_model=QuizPublic)
async def get_quiz(
    quiz_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """Get quiz by ID"""
    print(f"[Quiz Router] GET request for quiz_id: {quiz_id}, user: {current_user.id}")
    db = get_database()
    
    quiz = await get_quiz_by_id(db, quiz_id)
    
    if not quiz:
        print(f"[Quiz Router] ❌ Quiz {quiz_id} not found in database")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    if quiz.user_id != current_user.id:
        print(f"[Quiz Router] ❌ Quiz {quiz_id} belongs to different user: {quiz.user_id} != {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    return QuizPublic(
        id=quiz.id,
        user_id=quiz.user_id,
        document_id=quiz.document_id,
        document_filename=quiz.document_filename,
        title=quiz.title,
        questions=quiz.questions,
        total_questions=quiz.total_questions,
        difficulty=quiz.difficulty,
        created_at=quiz.created_at,
    )


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz_endpoint(
    quiz_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """Delete a quiz"""
    db = get_database()
    
    deleted = await delete_quiz(db, current_user.id, quiz_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    return None


@router.post("/submit", response_model=QuizAttemptPublic)
async def submit_quiz(
    payload: SubmitQuizRequest,
    current_user: UserPublic = Depends(get_current_user),
):
    """Submit quiz attempt and get results"""
    db = get_database()
    
    # Get quiz to verify
    quiz = await get_quiz_by_id(db, payload.quiz_id)
    if not quiz or quiz.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    # Calculate score
    score = sum(1 for answer in payload.answers if answer.is_correct)
    
    # Save attempt
    attempt = await create_quiz_attempt(
        db=db,
        user_id=current_user.id,
        quiz_id=payload.quiz_id,
        mode=payload.mode,
        answers=payload.answers,
        score=score,
        total_questions=quiz.total_questions,
        time_taken=payload.time_taken,
    )
    
    return QuizAttemptPublic(
        id=attempt.id,
        user_id=attempt.user_id,
        quiz_id=attempt.quiz_id,
        mode=attempt.mode,
        answers=attempt.answers,
        score=attempt.score,
        total_questions=attempt.total_questions,
        percentage=attempt.percentage,
        time_taken=attempt.time_taken,
        completed_at=attempt.completed_at,
    )


@router.get("/attempts/history", response_model=List[QuizAttemptPublic])
async def list_quiz_attempts(
    quiz_id: Optional[str] = None,
    limit: int = 20,
    current_user: UserPublic = Depends(get_current_user),
):
    """List quiz attempts by user"""
    db = get_database()
    
    attempts = await list_quiz_attempts_by_user(
        db=db,
        user_id=current_user.id,
        quiz_id=quiz_id,
        limit=min(max(limit, 1), 100),
    )
    
    return [
        QuizAttemptPublic(
            id=a.id,
            user_id=a.user_id,
            quiz_id=a.quiz_id,
            mode=a.mode,
            answers=a.answers,
            score=a.score,
            total_questions=a.total_questions,
            percentage=a.percentage,
            time_taken=a.time_taken,
            completed_at=a.completed_at,
        )
        for a in attempts
    ]

