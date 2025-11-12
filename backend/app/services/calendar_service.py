from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime
from typing import Any, Optional

from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..core.config import settings
from ..models.calendar_event import (
    delete_calendar_event,
    list_calendar_events,
    upsert_calendar_event,
)
from ..models.user import (
    clear_user_calendar_credentials,
    get_user_calendar_token,
    set_user_calendar_credentials,
)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class CalendarServiceError(Exception):
    """Raised when Google Calendar integration encounters a recoverable error."""


class CalendarService:
    def __init__(self, db):
        self.db = db
        if not settings.google_client_id or not settings.google_client_secret:
            raise CalendarServiceError("Google Calendar credentials are not configured.")
        if not settings.google_redirect_uri:
            raise CalendarServiceError("Google Calendar redirect URI is not configured.")

    # ------------------------------------------------------------------ #
    # Token encryption helpers
    # ------------------------------------------------------------------ #
    def _fernet(self) -> Fernet:
        secret = settings.calendar_token_secret or settings.jwt_secret_key
        key = base64.urlsafe_b64encode(secret.encode("utf-8"))
        if len(key) != 44:
            # Fernet expects 32-byte raw key before base64 (44 chars after)
            digest = hashlib.sha256(secret.encode("utf-8")).digest()
            key = base64.urlsafe_b64encode(digest)
        return Fernet(key)

    def _encrypt(self, payload: dict[str, Any]) -> str:
        data = json.dumps(payload).encode("utf-8")
        return self._fernet().encrypt(data).decode("utf-8")

    def _decrypt(self, token: str) -> dict[str, Any]:
        data = self._fernet().decrypt(token.encode("utf-8"))
        return json.loads(data.decode("utf-8"))

    # ------------------------------------------------------------------ #
    # OAuth Flow helpers
    # ------------------------------------------------------------------ #
    def _build_flow(self, state: Optional[str] = None) -> Flow:
        client_config = {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=SCOPES,
            state=state,
        )
        flow.redirect_uri = settings.google_redirect_uri
        return flow

    def _generate_state_token(self, user_id: str) -> str:
        payload = {
            "user_id": user_id,
            "nonce": secrets.token_urlsafe(8),
            "ts": datetime.utcnow().timestamp(),
        }
        return self._encrypt(payload)

    def _parse_state_token(self, state: str) -> str:
        payload = self._decrypt(state)
        user_id = payload.get("user_id")
        if not user_id:
            raise CalendarServiceError("Invalid OAuth state payload.")
        return user_id

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def generate_authorization_url(self, user_id: str) -> str:
        state = self._generate_state_token(user_id)
        flow = self._build_flow(state)
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        return auth_url

    async def handle_oauth_callback(self, code: str, state: str) -> str:
        user_id = self._parse_state_token(state)
        flow = self._build_flow(state)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        if not credentials or not credentials.refresh_token:
            raise CalendarServiceError("Failed to obtain Google Calendar credentials.")

        token_payload = json.loads(credentials.to_json())
        encrypted = self._encrypt(token_payload)
        await set_user_calendar_credentials(self.db, user_id, encrypted)
        return user_id

    async def disconnect_calendar(self, user_id: str) -> None:
        await clear_user_calendar_credentials(self.db, user_id)

    async def _load_credentials(self, user_id: str) -> Credentials:
        token = await get_user_calendar_token(self.db, user_id)
        if not token:
            raise CalendarServiceError("Google Calendar is not connected for this user.")
        payload = self._decrypt(token)
        credentials = Credentials.from_authorized_user_info(payload, SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            await self._persist_credentials(user_id, credentials)
        if not credentials.valid:
            raise CalendarServiceError("Google Calendar credentials are invalid.")
        return credentials

    async def _persist_credentials(self, user_id: str, credentials: Credentials) -> None:
        token_payload = json.loads(credentials.to_json())
        encrypted = self._encrypt(token_payload)
        await set_user_calendar_credentials(self.db, user_id, encrypted)

    async def get_calendar_service(self, user_id: str):
        credentials = await self._load_credentials(user_id)
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    async def create_event(
        self,
        user_id: str,
        summary: str,
        start_dt: datetime,
        end_dt: datetime,
        timezone: str,
        description: Optional[str] = None,
        reminders: Optional[list[dict[str, Any]]] = None,
        event_type: Optional[str] = None,
        question_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        service = await self.get_calendar_service(user_id)
        body: dict[str, Any] = {
            "summary": summary,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": timezone,
            },
        }
        if description:
            body["description"] = description
        if reminders is not None:
            body["reminders"] = {"useDefault": False, "overrides": reminders}

        try:
            event = service.events().insert(calendarId="primary", body=body).execute()
        except HttpError as exc:
            raise CalendarServiceError(f"Failed to create calendar event: {exc}") from exc

        await upsert_calendar_event(
            self.db,
            user_id=user_id,
            google_event_id=event["id"],
            summary=summary,
            start=start_dt,
            end=end_dt,
            timezone=timezone,
            description=description,
            event_type=event_type,
            question_id=question_id,
            document_ids=document_ids,
        )
        return event

    async def delete_event(self, user_id: str, event_id: str) -> None:
        service = await self.get_calendar_service(user_id)
        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
        except HttpError as exc:
            if exc.resp.status == 404:
                # Event already deleted; ignore
                pass
            else:
                raise CalendarServiceError(f"Failed to delete calendar event: {exc}") from exc
        await delete_calendar_event(self.db, user_id, event_id)

    async def list_events(
        self,
        user_id: str,
        max_results: int = 20,
        time_min: Optional[datetime] = None,
    ) -> dict[str, Any]:
        service = await self.get_calendar_service(user_id)
        params: dict[str, Any] = {
            "calendarId": "primary",
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_min:
            params["timeMin"] = time_min.isoformat() + "Z"

        try:
            events_result = service.events().list(**params).execute()
        except HttpError as exc:
            raise CalendarServiceError(f"Failed to list calendar events: {exc}") from exc

        stored = await list_calendar_events(self.db, user_id, limit=max_results)
        return {
            "google_events": events_result.get("items", []),
            "stored_events": [event.dict() for event in stored],
        }

