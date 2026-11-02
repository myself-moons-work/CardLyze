"""In-memory session store ensuring zero disk persistence."""

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from fastapi import HTTPException, status
from app.config import settings


@dataclass
class SessionData:
    session_id: str
    created_at: float
    last_accessed_at: float
    coladd: Dict[str, Any] = field(default_factory=dict)
    analysis: Dict[str, Any] = field(default_factory=dict)

    def wipe(self) -> None:
        """Drop all references to in-memory datasets."""
        self.coladd.clear()
        self.analysis.clear()


class SessionStore:
    """Thread-safe, in-memory session store with TTL, capacity limits, and wipe capabilities."""

    def __init__(
        self,
        ttl_seconds: int = settings.SESSION_TTL_SECONDS,
        max_sessions: int = settings.MAX_CONCURRENT_SESSIONS,
        time_func: Callable[[], float] = time.time,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.time_func = time_func
        self._sessions: Dict[str, SessionData] = {}
        self._lock = threading.Lock()

    def sweep_expired(self) -> int:
        """Purge sessions that have exceeded the idle TTL. Returns count of purged sessions."""
        now = self.time_func()
        expired_ids = []
        with self._lock:
            for s_id, session in self._sessions.items():
                if now - session.last_accessed_at > self.ttl_seconds:
                    expired_ids.append(s_id)

            for s_id in expired_ids:
                session = self._sessions.pop(s_id, None)
                if session is not None:
                    session.wipe()

        return len(expired_ids)

    def create_session(self) -> str:
        """Create a new session. Raises HTTP 503 if max concurrent sessions reached."""
        self.sweep_expired()
        now = self.time_func()

        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Maximum concurrent sessions reached. Please try again later.",
                )

            session_id = secrets.token_urlsafe(32)
            session = SessionData(
                session_id=session_id,
                created_at=now,
                last_accessed_at=now,
            )
            self._sessions[session_id] = session
            return session_id

    def get_session(self, session_id: Optional[str], touch: bool = True) -> Optional[SessionData]:
        """Retrieve an active session by ID. Returns None if not found or expired."""
        if not session_id:
            return None

        now = self.time_func()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            if now - session.last_accessed_at > self.ttl_seconds:
                self._sessions.pop(session_id, None)
                session.wipe()
                return None

            if touch:
                session.last_accessed_at = now

            return session

    def delete_session(self, session_id: Optional[str]) -> bool:
        """Explicitly wipe and remove a session by ID."""
        if not session_id:
            return False

        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is not None:
                session.wipe()
                return True
            return False

    def active_session_count(self) -> int:
        """Return the number of currently active non-expired sessions."""
        self.sweep_expired()
        with self._lock:
            return len(self._sessions)

    def clear_all(self) -> None:
        """Wipe and clear all sessions (primarily for test cleanup)."""
        with self._lock:
            for session in self._sessions.values():
                session.wipe()
            self._sessions.clear()


# Default singleton session store
session_store = SessionStore()

