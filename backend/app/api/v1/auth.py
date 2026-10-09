from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ...core.security import verify_password, create_token, current_user
from ...db.models import User
from ...db.session import SessionLocal

router = APIRouter(prefix="/auth", tags=["auth"])
PERMISSIONS = {"administrator": ["view_all", "approve_actions", "edit_config", "ingest", "simulate"],
               "operations": ["view_ops", "update_actions", "ingest", "simulate"],
               "sustainability": ["view_sustainability", "update_actions", "export_reports"]}
HOME = {"administrator": "/", "operations": "/waste", "sustainability": "/scorecard"}


class Login(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: Login):
    with SessionLocal() as s:
        u = s.get(User, body.username)
    if u is None or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return {"token": create_token(u.username, u.role, u.name), "user": {"username": u.username, "name": u.name, "role": u.role,
            "permissions": PERMISSIONS[u.role], "home": HOME[u.role]}}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"username": user["sub"], "name": user["name"], "role": user["role"], "permissions": PERMISSIONS[user["role"]], "home": HOME[user["role"]]}
