"""
Authentication HTTP Endpoints (/api/v1/auth)
Handles user login, token refresh rotation, logout, /me profile, and self-service password changes.
"""


from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.core.security import decode_token
from app.models.auth import User
from app.modules.auth.dependencies import (
    get_auth_service,
    get_current_user,
    security_scheme,
)
from app.modules.auth.service import AuthService
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticates credentials and sets secure httpOnly refresh token cookie."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent")

    token_response, refresh_token = await auth_service.login(
        email=payload.email,
        password=payload.password,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    # Secure httpOnly refresh cookie
    cookie_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=cookie_max_age,
        httponly=True,
        secure=settings.APP_ENV != "development",  # True in production
        samesite="lax",
        path="/api/v1/auth",
    )

    return token_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Rotates refresh tokens and issues a new access token."""
    token_candidate = refresh_token

    # Fallback to Authorization header if cookie is missing
    if not token_candidate and authorization and authorization.startswith("Bearer "):
        token_candidate = authorization.split(" ")[1]

    if not token_candidate:
        raise AuthenticationException(detail="Refresh token missing", error_code="AUTH_001")

    client_ip = request.client.host if request.client else "127.0.0.1"
    token_response, new_refresh_token = await auth_service.refresh_tokens(
        refresh_token_str=token_candidate, client_ip=client_ip
    )

    cookie_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=cookie_max_age,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
        path="/api/v1/auth",
    )

    return token_response


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Revokes active tokens and clears session cookies."""
    access_jti = None
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            access_jti = payload.get("jti")
        except Exception:
            pass

    await auth_service.logout(user_id=current_user.id, access_jti=access_jti)
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"message": "Successfully logged out and session revoked"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Returns the authenticated user's profile and granted permissions."""
    permissions = [f"{p.resource}:{p.action}" for p in current_user.role.permissions]
    return UserResponse(
        id=current_user.id,
        employee_id=current_user.employee_id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.name,
        role_display_name=current_user.role.display_name,
        department=current_user.department,
        designation=current_user.designation,
        is_active=current_user.is_active,
        is_locked=current_user.is_locked,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        permissions=permissions,
    )


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Enables self-service password update for the authenticated user."""
    await auth_service.change_password(
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return {"message": "Password successfully updated. All other active sessions have been invalidated."}
