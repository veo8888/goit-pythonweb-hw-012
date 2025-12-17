"""Database models for the Contacts API.

This module defines SQLAlchemy ORM models used by the application.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Boolean,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """
    SQLAlchemy model representing an application user.

    A user can own multiple contacts and may have different roles
    (e.g. regular user or administrator).
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(20), default="user", nullable=False)

    #: List of contacts owned by the user
    contacts = relationship(
        "Contact",
        back_populates="owner",
        cascade="all, delete",
    )


class Contact(Base):
    """
    SQLAlchemy model representing a contact entry.

    Each contact belongs to exactly one user and must have
    a unique email address per owner.
    """

    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("owner_id", "email", name="uq_owner_email"),)

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False, index=True)
    last_name = Column(String(100), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    birthday = Column(Date, nullable=True)
    extra = Column(String(500), nullable=True)

    #: Identifier of the owning user
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: Reference to the owning User object
    owner = relationship("User", back_populates="contacts")
