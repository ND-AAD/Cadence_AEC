"""Auth schemas for registration and login."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    invite_code: str = Field(..., min_length=1, description="Shared alpha invite code")
