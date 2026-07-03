"""
Session Manager
===============
Handles saving, loading and validation of Telethon StringSessions.
Sessions are stored encrypted in the database via the infrastructure layer.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------
# The encryption key is derived from SESSION_SECRET env var (or a project
# fallback).  In production this MUST be set to a strong random 32-byte
# URL-safe base64 string (``Fernet.generate_key().decode()``).
# ---------------------------------------------------------------------------


def _get_fernet() -> Fernet:
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret:
        # Generate a deterministic key from a known string so that existing
        # sessions survive restarts even without an env var (not recommended
        # for production, but safe enough for development).
        from hashlib import sha256
        raw = sha256(b"telegram_ai_assistant_session_key_fallback").digest()
        secret = base64.urlsafe_b64encode(raw).decode()
        logger.warning(
            "SESSION_SECRET not set — using fallback key. "
            "Set SESSION_SECRET in your environment for production!"
        )
    # Fernet requires a 32-byte URL-safe base64 key (44 chars).
    # If the secret is longer/shorter we normalise it.
    raw_bytes = base64.urlsafe_b64decode(secret + "==")[:32]
    raw_bytes = raw_bytes.ljust(32, b"\x00")
    key = base64.urlsafe_b64encode(raw_bytes)
    return Fernet(key)


def _encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string and return base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> Optional[str]:
    """Decrypt a base64-encoded ciphertext string.  Returns ``None`` on failure."""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception) as exc:
        logger.error("Failed to decrypt session string — %s", exc)
        return None


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------


class SessionManager:
    """
    Manages Telethon StringSessions persisted in the database.

    The manager encrypts every session string before storing it so that a
    compromised database dump cannot be used to hijack user accounts.

    All public methods accept a ``db_manager`` parameter so the class works
    in both dependency-injected and direct-call contexts.
    """

    def __init__(self, db_manager=None) -> None:
        self._db = db_manager

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save_session(
        self,
        user_id: int,
        session_string: str,
        db_manager=None,
    ) -> None:
        """
        Encrypt and persist *session_string* for *user_id*.

        Parameters
        ----------
        user_id:
            The bot user's Telegram ID.
        session_string:
            A Telethon ``StringSession.save()`` value.
        db_manager:
            Optional override for the injected db_manager.
        """
        db = db_manager or self._db
        encrypted = _encrypt(session_string)
        try:
            await db.execute(
                """
                INSERT INTO telethon_sessions (user_id, session_string, created_at, updated_at)
                VALUES ($1, $2, NOW(), NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET session_string = $2, updated_at = NOW()
                """,
                user_id,
                encrypted,
            )
            logger.info("Session saved for user_id=%s", user_id)
        except Exception as exc:
            logger.error("Failed to save session for user_id=%s — %s", user_id, exc)
            raise

    async def load_session(
        self,
        user_id: int,
        db_manager=None,
    ) -> Optional[str]:
        """
        Load and decrypt the session string for *user_id*.

        Returns ``None`` if no session exists or decryption fails.
        """
        db = db_manager or self._db
        try:
            row = await db.fetchrow(
                "SELECT session_string FROM telethon_sessions WHERE user_id = $1",
                user_id,
            )
            if row is None:
                logger.debug("No session found for user_id=%s", user_id)
                return None
            decrypted = _decrypt(row["session_string"])
            if decrypted is None:
                logger.warning("Session for user_id=%s failed to decrypt", user_id)
                return None
            return decrypted
        except Exception as exc:
            logger.error("Failed to load session for user_id=%s — %s", user_id, exc)
            return None

    async def delete_session(
        self,
        user_id: int,
        db_manager=None,
    ) -> None:
        """Delete the stored session for *user_id*."""
        db = db_manager or self._db
        try:
            await db.execute(
                "DELETE FROM telethon_sessions WHERE user_id = $1",
                user_id,
            )
            logger.info("Session deleted for user_id=%s", user_id)
        except Exception as exc:
            logger.error("Failed to delete session for user_id=%s — %s", user_id, exc)
            raise

    async def has_session(self, user_id: int, db_manager=None) -> bool:
        """Return ``True`` if a session record exists for *user_id*."""
        db = db_manager or self._db
        try:
            row = await db.fetchrow(
                "SELECT 1 FROM telethon_sessions WHERE user_id = $1",
                user_id,
            )
            return row is not None
        except Exception as exc:
            logger.error("Failed to check session for user_id=%s — %s", user_id, exc)
            return False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def is_valid_session(self, session_string: str) -> bool:
        """
        Check whether *session_string* represents a plausible Telethon session.

        This is a lightweight syntactic check; it does **not** make a network
        request.  Use ``TelethonAuthHandler.check_account_status()`` for a
        live authorisation check.
        """
        if not session_string or not isinstance(session_string, str):
            return False
        # Telethon StringSession strings are base64-encoded and typically
        # start with a version byte encoded as a number followed by content.
        try:
            # Attempt to reconstruct a StringSession — if it raises the
            # string is invalid.
            from telethon.sessions import StringSession

            ss = StringSession(session_string)
            # A valid session has at least a dc_id saved
            return ss.dc_id is not None and ss.dc_id > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def get_all_user_ids_with_sessions(self, db_manager=None) -> list[int]:
        """Return a list of every user_id that has a stored session."""
        db = db_manager or self._db
        try:
            rows = await db.fetch("SELECT user_id FROM telethon_sessions")
            return [row["user_id"] for row in rows]
        except Exception as exc:
            logger.error("Failed to list session user IDs — %s", exc)
            return []
