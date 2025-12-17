# tests/conftest.py
import os
import sys
import asyncio
import json
from urllib.parse import urlencode

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.abspath("."))

from fastapi_limiter import FastAPILimiter

from app.database import Base, get_db
from app.core import get_settings
from app import models
from main import app


# DB (SQLite in-memory for tests)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# One event loop for the WHOLE pytest session
@pytest.fixture(scope="session")
def session_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# Run FastAPI startup/shutdown once per session (same loop)
# This ensures FastAPILimiter.init() is called correctly.
@pytest.fixture(scope="session", autouse=True)
def app_lifespan(session_loop):
    # startup once
    session_loop.run_until_complete(app.router.startup())
    yield
    # shutdown once
    session_loop.run_until_complete(app.router.shutdown())

    # cleanup limiter redis (prevents "event loop is closed" on next tests/run)
    try:
        r = getattr(FastAPILimiter, "redis", None)
        if r is not None:
            session_loop.run_until_complete(r.close())
            cp = getattr(r, "connection_pool", None)
            if cp is not None:
                session_loop.run_until_complete(cp.disconnect())
    except Exception:
        pass


# Settings adjust (optional)
# If your get_settings() uses cached settings, this may or may not affect runtime.
# Keep it anyway if your homework expects it.
@pytest.fixture(scope="session", autouse=True)
def adjust_settings_env():
    settings = get_settings()
    settings.DATABASE_URL = SQLALCHEMY_DATABASE_URL
    settings.CLOUDINARY_URL = None
    return settings


# Simple ASGI response/client
class SimpleResponse:
    def __init__(
        self, status_code: int, body: bytes, headers: list[tuple[bytes, bytes]]
    ):
        self.status_code = status_code
        self._body = body
        self.headers = {k.decode(): v.decode() for k, v in headers}

    def json(self):
        return json.loads(self._body.decode())


class SimpleClient:
    """
    Important:
    - uses ONE shared session loop (passed from fixture)
    - does NOT call asyncio.run()
    - does NOT close the loop
    """

    def __init__(self, app, loop):
        self.app = app
        self.loop = loop

    def close(self):
        # do not close the loop here (session fixture closes it)
        pass

    def request(
        self,
        method: str,
        path: str,
        json_body=None,
        data=None,
        headers=None,
        files=None,
    ):
        headers = headers or {}
        body_bytes = b""

        if files:
            boundary = "TESTBOUNDARY"
            parts: list[bytes] = []
            for name, (filename, content, content_type) in files.items():
                disposition = f'form-data; name="{name}"; filename="{filename}"'
                part_headers = (
                    f"--{boundary}\r\n"
                    f"Content-Disposition: {disposition}\r\n"
                    f"Content-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
                )
                parts.append(part_headers.encode() + content + b"\r\n")
            parts.append(f"--{boundary}--\r\n".encode())
            body_bytes = b"".join(parts)
            headers["content-type"] = f"multipart/form-data; boundary={boundary}"

        elif json_body is not None:
            body_bytes = json.dumps(json_body).encode()
            headers.setdefault("content-type", "application/json")

        elif data is not None:
            if isinstance(data, dict):
                body_bytes = urlencode(data, doseq=True).encode()
            elif isinstance(data, bytes):
                body_bytes = data
            else:
                body_bytes = str(data).encode()
            headers.setdefault("content-type", "application/x-www-form-urlencoded")

        raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        scope = {
            "type": "http",
            "method": method.upper(),
            "path": path,
            "headers": raw_headers,
            "query_string": b"",
            "client": ("testclient", 5000),
        }

        async def receive():
            nonlocal body_bytes
            chunk, body_bytes = body_bytes, b""
            return {"type": "http.request", "body": chunk, "more_body": False}

        response_body = bytearray()
        response_status = 500
        response_headers: list[tuple[bytes, bytes]] = []

        async def send(message):
            nonlocal response_status, response_headers
            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body.extend(message.get("body", b""))

        # ensure the loop is the current one
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.app(scope, receive, send))
        return SimpleResponse(response_status, bytes(response_body), response_headers)

    def get(self, path: str, headers=None):
        return self.request("GET", path, headers=headers)

    def post(self, path: str, json=None, data=None, headers=None, files=None):
        return self.request(
            "POST", path, json_body=json, data=data, headers=headers, files=files
        )

    def put(self, path: str, json=None, data=None, headers=None, files=None):
        return self.request(
            "PUT", path, json_body=json, data=data, headers=headers, files=files
        )


# Client fixture: override DB dependency per test
@pytest.fixture()
def client(db_session, session_loop):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    c = SimpleClient(app, loop=session_loop)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()
        c.close()
