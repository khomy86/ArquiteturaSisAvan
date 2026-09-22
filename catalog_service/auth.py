import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import AdminUser
from .schemas import AdminOut, Token

logger = logging.getLogger(__name__)

password_hash = PasswordHash.recommended()
# Checked against when the username doesn't exist, so a failed login takes the
# same time either way and doesn't reveal which usernames are valid.
_DUMMY_HASH = password_hash.hash("not-a-real-password")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])


def create_access_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=config.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def authenticate(db: Session, username: str, password: str) -> AdminUser | None:
    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if user is None:
        password_hash.verify(password, _DUMMY_HASH)
        return None
    if not password_hash.verify(password, user.password_hash):
        return None
    return user


def require_admin(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise unauthorized
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.get("sub")))
    if user is None:
        raise unauthorized
    return user


def ensure_admin_user(db: Session) -> None:
    """Create the admin account from the environment, or update its password."""
    if not config.ADMIN_USERNAME or not config.ADMIN_PASSWORD:
        logger.warning("ADMIN_USERNAME/ADMIN_PASSWORD not set; no admin account was created")
        return

    user = db.scalar(select(AdminUser).where(AdminUser.username == config.ADMIN_USERNAME))
    if user is None:
        db.add(AdminUser(
            username=config.ADMIN_USERNAME,
            password_hash=password_hash.hash(config.ADMIN_PASSWORD),
        ))
        logger.info("Created admin user %r", config.ADMIN_USERNAME)
    elif not password_hash.verify(config.ADMIN_PASSWORD, user.password_hash):
        user.password_hash = password_hash.hash(config.ADMIN_PASSWORD)
        logger.info("Updated password for admin user %r", config.ADMIN_USERNAME)
    db.commit()


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    user = authenticate(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.username))


@router.get("/me", response_model=AdminOut)
def me(admin: Annotated[AdminUser, Depends(require_admin)]):
    return admin
