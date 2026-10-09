"""JWT authentication and role-based access control (RBAC)."""
from __future__ import annotations
import hashlib, hmac, os, time
from typing import Callable
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import settings

ROLES = ("administrator", "operations", "sustainability")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
    return hmac.compare_digest(check.hex(), digest_hex)


def create_token(username: str, role: str, name: str) -> str:
    payload = {"sub": username, "role": role, "name": name, "exp": int(time.time()) + settings.jwt_minutes * 60}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def require_roles(*roles: str) -> Callable:
    def dep(user: dict = Depends(current_user)) -> dict:
        if roles and user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user['role']}' cannot perform this action")
        return user
    return dep
