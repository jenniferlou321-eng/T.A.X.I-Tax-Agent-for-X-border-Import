"""用户管理路由（Demo: 简化占位）"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


@router.post("/register")
async def register(req: RegisterRequest):
    return {"message": "Registration placeholder", "user_id": "demo-user-1"}


@router.post("/login")
async def login(req: LoginRequest):
    return {"message": "Login placeholder", "token": "demo-token"}


@router.get("/me")
async def get_me():
    return {
        "user_id": "demo-user-1",
        "name": "Demo User",
        "email": "demo@example.com",
    }