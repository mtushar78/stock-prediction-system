"""
Authentication for DSE Sniper.

JWT bearer-token auth over the existing SQLite DB. A single ``users`` table
holds credentials (bcrypt-hashed). The API is protected globally via the
``authenticate`` dependency wired into the FastAPI app; portfolio endpoints
additionally read the caller's id via ``current_user_id`` to scope data.

This is a closed system: there is no public registration endpoint. Users are
created out-of-band with ``backend/create_user.py`` (or the auth migration).
"""

import os
import datetime
import logging
from typing import Optional, Dict

import jwt
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

try:  # works whether imported as ``src.auth`` or with ``src`` on sys.path
    from db_manager import DatabaseManager
except ImportError:  # pragma: no cover
    from src.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get(
    "JWT_SECRET",
    # Dev fallback only. Set JWT_SECRET in .env for production — rotating it
    # invalidates all issued tokens (forces re-login).
    "dse-sniper-dev-secret-change-me",
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

# The owner account is ALWAYS treated as admin, even if the DB flag is somehow
# missing (e.g. an old token, or before the migration ran). This is the account
# that can create users and impersonate.
OWNER_EMAIL = "mtushar78@gmail.com"

# auto_error=False so the global dependency can craft its own 401 and so the
# login route (which carries no token) doesn't get rejected by the extractor.
_bearer = HTTPBearer(auto_error=False)

# Paths that do NOT require authentication.
_PUBLIC_PATHS = {"/api/auth/login"}


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Users table + CRUD
# ---------------------------------------------------------------------------
def ensure_users_table() -> None:
    """Create the users table if missing + add the is_admin column (idempotent).

    Safe to call on every startup. It creates the table for a fresh install,
    back-fills the ``is_admin`` column on an older table that predates it, and
    guarantees the owner account is flagged admin.
    """
    db = DatabaseManager()
    conn = db.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Add is_admin to a pre-existing table that lacks it.
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if "is_admin" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        # The owner is always admin.
        cur.execute("UPDATE users SET is_admin = 1 WHERE lower(email) = ?", (OWNER_EMAIL,))
        conn.commit()
    finally:
        conn.close()


def is_admin_email(email: Optional[str], flag=0) -> bool:
    """Effective admin check: the DB flag OR the always-admin owner email."""
    return bool(flag) or (email or "").strip().lower() == OWNER_EMAIL


def _row_to_user(row) -> Optional[Dict]:
    if not row:
        return None
    flag = row[3] if len(row) > 3 else 0
    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "is_admin": is_admin_email(row[1], flag),
    }


def get_user_by_email(email: str) -> Optional[Dict]:
    # This runs on the per-request auth path, so the connection MUST be released
    # on every path (QueuePool would otherwise leak on any DB error and exhaust).
    db = DatabaseManager()
    try:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash, is_admin FROM users WHERE email = %s",
            ((email or "").strip().lower(),),
        )
        return _row_to_user(cur.fetchone())
    finally:
        db.close()


def get_user_by_id(user_id: int) -> Optional[Dict]:
    db = DatabaseManager()
    try:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash, is_admin FROM users WHERE id = %s",
            (user_id,),
        )
        return _row_to_user(cur.fetchone())
    finally:
        db.close()


def list_users() -> list:
    """Every user (id, email, is_admin, created_at) — for the admin console."""
    db = DatabaseManager()
    try:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT id, email, is_admin, created_at FROM users ORDER BY id"
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "email": r[1],
                "is_admin": is_admin_email(r[1], r[2]),
                "created_at": r[3],
            }
            for r in rows
        ]
    finally:
        db.close()


def create_user(email: str, password: str, is_admin: bool = False) -> Dict:
    """Create a user. Raises ValueError if the email already exists."""
    ensure_users_table()
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid email is required")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters")
    if get_user_by_email(email):
        raise ValueError(f"User {email} already exists")

    admin_flag = 1 if (is_admin or email == OWNER_EMAIL) else 0
    db = DatabaseManager()
    conn = db.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, ?)",
            (email, hash_password(password), admin_flag),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    logger.info("Created user %s (id=%s, admin=%s)", email, new_id, admin_flag)
    return {"id": new_id, "email": email, "is_admin": bool(admin_flag)}


def set_password(user_id: int, new_password: str) -> None:
    """Overwrite a user's password (admin reset or self-service change)."""
    if not new_password or len(new_password) < 4:
        raise ValueError("Password must be at least 4 characters")
    db = DatabaseManager()
    conn = db.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        if cur.rowcount == 0:
            raise ValueError("User not found")
        conn.commit()
    finally:
        conn.close()
    logger.info("Password changed for user id=%s", user_id)


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "email": user["email"], "is_admin": user["is_admin"]}


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(user: Dict, impersonator: Optional[Dict] = None) -> str:
    """Issue a JWT for ``user``.

    When ``impersonator`` is given (an admin acting as this user), its identity
    is embedded in the token so the API and UI can surface an impersonation
    banner even after a page reload — the effective identity is still ``user``.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "is_admin": bool(user.get("is_admin")),
        "iat": now,
        "exp": now + datetime.timedelta(days=JWT_EXPIRE_DAYS),
    }
    if impersonator:
        payload["imp_by_id"] = impersonator.get("id")
        payload["imp_by_email"] = impersonator.get("email")
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> Dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired, please log in again",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def authenticate(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    """Global dependency: every request must carry a valid bearer token.

    Exceptions: CORS preflight (OPTIONS) and the login route. The resolved
    user is stashed on ``request.state.user`` for downstream dependencies.
    """
    if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
        return

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_token(credentials.credentials)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    email = payload.get("email")
    impersonator = None
    if payload.get("imp_by_email"):
        impersonator = {
            "id": payload.get("imp_by_id"),
            "email": payload.get("imp_by_email"),
        }
    request.state.user = {
        "id": user_id,
        "email": email,
        # Trust the token flag, but the owner email is always admin regardless.
        "is_admin": is_admin_email(email, payload.get("is_admin")),
        "impersonator": impersonator,
    }


def current_user(request: Request) -> Dict:
    """Return the authenticated user dict stashed by ``authenticate``."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user


def current_user_id(request: Request) -> int:
    return current_user(request)["id"]


def require_admin(request: Request) -> Dict:
    """Dependency: reject non-admins with 403.

    NOTE: while impersonating, the effective identity is the impersonated
    (usually non-admin) user, so admin routes are correctly forbidden — admin
    actions must be taken from the admin's own session.
    """
    user = current_user(request)
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
