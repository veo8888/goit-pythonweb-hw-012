from fastapi import status

from app import crud
from app.auth import (
    create_access_token,
    create_password_reset_token,
    get_password_hash,
    verify_password,
)
from app.schemas import UserCreate
from app.models import User


def test_password_hashing_roundtrip():
    password = "secret123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed)


def create_verified_user(
    db_session, email="user@example.com", password="secret123", role="user"
):
    hashed = get_password_hash(password)
    user_in = UserCreate(email=email, password=password, role=role)
    user = crud.create_user(db_session, user_in, hashed)
    user.is_verified = True
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_and_token_pair(client, db_session):
    create_verified_user(db_session)
    response = client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": "secret123"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data and "refresh_token" in data

    me_resp = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_resp.status_code == status.HTTP_200_OK
    assert me_resp.json()["email"] == "user@example.com"


def test_refresh_token_returns_new_access(client, db_session):
    create_verified_user(db_session, email="refresh@example.com")
    login_resp = client.post(
        "/auth/login",
        data={"username": "refresh@example.com", "password": "secret123"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    ).json()
    refresh_resp = client.post(
        "/auth/refresh",
        json={"refresh_token": login_resp["refresh_token"]},
    )
    assert refresh_resp.status_code == status.HTTP_200_OK
    tokens = refresh_resp.json()
    assert tokens["access_token"] != ""


def test_password_reset_flow(client, db_session):
    user = create_verified_user(db_session, email="reset@example.com")
    request_resp = client.post("/auth/password/reset", json={"email": user.email})
    assert request_resp.status_code == status.HTTP_200_OK

    token = create_password_reset_token(user)
    confirm_resp = client.post(
        "/auth/password/reset/confirm",
        json={"token": token, "new_password": "newpass123"},
    )
    assert confirm_resp.status_code == status.HTTP_200_OK
    db_session.refresh(user)
    assert verify_password("newpass123", user.hashed_password)
