"""
SmartHire AI — Authentication API Router

Endpoints:
    POST /auth/register    — Create new user account
    POST /auth/login       — Authenticate, receive JWT pair
    POST /auth/refresh     — Exchange refresh token for new access token
    POST /auth/logout      — Invalidate refresh token
    GET  /auth/me          — Get current user profile
    PUT  /auth/me          — Update profile / change password
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limiter import RATE_LIMIT_AUTH, limiter
from app.core.redis_client import (
    get_refresh_token,
    revoke_refresh_token,
    store_refresh_token,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user_id,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    AccessToken,
    Token,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _get_user_by_id(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit(RATE_LIMIT_AUTH)
async def register(
    request: Request,
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Create a new user account.

    - Validates email uniqueness
    - Hashes password with bcrypt (12 rounds)
    - Returns the created user (no tokens — user must log in separately)
    """
    # Check for existing email
    existing = await _get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info("User registered", user_id=str(user.id), email=user.email)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive JWT tokens",
)
@limiter.limit(RATE_LIMIT_AUTH)
async def login(
    request: Request,
    body: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Authenticate with email and password.

    Returns:
        - `access_token` (15-min TTL)
        - `refresh_token` (7-day TTL, stored in Redis)
    """
    user = await _get_user_by_email(db, body.email)

    if not user or not verify_password(body.password, user.hashed_password):
        logger.warning("Failed login attempt", email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    # Persist refresh token in Redis
    await store_refresh_token(str(user.id), refresh_token)

    logger.info("User logged in", user_id=str(user.id))
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=AccessToken,
    summary="Refresh access token using refresh token",
)
@limiter.limit(RATE_LIMIT_AUTH)
async def refresh_token(
    request: Request,
    body: TokenRefresh,
) -> AccessToken:
    """
    Exchange a valid refresh token for a new access token.

    The refresh token is validated against Redis — if it was revoked
    (via logout), this endpoint returns 401.
    """
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id: str = payload["sub"]

    # Verify token matches what's stored in Redis
    stored_token = await get_refresh_token(user_id)
    if stored_token != body.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or is invalid",
        )

    access_token = create_access_token(subject=user_id)
    logger.info("Access token refreshed", user_id=user_id)

    return AccessToken(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    summary="Invalidate refresh token (logout)",
    status_code=status.HTTP_200_OK,
)
async def logout(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Logout the current user by revoking their refresh token in Redis.
    The access token will naturally expire within 15 minutes.
    """
    await revoke_refresh_token(user_id)
    logger.info("User logged out", user_id=user_id)
    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the authenticated user's profile."""
    user = await _get_user_by_id(db, user_id)
    return UserResponse.model_validate(user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update profile or change password",
)
async def update_me(
    body: UserUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update user profile fields.
    To change the password, provide both `current_password` and `new_password`.
    """
    user = await _get_user_by_id(db, user_id)

    if body.full_name is not None:
        user.full_name = body.full_name

    if body.new_password is not None:
        if not body.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current_password is required to set a new password",
            )
        if not verify_password(body.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )
        user.hashed_password = hash_password(body.new_password)

    await db.flush()
    await db.refresh(user)

    logger.info("User profile updated", user_id=user_id)
    return UserResponse.model_validate(user)
