from datetime import date, timedelta

from fastapi import status

from app import crud
from app.auth import get_password_hash
from app.schemas import UserCreate, ContactCreate


def create_verified_user(
    db_session, email="owner@example.com", password="secret123", role="user"
):
    hashed = get_password_hash(password)
    user_in = UserCreate(email=email, password=password, role=role)
    user = crud.create_user(db_session, user_in, hashed)
    user.is_verified = True
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login(client, email, password):
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()["access_token"]


def test_create_and_list_contacts(client, db_session):
    user = create_verified_user(db_session, email="contacts@example.com")
    token = login(client, user.email, "secret123")

    new_contact = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "12345",
    }
    create_resp = client.post(
        "/contacts/",
        json=new_contact,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED

    list_resp = client.get(
        "/contacts/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == status.HTTP_200_OK
    assert len(list_resp.json()) == 1


def test_upcoming_birthdays(client, db_session):
    user = create_verified_user(db_session, email="birthday@example.com")
    token = login(client, user.email, "secret123")
    birthday_date = date.today() + timedelta(days=3)
    contact = ContactCreate(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        birthday=birthday_date,
    )
    crud.create_contact(db_session, contact, user)

    resp = client.get(
        "/contacts/birthdays/upcoming",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert any(item["email"] == "jane@example.com" for item in data)
