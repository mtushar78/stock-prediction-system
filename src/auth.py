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
    """Create the users table if missing (idempotent)."""
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_user(row) -> Optional[Dict]:
    if not row:
        return None
    return {"id": row[0], "email": row[1], "password_hash": row[2]}


def get_user_by_email(email: str) -> Optional[Dict]:
    # This runs on the per-request auth path, so the connection MUST be released
    # on every path (QueuePool would otherwise leak on any DB error and exhaust).
    db = DatabaseManager()
    try:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash FROM users WHERE email = %s",
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
            "SELECT id, email, password_hash FROM users WHERE id = %s",
            (user_id,),
        )
        return _row_to_user(cur.fetchone())
    finally:
        db.close()


def create_user(email: str, password: str) -> Dict:
    """Create a user. Raises ValueError if the email already exists."""
    ensure_users_table()
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid email is required")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters")
    if get_user_by_email(email):
        raise ValueError(f"User {email} already exists")

    db = DatabaseManager()
    conn = db.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, hash_password(password)),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    logger.info("Created user %s (id=%s)", email, new_id)
    return {"id": new_id, "email": email}


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "email": user["email"]}


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(user: Dict) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "iat": now,
        "exp": now + datetime.timedelta(days=JWT_EXPIRE_DAYS),
    }
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

    request.state.user = {"id": user_id, "email": payload.get("email")}


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
