"""User-related routes and operations for the Contacts API."""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader

from .auth import get_current_user
from .database import get_db
from . import schemas, crud
from .core import get_settings

router = APIRouter(prefix="/users", tags=["users"])
settings = get_settings()

if settings.CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL)


@router.get(
    "/me",
    response_model=schemas.UserOut,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
def read_me(current_user=Depends(get_current_user)):
    """
    Retrieve details of the currently authenticated user.

    Args:
        current_user (User): Authenticated user obtained from JWT token.

    Returns:
        UserOut: User profile information.
    """
    return current_user


@router.put("/avatar", response_model=schemas.UserOut)
def update_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the avatar of the authenticated user.

    Only users with the ``admin`` role are allowed to update avatars.

    Args:
        file (UploadFile): Uploaded image file.
        current_user (User): Authenticated user.
        db (Session): Database session.

    Raises:
        HTTPException: If user is not an administrator.
        HTTPException: If Cloudinary is not configured.
        HTTPException: If avatar upload fails.

    Returns:
        UserOut: Updated user profile.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change avatars",
        )

    if not settings.CLOUDINARY_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cloudinary is not configured",
        )

    upload_result = cloudinary.uploader.upload(file.file, folder="contacts_avatars")
    avatar_url = upload_result.get("secure_url")

    if not avatar_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to upload avatar",
        )

    user = crud.update_user_avatar(db, current_user, avatar_url)
    return user
