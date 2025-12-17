"""CRUD operations for users and contacts.

This module contains database interaction logic for user and contact
entities, isolated from FastAPI route handlers.
"""

from datetime import date, timedelta
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas


def create_user(
    db: Session, user_in: schemas.UserCreate, hashed_password: str
) -> models.User:
    """
    Create and persist a new user.

    Args:
        db (Session): SQLAlchemy database session.
        user_in (UserCreate): Incoming user data.
        hashed_password (str): Securely hashed password.

    Raises:
        HTTPException: If a user with the same email already exists.

    Returns:
        User: Newly created user instance.
    """
    existing = db.execute(
        select(models.User).where(models.User.email == user_in.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    user = models.User(
        email=user_in.email,
        hashed_password=hashed_password,
        role=user_in.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> models.User | None:
    """
    Retrieve a user by email address.

    Args:
        db (Session): Database session.
        email (str): User email.

    Returns:
        User | None: User if found, otherwise ``None``.
    """
    return db.execute(
        select(models.User).where(models.User.email == email)
    ).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> models.User | None:
    """
    Retrieve a user by primary key.

    Args:
        db (Session): Database session.
        user_id (int): User identifier.

    Returns:
        User | None: User if found, otherwise ``None``.
    """
    return db.execute(
        select(models.User).where(models.User.id == user_id)
    ).scalar_one_or_none()


def verify_user(db: Session, user: models.User) -> models.User:
    """
    Mark a user account as verified.

    Args:
        db (Session): Database session.
        user (User): User to verify.

    Returns:
        User: Updated user instance.
    """
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_avatar(db: Session, user: models.User, avatar_url: str) -> models.User:
    """
    Update avatar URL for a user.

    Args:
        db (Session): Database session.
        user (User): Target user.
        avatar_url (str): URL of uploaded avatar.

    Returns:
        User: Updated user instance.
    """
    target = get_user_by_id(db, user.id) or user
    target.avatar_url = avatar_url
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def update_user_password(
    db: Session, user: models.User, hashed_password: str
) -> models.User:
    """
    Update user's hashed password.

    Args:
        db (Session): Database session.
        user (User): Target user.
        hashed_password (str): New hashed password.

    Returns:
        User: Updated user instance.
    """
    target = get_user_by_id(db, user.id) or user
    target.hashed_password = hashed_password
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def create_contact(
    db: Session, contact_in: schemas.ContactCreate, user: models.User
) -> models.Contact:
    """
    Create a new contact owned by the given user.

    Args:
        db (Session): Database session.
        contact_in (ContactCreate): Contact data.
        user (User): Owner of the contact.

    Raises:
        HTTPException: If a contact with the same email already exists.

    Returns:
        Contact: Newly created contact.
    """
    existing = db.execute(
        select(models.Contact).where(
            models.Contact.owner_id == user.id,
            models.Contact.email == contact_in.email,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact already exists",
        )

    contact = models.Contact(**contact_in.dict(), owner_id=user.id)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def get_contact(db: Session, contact_id: int, user: models.User):
    """
    Retrieve a single contact owned by the given user.

    Args:
        db (Session): Database session.
        contact_id (int): Contact identifier.
        user (User): Contact owner.

    Returns:
        Contact | None: Contact if found, otherwise ``None``.
    """
    return db.execute(
        select(models.Contact).where(
            models.Contact.id == contact_id,
            models.Contact.owner_id == user.id,
        )
    ).scalar_one_or_none()


def get_contacts(
    db: Session,
    user: models.User,
    skip: int = 0,
    limit: int = 100,
    q: str | None = None,
):
    """
    Retrieve a list of contacts for the given user.

    Supports optional case-insensitive search by name or email.

    Args:
        db (Session): Database session.
        user (User): Contact owner.
        skip (int): Number of records to skip.
        limit (int): Maximum number of records to return.
        q (str | None): Optional search query.

    Returns:
        list[Contact]: List of contacts.
    """
    stmt = (
        select(models.Contact)
        .where(models.Contact.owner_id == user.id)
        .offset(skip)
        .limit(limit)
    )

    if q:
        like_q = f"%{q}%"
        stmt = (
            select(models.Contact)
            .where(
                models.Contact.owner_id == user.id,
                or_(
                    models.Contact.first_name.ilike(like_q),
                    models.Contact.last_name.ilike(like_q),
                    models.Contact.email.ilike(like_q),
                ),
            )
            .offset(skip)
            .limit(limit)
        )

    return db.scalars(stmt).all()


def update_contact(db: Session, contact: models.Contact, changes: dict):
    """
    Update mutable fields of a contact.

    Args:
        db (Session): Database session.
        contact (Contact): Contact instance.
        changes (dict): Fields to update.

    Returns:
        Contact: Updated contact.
    """
    for key, value in changes.items():
        setattr(contact, key, value)

    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact: models.Contact):
    """
    Delete a contact from the database.

    Args:
        db (Session): Database session.
        contact (Contact): Contact to delete.
    """
    db.delete(contact)
    db.commit()
    return None


def get_upcoming_birthdays(db: Session, user: models.User, days: int = 7):
    """
    Retrieve contacts with birthdays occurring within the next N days.

    Args:
        db (Session): Database session.
        user (User): Contact owner.
        days (int): Number of days ahead to check.

    Returns:
        list[Contact]: Contacts with upcoming birthdays.
    """
    today = date.today()
    end = today + timedelta(days=days)

    contacts = db.scalars(
        select(models.Contact).where(models.Contact.owner_id == user.id)
    ).all()

    result = []
    for contact in contacts:
        if not contact.birthday:
            continue

        birthday_this_year = contact.birthday.replace(year=today.year)
        if today <= birthday_this_year <= end:
            result.append(contact)

    return result
