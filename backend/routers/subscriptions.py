"""Subscriptions & Auth router"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from core.auth import hash_password, verify_password, create_access_token, get_current_user
from core.database import Database

router = APIRouter()
db = Database()


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/register")
async def register(data: RegisterRequest):
    existing = db.get_user_by_email(data.email)
    if existing:
        raise HTTPException(400, "Email already registered")
    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    user_id = db.create_user(data.email, hash_password(data.password), data.full_name)
    user = db.get_user_by_id(user_id)
    token = create_access_token(user_id, data.email)
    return {"token": token, "user": {
        "id": user["id"], "email": user["email"],
        "full_name": user["full_name"], "plan": user["plan"],
        "api_key": user["api_key"]
    }}


@router.post("/login")
async def login(data: LoginRequest):
    user = db.get_user_by_email(data.email)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    if not user["active"]:
        raise HTTPException(403, "Account is disabled")
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": {
        "id": user["id"], "email": user["email"],
        "full_name": user["full_name"], "plan": user["plan"],
        "api_key": user["api_key"]
    }}


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "plan": current_user["plan"],
        "plan_expires_at": current_user.get("plan_expires_at"),
        "api_key": current_user["api_key"],
    }


@router.get("/plans")
async def get_plans():
    return [
        {"id": "free", "name": "Free", "price": 0, "accounts": 2, "features": ["2 accounts", "Basic support"]},
        {"id": "starter", "name": "Starter", "price": 19, "accounts": 5, "features": ["5 accounts", "Email support", "Symbol mapping"]},
        {"id": "pro", "name": "Pro", "price": 49, "accounts": 20, "features": ["20 accounts", "Priority support", "Advanced settings", "API access"]},
        {"id": "enterprise", "name": "Enterprise", "price": 149, "accounts": 999, "features": ["Unlimited accounts", "Dedicated support", "Custom features"]},
    ]
