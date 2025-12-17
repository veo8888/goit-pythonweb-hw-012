"""Application configuration and settings management.

This module defines the application settings loaded from environment
variables and provides helper functions for accessing cached settings
and email configuration.
"""

from functools import lru_cache
from typing import List

from fastapi_mail import ConnectionConfig
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Attributes:
        DATABASE_URL: Database connection string.
        SECRET_KEY: Secret key used for JWT signing.
        ALGORITHM: Algorithm used to encode JWT tokens.
        ACCESS_TOKEN_EXPIRE_MINUTES: Access token lifetime in minutes.
        REFRESH_TOKEN_EXPIRE_MINUTES: Refresh token lifetime in minutes.
        ALLOWED_ORIGINS: Allowed origins for CORS.
        REDIS_URL: Redis connection URL for rate limiting and caching.
        CLOUDINARY_URL: Cloudinary connection URL for avatar uploads.
        SMTP_FROM_EMAIL: Sender email address for outgoing emails.
        SMTP_USER: SMTP username.
        SMTP_PASSWORD: SMTP password.
        SMTP_PORT: SMTP server port.
        SMTP_HOST: SMTP server host.
        BASE_URL: Base URL of the application.
    """

    DATABASE_URL: str = "sqlite:///./app.db"
    SECRET_KEY: str = "dev-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALLOWED_ORIGINS: List[str] = ["*"]
    REDIS_URL: str = "redis://redis:6379"
    CLOUDINARY_URL: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@example.com"
    SMTP_USER: str = "user"
    SMTP_PASSWORD: str = "password"
    SMTP_PORT: str = "1025"
    SMTP_HOST: str = "localhost"
    BASE_URL: str = "http://localhost:8000"

    class Config:
        """Pydantic configuration for loading environment variables."""

        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings.

    The settings object is cached to prevent reloading environment
    variables multiple times during application lifetime.
    """

    return Settings()


def get_mail_config() -> ConnectionConfig:
    """Create and return email configuration for FastAPI-Mail.

    Returns:
        ConnectionConfig: Configured email connection settings.
    """

    settings = get_settings()
    return ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USER,
        MAIL_PASSWORD=settings.SMTP_PASSWORD,
        MAIL_FROM=settings.SMTP_FROM_EMAIL,
        MAIL_PORT=settings.SMTP_PORT,
        MAIL_SERVER=settings.SMTP_HOST,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
    )
