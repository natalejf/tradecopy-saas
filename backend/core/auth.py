"""
Authentication: JWT tokens + API keys
"""
import os
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.environ.get("JWT_SECRET", "change-me-in-production-super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days

security = HTTPBearer()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, h = password_hash.split(":")
        return hashlib.sha256((password + salt).encode()).hexdigest() == h
    except Exception:
        return False


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM
    )


def verify_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "email": payload["email"]}
    except Exception:
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    from core.database import Database
    token = credentials.credentials
    user = verify_token(token)
    if not user:
        # Try API key
        db = Database()
        user_row = db.get_user_by_api_key(token)
        if user_row:
            return user_row
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # Fetch full user
    db = Database()
    full_user = db.get_user_by_id(user["id"])
    if not full_user or not full_user["active"]:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return full_user
