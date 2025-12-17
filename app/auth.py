"""Authentication and authorization related routes and helpers."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_mail import MessageSchema, FastMail
from jose import JWTError, jwt
import redis.asyncio as redis
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import schemas, crud
from .database import get_db
from .models import User
from .core import get_settings, get_mail_config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])


@dataclass
class CachedUser:
    """Serializable representation of a user stored in cache."""

    id: int
    email: str
    is_verified: bool
    avatar_url: str | None
    role: str
    hashed_password: str | None = None

    @classmethod
    def from_model(cls, user: User) -> "CachedUser":
        """
        Create a CachedUser instance from a User ORM model.

        Args:
            user (User): SQLAlchemy User model.

        Returns:
            CachedUser: Serializable cached user representation.
        """
        return cls(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            avatar_url=user.avatar_url,
            role=user.role,
            hashed_password=getattr(user, "hashed_password", None),
        )

    def to_model(self) -> User:
        """
        Convert cached user data back into a User ORM model.

        Returns:
            User: SQLAlchemy User instance populated from cache.
        """
        return User(
            id=self.id,
            email=self.email,
            hashed_password=self.hashed_password or "",
            is_verified=self.is_verified,
            avatar_url=self.avatar_url,
            role=self.role,
        )

    def to_json(self) -> str:
        """
        Serialize cached user data to JSON string.

        Returns:
            str: JSON representation of cached user.
        """
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, raw: str) -> "CachedUser":
        """
        Deserialize cached user from JSON string.

        Args:
            raw (str): JSON string with cached user data.

        Returns:
            CachedUser: Restored cached user object.
        """
        data: dict[str, Any] = json.loads(raw)
        return cls(**data)


class MemoryCache:
    """Simple in-memory cache used when Redis is unavailable."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        """
        Retrieve a value from in-memory cache.

        Args:
            key (str): Cache key.

        Returns:
            str | None: Cached value if present.
        """
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        """
        Store a value in in-memory cache.

        Args:
            key (str): Cache key.
            value (str): Value to store.
            ex (int | None): Expiration time in seconds (ignored).
        """
        self.store[key] = value


_cache_client: Any | None = None


async def get_cache_client():
    """
    Return a Redis client or an in-memory fallback cache.

    Returns:
        Redis | MemoryCache: Cache backend instance.
    """
    global _cache_client
    if _cache_client is not None:
        return _cache_client
    settings = get_settings()
    try:
        client = redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
        await client.ping()
        _cache_client = client
    except Exception:
        _cache_client = MemoryCache()
    return _cache_client


async def cache_user(user: User, expire_minutes: int | None = None):
    """
    Store user data in cache to reduce database access.

    Args:
        user (User): User ORM model.
        expire_minutes (int | None): Cache expiration time.
    """
    client = await get_cache_client()
    settings = get_settings()
    expires = expire_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    await client.set(
        f"user:{user.email}", CachedUser.from_model(user).to_json(), ex=expires * 60
    )


async def get_cached_user(email: str) -> User | None:
    """
    Retrieve user from cache if available.

    Args:
        email (str): User email.

    Returns:
        User | None: Cached user or None.
    """
    client = await get_cache_client()
    cached = await client.get(f"user:{email}")
    if cached:
        return CachedUser.from_json(cached).to_model()
    return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain password with its hashed value."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a password hash using the configured context."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict, expires_delta: timedelta | None = None, scope: str = "access"
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "scope": scope})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token with a longer lifetime."""
    settings = get_settings()
    return create_access_token(
        data,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
        scope="refresh",
    )


def create_password_reset_token(user: User) -> str:
    """Generate a short-lived password reset token for the user."""
    return create_access_token(
        {"sub": user.email}, expires_delta=timedelta(hours=1), scope="reset"
    )


def create_verification_token(user: User) -> str:
    """Generate verification JWT token for email confirmation."""
    return create_access_token(
        {"sub": user.email, "scope": "verification"}, expires_delta=timedelta(hours=24)
    )


def send_verification_email(background_tasks: BackgroundTasks, email: str, token: str):
    """Schedule sending of email verification message."""
    background_tasks.add_task(send_verification_email_task, email, token)


