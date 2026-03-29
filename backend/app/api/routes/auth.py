"""Auth routes — login + current user."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_password, create_access_token, hash_password
from app.core.config import settings
from app.core.database import get_db
from app.models.infrastructure import User
from app.api.deps import get_current_user
from app.schemas.auth import RegisterRequest

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class UserInfo(BaseModel):
    id: str
    email: str
    name: str


class LoginResponse(BaseModel):
    token: str
    user: UserInfo


class UserResponse(BaseModel):
    id: str
    email: str
    name: str


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(str(user.id), user.email)
    return LoginResponse(
        token=token,
        user=UserInfo(id=str(user.id), email=user.email, name=user.name),
    )


@router.post("/register", response_model=LoginResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Validate invite code
    if payload.invite_code != settings.ALPHA_INVITE_CODE:
        raise HTTPException(status_code=403, detail="Invalid invite code")

    # Check for duplicate email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create user with hashed password
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Return immediate auth token
    token = create_access_token(str(user.id), user.email)
    return LoginResponse(
        token=token,
        user=UserInfo(id=str(user.id), email=user.email, name=user.name),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(id=str(user.id), email=user.email, name=user.name)
