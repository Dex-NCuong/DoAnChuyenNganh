from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator

from ..core.config import settings
from ..core.database import get_database
from ..core.security import decode_token
from ..models.user import UserPublic, get_user_by_id
from ..services.calendar_service import CalendarService, CalendarServiceError

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
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_admin=user.is_admin,
    )


class ReminderSetting(BaseModel):
    method: str
    minutes: int = Field(ge=0, le=40320)  # up to 4 weeks

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        if value not in {"popup", "email"}:
            raise ValueError("method must be either 'popup' or 'email'")
        return value


class CalendarEventPayload(BaseModel):
    summary: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime
    timezone: str = Field(default="Asia/Ho_Chi_Minh", min_length=2, max_length=64)
    description: Optional[str] = Field(default=None, max_length=4000)
    reminders: Optional[list[ReminderSetting]] = None
    event_type: Optional[str] = Field(default=None, max_length=50)
    question_id: Optional[str] = None
    document_ids: Optional[list[str]] = None

    @field_validator("end")
    @classmethod
    def validate_time(cls, end_value: datetime, info):
        start = info.data.get("start")
        if start and end_value <= start:
            raise ValueError("End time must be after start time")
        return end_value


@router.get("/connect")
async def start_calendar_connect(current_user: UserPublic = Depends(get_current_user)):
    db = get_database()
    service = CalendarService(db)
    try:
        url = await service.generate_authorization_url(current_user.id)
    except CalendarServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"authorization_url": url}


@router.get("/oauth/callback")
async def calendar_oauth_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
):
    db = get_database()
    service = CalendarService(db)

    if error:
        failure_url = f"{settings.calendar_failure_redirect}?reason={quote_plus(error)}"
        return RedirectResponse(url=failure_url, status_code=status.HTTP_302_FOUND)

    if not code or not state:
        failure_url = f"{settings.calendar_failure_redirect}?reason=missing_code"
        return RedirectResponse(url=failure_url, status_code=status.HTTP_302_FOUND)

    try:
        await service.handle_oauth_callback(code, state)
    except CalendarServiceError as exc:
        failure_url = f"{settings.calendar_failure_redirect}?reason={quote_plus(str(exc))}"
        return RedirectResponse(url=failure_url, status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url=settings.calendar_success_redirect, status_code=status.HTTP_302_FOUND)


@router.get("/status")
async def calendar_status(current_user: UserPublic = Depends(get_current_user)):
    db = get_database()
    user = await get_user_by_id(db, current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return {
        "connected": bool(user.google_calendar_connected and user.google_calendar_token),
        "connected_at": user.calendar_connected_at,
    }


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_calendar(current_user: UserPublic = Depends(get_current_user)):
    db = get_database()
    service = CalendarService(db)
    try:
        await service.disconnect_calendar(current_user.id)
    except CalendarServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return None


@router.post("/events")
async def create_calendar_event(
    payload: CalendarEventPayload,
    current_user: UserPublic = Depends(get_current_user),
):
    db = get_database()
    service = CalendarService(db)
    try:
        result = await service.create_event(
            user_id=current_user.id,
            summary=payload.summary,
            start_dt=payload.start,
            end_dt=payload.end,
            timezone=payload.timezone,
            description=payload.description,
            reminders=[rem.model_dump() for rem in payload.reminders] if payload.reminders else None,
            event_type=payload.event_type,
            question_id=payload.question_id,
            document_ids=payload.document_ids,
        )
    except CalendarServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.get("/events")
async def list_calendar_events(
    max_results: int = Query(default=10, ge=1, le=50),
    time_min: Optional[datetime] = Query(default=None),
    current_user: UserPublic = Depends(get_current_user),
):
    db = get_database()
    service = CalendarService(db)
    try:
        result = await service.list_events(
            user_id=current_user.id,
            max_results=max_results,
            time_min=time_min,
        )
    except CalendarServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar_event_route(
    event_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    db = get_database()
    service = CalendarService(db)
    try:
        await service.delete_event(current_user.id, event_id)
    except CalendarServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return None

