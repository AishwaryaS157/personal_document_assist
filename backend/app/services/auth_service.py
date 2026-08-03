import os
import time

import bcrypt
import jwt

from app.database import get_supabase

JWT_ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
MIN_PASSWORD_LENGTH = 8


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])


def register_user(email: str, password: str) -> dict:
    email = _normalize_email(email)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    supabase = get_supabase()
    existing = supabase.table("users").select("id").eq("email", email).execute()
    if existing.data:
        raise DuplicateEmailError("An account with this email already exists")

    try:
        result = supabase.table("users").insert({
            "email": email,
            "password_hash": hash_password(password),
        }).execute()
    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise DuplicateEmailError("An account with this email already exists")
        raise

    user = result.data[0]
    return {"id": user["id"], "email": user["email"]}


def authenticate_user(email: str, password: str) -> dict:
    email = _normalize_email(email)
    supabase = get_supabase()
    result = supabase.table("users").select("id, email, password_hash").eq("email", email).execute()
    if not result.data or not verify_password(password, result.data[0]["password_hash"]):
        raise InvalidCredentialsError("Invalid email or password")

    user = result.data[0]
    return {"id": user["id"], "email": user["email"]}
