from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class QuizQuestion(BaseModel):
    """Single quiz question"""
    question_type: str  # "multiple_choice" or "true_false"
    question_text: str
    options: List[str]  # For multiple_choice: 4 options, for true_false: ["Đúng", "Sai"]
    correct_answer: str  # The correct option text
    explanation: str  # Explanation why this is correct
    section: Optional[str] = None  # Which section/chapter this question is from
    difficulty: Optional[str] = "medium"  # "easy", "medium", "hard"


class QuizInDB(BaseModel):
    """Quiz stored in database"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    document_id: str
    document_filename: str
    title: str
    questions: List[QuizQuestion]
    total_questions: int
    difficulty: str  # Overall difficulty
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


class QuizPublic(BaseModel):
    """Quiz data for API response"""
    id: str
    user_id: str
    document_id: str
    document_filename: str
    title: str
    questions: List[QuizQuestion]
    total_questions: int
    difficulty: str
    created_at: datetime


class QuizAttemptAnswer(BaseModel):
    """User's answer for one question"""
    question_index: int
    user_answer: str
    is_correct: bool
    time_spent: Optional[int] = None  # seconds spent on this question


class QuizAttemptInDB(BaseModel):
    """Quiz attempt/result stored in database"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    quiz_id: str
    mode: str  # "practice" or "test"
    answers: List[QuizAttemptAnswer]
    score: int  # Number of correct answers
    total_questions: int
    percentage: float  # Score percentage
    time_taken: Optional[int] = None  # Total time in seconds (for test mode)
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


class QuizAttemptPublic(BaseModel):
    """Quiz attempt data for API response"""
    id: str
    user_id: str
    quiz_id: str
    mode: str
    answers: List[QuizAttemptAnswer]
    score: int
    total_questions: int
    percentage: float
    time_taken: Optional[int] = None
    completed_at: datetime


# Database operations

async def create_quiz(
    db: AsyncIOMotorDatabase,
    user_id: str,
    document_id: str,
    document_filename: str,
    title: str,
    questions: List[QuizQuestion],
    difficulty: str,
) -> QuizInDB:
    """Create a new quiz"""
    # Don't use Field(default_factory) - create ID manually
    from bson import ObjectId
    quiz_id = str(ObjectId())
    
    quiz_dict = {
        "_id": ObjectId(quiz_id),
        "user_id": user_id,
        "document_id": document_id,
        "document_filename": document_filename,
        "title": title,
        "questions": [q.model_dump() for q in questions],
        "total_questions": len(questions),
        "difficulty": difficulty,
        "created_at": datetime.utcnow(),
    }
    
    print(f"[Quiz Model] Creating quiz with ID: {quiz_id}")
    result = await db["quizzes"].insert_one(quiz_dict)
    print(f"[Quiz Model] ✅ Quiz inserted, ObjectId: {result.inserted_id}")
    
    # Build QuizInDB object for return
    quiz = QuizInDB(
        id=quiz_id,
        user_id=user_id,
        document_id=document_id,
        document_filename=document_filename,
        title=title,
        questions=questions,
        total_questions=len(questions),
        difficulty=difficulty,
        created_at=quiz_dict["created_at"],
    )
    
    return quiz


async def get_quiz_by_id(db: AsyncIOMotorDatabase, quiz_id: str) -> Optional[QuizInDB]:
    """Get quiz by ID"""
    print(f"[Quiz Model] Looking for quiz with ID: {quiz_id}")
    
    try:
        from bson import ObjectId
        doc = await db["quizzes"].find_one({"_id": ObjectId(quiz_id)})
        print(f"[Quiz Model] Found quiz: {doc is not None}")
    except Exception as e:
        print(f"[Quiz Model] Error finding quiz with ObjectId: {e}")
        doc = await db["quizzes"].find_one({"_id": quiz_id})
        print(f"[Quiz Model] Found quiz with string ID: {doc is not None}")
    
    if not doc:
        print(f"[Quiz Model] ❌ Quiz {quiz_id} not found in database")
        return None
    
    doc["id"] = str(doc.pop("_id"))
    print(f"[Quiz Model] ✅ Returning quiz: {doc['id']}")
    return QuizInDB(**doc)


async def list_quizzes_by_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    document_id: Optional[str] = None,
    limit: int = 20,
) -> List[QuizInDB]:
    """List quizzes by user, optionally filtered by document"""
    query = {"user_id": user_id}
    if document_id:
        query["document_id"] = document_id
    
    cursor = db["quizzes"].find(query).sort("created_at", -1).limit(limit)
    quizzes = []
    
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        quizzes.append(QuizInDB(**doc))
    
    return quizzes


async def delete_quiz(db: AsyncIOMotorDatabase, user_id: str, quiz_id: str) -> bool:
    """Delete a quiz"""
    try:
        from bson import ObjectId
        result = await db["quizzes"].delete_one(
            {"_id": ObjectId(quiz_id), "user_id": user_id}
        )
    except Exception:
        result = await db["quizzes"].delete_one(
            {"_id": quiz_id, "user_id": user_id}
        )
    
    return result.deleted_count > 0


async def create_quiz_attempt(
    db: AsyncIOMotorDatabase,
    user_id: str,
    quiz_id: str,
    mode: str,
    answers: List[QuizAttemptAnswer],
    score: int,
    total_questions: int,
    time_taken: Optional[int] = None,
) -> QuizAttemptInDB:
    """Save quiz attempt/result"""
    percentage = (score / total_questions * 100) if total_questions > 0 else 0
    
    attempt = QuizAttemptInDB(
        user_id=user_id,
        quiz_id=quiz_id,
        mode=mode,
        answers=answers,
        score=score,
        total_questions=total_questions,
        percentage=percentage,
        time_taken=time_taken,
    )
    
    attempt_dict = attempt.model_dump(by_alias=True)
    result = await db["quiz_attempts"].insert_one(attempt_dict)
    attempt.id = str(result.inserted_id)
    return attempt


async def list_quiz_attempts_by_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    quiz_id: Optional[str] = None,
    limit: int = 20,
) -> List[QuizAttemptInDB]:
    """List quiz attempts by user"""
    query = {"user_id": user_id}
    if quiz_id:
        query["quiz_id"] = quiz_id
    
    cursor = db["quiz_attempts"].find(query).sort("completed_at", -1).limit(limit)
    attempts = []
    
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        attempts.append(QuizAttemptInDB(**doc))
    
    return attempts

