"""Contact management routes for the Contacts API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from . import schemas, crud
from .database import get_db
from .auth import get_current_user
from .models import User

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("/", response_model=schemas.ContactOut, status_code=201)
def create_contact(
    contact_in: schemas.ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new contact owned by the current user.

    Args:
        contact_in (ContactCreate): Contact input data.
        db (Session): Database session.
        current_user (User): Authenticated user.

    Returns:
        ContactOut: Created contact.
    """
    return crud.create_contact(db, contact_in, current_user)


@router.get("/", response_model=List[schemas.ContactOut])
def list_contacts(
    q: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a list of contacts belonging to the current user.

    Supports optional text search by first name, last name, or email.

    Args:
        q (str | None): Optional search query.
        skip (int): Number of records to skip.
        limit (int): Maximum number of records to return.
        db (Session): Database session.
        current_user (User): Authenticated user.

    Returns:
        list[ContactOut]: List of contacts.
    """
    return crud.get_contacts(db, user=current_user, skip=skip, limit=limit, q=q)


@router.get("/{contact_id}", response_model=schemas.ContactOut)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a single contact by ID for the current user.

    Args:
        contact_id (int): Contact identifier.
        db (Session): Database session.
        current_user (User): Authenticated user.

    Raises:
        HTTPException: If contact is not found.

    Returns:
        ContactOut: Contact data.
    """
    c = crud.get_contact(db, contact_id, current_user)
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return c


@router.patch("/{contact_id}", response_model=schemas.ContactOut)
def patch_contact(
    contact_id: int,
    changes: schemas.ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Partially update an existing contact.

    Only fields provided in the request will be updated.

    Args:
        contact_id (int): Contact identifier.
        changes (ContactUpdate): Fields to update.
        db (Session): Database session.
        current_user (User): Authenticated user.

    Raises:
        HTTPException: If contact is not found.

    Returns:
        ContactOut: Updated contact.
    """
    c = crud.get_contact(db, contact_id, current_user)
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return crud.update_contact(db, c, changes.dict(exclude_unset=True))


@router.delete("/{contact_id}")
def remove_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a contact owned by the current user.

    Args:
        contact_id (int): Contact identifier.
        db (Session): Database session.
        current_user (User): Authenticated user.

    Raises:
        HTTPException: If contact is not found.

    Returns:
        dict: Deletion status.
    """
    c = crud.get_contact(db, contact_id, current_user)
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    crud.delete_contact(db, c)
    return {"ok": True}


@router.get("/birthdays/upcoming", response_model=List[schemas.ContactOut])
def upcoming_birthdays(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve contacts with upcoming birthdays.

    Args:
        days (int): Number of days ahead to check birthdays.
        db (Session): Database session.
        current_user (User): Authenticated user.

    Returns:
        list[ContactOut]: Contacts with upcoming birthdays.
    """
    return crud.get_upcoming_birthdays(db, user=current_user, days=days)
