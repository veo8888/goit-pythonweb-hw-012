from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class ContactBase(BaseModel):
    """Shared fields for contact schemas."""

    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    birthday: Optional[date] = None
    extra: Optional[str] = None


class ContactCreate(ContactBase):
    """Schema for creating new contact."""

    pass


class ContactUpdate(BaseModel):
    """Schema for updating contact (all fields optional)."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    birthday: Optional[date] = None
    extra: Optional[str] = None


class ContactOut(ContactBase):
    """Schema for returning contact with ID."""

    id: int

    class Config:
        orm_mode = True  # allow SQLAlchemy objects


class UserBase(BaseModel):
    """Shared fields for user schemas."""

    email: EmailStr


class UserCreate(UserBase):
    """Payload for creating a new user."""

    password: str = Field(min_length=6)
    role: str = "user"


class UserOut(UserBase):
    """Response schema for user data."""

    id: int
    is_verified: bool
    avatar_url: Optional[str] = None
    role: str = "user"

    class Config:
        orm_mode = True


class Token(BaseModel):
    """JWT token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for requesting a new access token from a refresh token."""

    refresh_token: str


class TokenData(BaseModel):
    """Payload stored inside JWT token."""

    sub: str | None = None
    exp: Optional[datetime] = None
    scope: Optional[str] = None


class EmailRequest(BaseModel):
    """Schema for verification email requests."""

    email: EmailStr


class PasswordResetRequest(BaseModel):
    """Request schema for initiating password reset."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Payload for completing password reset using token."""

    token: str
    new_password: str = Field(min_length=6)
