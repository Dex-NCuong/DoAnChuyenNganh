from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from ..core.config import settings
from ..core.database import get_database
from ..core.security import hash_password, verify_password, create_access_token, decode_token
from ..models.user import UserInCreate, UserPublic, get_user_by_email, create_user, get_user_by_id


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False


class LoginJSON(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", response_model=UserPublic)
async def register(payload: UserInCreate):
    db = get_database()
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    is_admin = payload.email.lower() in settings.admin_emails
    user = await create_user(
        db,
        payload.email,
        hash_password(payload.password),
        payload.full_name,
        is_admin=is_admin,
    )
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name, is_admin=user.is_admin)


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = get_database()
    user = await get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(user.id)
    return Token(access_token=token, is_admin=user.is_admin)


@router.post("/login-json", response_model=Token)
async def login_json(payload: LoginJSON):
    db = get_database()
    user = await get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(user.id)
    return Token(access_token=token, is_admin=user.is_admin)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    db = get_database()
    user = await get_user_by_id(db, payload["sub"])  # fetch real user
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name, is_admin=user.is_admin)


@router.get("/me", response_model=UserPublic)
async def me(current_user: UserPublic = Depends(get_current_user)):
    return current_user