async def send_verification_email_task(email: str, token: str):
    """
    Send verification email asynchronously.

    Args:
        email (str): Recipient email address.
        token (str): Verification token.
    """
    settings = get_settings()
    verification_link = f"{settings.BASE_URL}/auth/verify?token={token}"
    message = MessageSchema(
        subject="Confirmation of registration",
        recipients=[email],
        body=f"""
        <html>
          <body>
            <h2>Welcome!</h2>
            <p>To confirm your registration, follow the link:</p>
            <a href="{verification_link}">Confirm email</a>
          </body>
        </html>
        """,
        subtype="html",
    )
    fm = FastMail(get_mail_config())
    try:
        await fm.send_message(message)
    except Exception:
        return


def send_password_reset_email(
    background_tasks: BackgroundTasks, email: str, token: str
):
    """Schedule sending password reset instructions."""
    background_tasks.add_task(send_password_reset_email_task, email, token)


async def send_password_reset_email_task(email: str, token: str):
    """
    Send password reset email asynchronously.

    Args:
        email (str): Recipient email.
        token (str): Password reset token.
    """
    settings = get_settings()
    reset_link = f"{settings.BASE_URL}/auth/password/reset/confirm?token={token}"
    message = MessageSchema(
        subject="Password reset instructions",
        recipients=[email],
        body=f"""
        <html>
          <body>
            <h2>Password reset</h2>
            <p>To reset your password, follow the link:</p>
            <a href="{reset_link}">Reset password</a>
          </body>
        </html>
        """,
        subtype="html",
    )
    fm = FastMail(get_mail_config())
    try:
        await fm.send_message(message)
    except Exception:
        return


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Dependency that returns authenticated user from JWT token with caching."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM]
        )
        email: str | None = payload.get("sub")
        scope = payload.get("scope", "access")
        if email is None or scope != "access":
            raise credentials_exception
        token_data = schemas.TokenData(sub=email, scope=scope)
    except JWTError:
        raise credentials_exception
    cached_user = await get_cached_user(token_data.sub)
    if cached_user:
        return cached_user
    user = crud.get_user_by_email(db, email=token_data.sub)
    if user is None:
        raise credentials_exception
    await cache_user(user)
    return user


@router.post(
    "/signup", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED
)
def signup(
    user_in: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Register a new user and send verification email."""

    hashed_password = get_password_hash(user_in.password)
    user = crud.create_user(db, user_in, hashed_password)
    token = create_verification_token(user)
    send_verification_email(background_tasks, user.email, token)
    return user


@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Authenticate user and return access/refresh token pair."""

    user = crud.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email is not verified"
        )
    access_token = create_access_token({"sub": user.email})
    refresh_token = create_refresh_token({"sub": user.email})
    await cache_user(user)
    return schemas.Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=schemas.Token)
async def refresh_tokens(payload: schemas.TokenRefresh, db: Session = Depends(get_db)):
    """Issue a new pair of tokens based on a refresh token."""

    try:
        token_data = jwt.decode(
            payload.refresh_token,
            get_settings().SECRET_KEY,
            algorithms=[get_settings().ALGORITHM],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    if token_data.get("scope") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token scope"
        )
    email = token_data.get("sub")
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    access_token = create_access_token({"sub": user.email})
    refresh_token = create_refresh_token({"sub": user.email})
    await cache_user(user)
    return schemas.Token(access_token=access_token, refresh_token=refresh_token)


@router.get("/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify email address using token."""

    try:
        payload = jwt.decode(
            token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token"
        )
    if payload.get("scope") != "verification":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token scope"
        )
    email = payload.get("sub")
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if user.is_verified:
        return {"message": "Email already verified"}
    crud.verify_user(db, user)
    return {"message": "Email verified successfully"}


@router.post("/verify", status_code=status.HTTP_200_OK)
def resend_verification(
    request: schemas.EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Resend verification token to provided email."""

    user = crud.get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    token = create_verification_token(user)
    send_verification_email(background_tasks, user.email, token)
    return {"message": "Verification email sent"}


@router.post("/password/reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request: schemas.PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send password reset email to the requested user."""

    user = crud.get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    token = create_password_reset_token(user)
    send_password_reset_email(background_tasks, user.email, token)
    return {"message": "Password reset email sent"}


@router.post("/password/reset/confirm", status_code=status.HTTP_200_OK)
async def confirm_password_reset(
    payload: schemas.PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Confirm password reset using a provided token and new password."""

    try:
        token_data = jwt.decode(
            payload.token,
            get_settings().SECRET_KEY,
            algorithms=[get_settings().ALGORITHM],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token"
        )
    if token_data.get("scope") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token scope"
        )
    email = token_data.get("sub")
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    new_hash = get_password_hash(payload.new_password)
    crud.update_user_password(db, user, new_hash)
    await cache_user(user)
    return {"message": "Password updated"}
