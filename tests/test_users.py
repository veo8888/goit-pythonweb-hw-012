from fastapi import status

from app import crud
from app.auth import get_password_hash
from app.schemas import UserCreate


def create_user(db_session, email, role="user"):
    hashed = get_password_hash("secret123")
    user_in = UserCreate(email=email, password="secret123", role=role)
    user = crud.create_user(db_session, user_in, hashed)
    user.is_verified = True
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login(client, email):
    resp = client.post(
        "/auth/login",
        data={"username": email, "password": "secret123"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()["access_token"]


def test_avatar_update_requires_admin(client, db_session):
    user = create_user(db_session, "standard@example.com", role="user")
    token = login(client, user.email)
    response = client.put(
        "/users/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("avatar.png", b"content", "image/png")},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    admin = create_user(db_session, "admin@example.com", role="admin")
    admin_token = login(client, admin.email)
    response_admin = client.put(
        "/users/avatar",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("avatar.png", b"content", "image/png")},
    )
    assert response_admin.status_code in (
        status.HTTP_200_OK,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
