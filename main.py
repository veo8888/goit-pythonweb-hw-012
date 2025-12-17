"""
Main application entry point for the Contacts API.

This module initializes the FastAPI application, sets up middleware,
configures CORS, initializes the rate limiter with Redis backend, and
includes routers for authentication, users, and contacts.

Modules:
- FastAPI: Web framework
- CORSMiddleware: Middleware for handling CORS
- FastAPILimiter: Rate limiting
- redis.asyncio: Async Redis client
- fakeredis.aioredis: Fake Redis for testing/offline
- app.database: Database engine
- app.models: SQLAlchemy models
- app.contacts: Contacts router
- app.auth: Authentication router
- app.users: Users router
- app.core: Application settings
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

try:
    from fakeredis.aioredis import FakeRedis  # type: ignore
except Exception:  # pragma: no cover - fallback for offline environments

    class FakeRedis:  # type: ignore
        """
        Lightweight stand-in for fakeredis when the dependency is unavailable.
        Provides dummy async methods for testing and offline development.
        """

        async def script_load(self, script: str) -> str:
            """
            Simulate loading a Lua script.

            Args:
                script (str): Lua script text

            Returns:
                str: Dummy SHA value
            """
            return "lua"

        async def evalsha(self, *args, **kwargs) -> int:
            """
            Simulate evaluating a Lua script by SHA.

            Returns:
                int: Dummy result (always 0)
            """
            return 0

        async def close(self):
            """
            Simulate closing the fake Redis connection.
            """
            return None


from app.database import engine
from app import models, contacts
from app.auth import router as auth_router
from app.users import router as users_router
from app.core import get_settings

# Create tables (for development only)
models.Base.metadata.create_all(bind=engine)

settings = get_settings()

# Initialize FastAPI application
app = FastAPI(title="Contacts API")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.

    Initializes the rate limiter with Redis backend. Falls back to
    FakeRedis if Redis is unavailable (e.g., during tests or offline).
    """
    redis_client = redis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )
    try:
        await FastAPILimiter.init(redis_client)
    except Exception:
        await FastAPILimiter.init(FakeRedis())


# Include routers for application areas
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(contacts.router)


@app.get("/")
def root():
    """
    Root endpoint for the API.

    Returns a simple JSON message directing users to the Swagger UI.

    Returns:
        dict: JSON message with information about the API
    """
    return {"msg": "Contacts API. Visit /docs for Swagger UI"}
