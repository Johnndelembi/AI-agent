"""Authentication controller for Google OAuth login and profile management."""

import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse

from app.models.auth import (
    # Pydantic models
    TokenResponse, RefreshTokenRequest,
    UserResponse, UpdateProfileRequest,
    AdminPatchUserRequest,
    # MongoDB models
    User
)
from app.services.auth_service import auth_service, ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.oauth_service import google_oauth_service
from app.utils.auth_utils import get_current_user, get_current_active_user, get_current_admin_user
from app.utils.error_handler import handle_http_errors
from app.dependencies import get_database
from app.config import logger, settings


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/google/login", summary="Initiate Google OAuth login")
@handle_http_errors("Failed to initiate Google OAuth")
async def google_login(redirect_uri: str = None, frontend_url: str = None):
    """
    Initiates Google OAuth flow.
    
    - **redirect_uri**: Where Google should redirect after auth (default: frontend callback)
    - **frontend_url**: Frontend URL (for fallback)
    """
    # Use frontend callback URL if provided, otherwise use backend
    if redirect_uri:
        callback_url = redirect_uri
    elif frontend_url:
        callback_url = f"{frontend_url}/auth/google/callback"
    else:
        # Default to frontend callback
        callback_url = "https://artemis.ares.codes/auth/google/callback"
    
    # Generate OAuth URL with frontend callback
    oauth_url = google_oauth_service.get_authorization_url(
        redirect_uri=callback_url
    )
    
    return RedirectResponse(url=oauth_url)


@router.get("/google/callback")
async def google_callback(code: str, state: str = None, db=Depends(get_database)):
    """
    Handles Google OAuth callback - called by FRONTEND to exchange code for tokens.
    This is an API endpoint, not a redirect target.
    """
    logger.info(f"Google OAuth callback received: code={code[:20]}...")
    
    try:
        result = await google_oauth_service.handle_callback(code)
        
        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "token_type": result["token_type"],
            "expires_in": result["expires_in"],
            "user": result["user"]
        }
        
    except Exception as e:
        logger.error(f"Google OAuth callback error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
@handle_http_errors("Token refresh failed")
async def refresh_token(request: RefreshTokenRequest, db=Depends(get_database)) -> TokenResponse:
    """
    Generate new access token using refresh token.
    
    - **refresh_token**: Valid refresh token from login
    
    Returns new access token.
    """
    result = await asyncio.to_thread(
        auth_service.refresh_access_token,
        refresh_token=request.refresh_token
    )
    
    return TokenResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
@handle_http_errors("Failed to get profile")
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current authenticated user's profile.
    
    Requires: Valid JWT token in Authorization header.
    """
    return UserResponse(**current_user.to_dict())


@router.put("/me", response_model=UserResponse, summary="Update current user profile")
@handle_http_errors("Failed to update profile")
async def update_current_user_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Update current user's profile information.
    
    Requires: Valid JWT token in Authorization header.
    """
    # Update fields if provided
    update_data = request.dict(exclude_unset=True)
    
    # Handle first_name and last_name updates
    if 'first_name' in update_data:
        current_user.first_name = update_data['first_name'] or ""
    if 'last_name' in update_data:
        current_user.last_name = update_data['last_name'] or ""
    
    # Update fullname if first_name or last_name changed, or if fullname is explicitly provided
    if 'first_name' in update_data or 'last_name' in update_data:
        # Recompute fullname from first_name and last_name
        current_user.fullname = f"{current_user.first_name} {current_user.last_name}".strip()
    elif 'fullname' in update_data and update_data['fullname']:
        # If fullname is explicitly provided, use it
        current_user.fullname = update_data['fullname']
    
    # Update other fields
    for field, value in update_data.items():
        if field not in ['first_name', 'last_name', 'fullname'] and hasattr(current_user, field) and value is not None:
            setattr(current_user, field, value)
    
    # Save changes
    await asyncio.to_thread(current_user.save)
    
    logger.info(f"User profile updated: {current_user.email}")
    
    return UserResponse(**current_user.to_dict())




@router.post("/logout", summary="Logout (client-side)")
async def logout(current_user: User = Depends(get_current_user)) -> dict:
    """
    Logout endpoint (for completeness).
    
    Note: JWT tokens are stateless, so logout is handled client-side
    by deleting the token. This endpoint just validates the token is valid.
    
    For true token invalidation, implement a token blacklist in Redis.
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return {
        "message": "Logged out successfully",
        "note": "Please delete the token on client side"
    }


@router.delete("/me", summary="Delete current user account")
@handle_http_errors("Failed to delete account")
async def delete_current_user(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Delete current user's account.
    
    Requires: Valid JWT token in Authorization header.
    Warning: This action cannot be undone!
    """
    email = current_user.email
    await asyncio.to_thread(current_user.delete)
    
    logger.warning(f"User account deleted: {email}")
    
    return {"message": "Account deleted successfully"}


@router.patch("/users/{user_id}", summary="Admin: Partially update a user")
@handle_http_errors("Failed to update user")
async def admin_patch_user(
    user_id: str,
    request: AdminPatchUserRequest,
    admin_user: User = Depends(get_current_admin_user),
    db=Depends(get_database)
) -> UserResponse:
    """
    Admin-only partial update of a user document.
    Supports updating profile fields, account flags, roles, and meal management fields.
    """
    # Fetch target user
    user = await asyncio.to_thread(User.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = request.dict(exclude_unset=True)

    # Special handling for roles to avoid None and enforce list semantics
    roles_update = update_data.pop('roles', None)
    if roles_update is not None:
        if not isinstance(roles_update, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="roles must be a list of strings")
        user.roles = roles_update

    # Keep roles in sync with is_admin if provided (unless roles explicitly set above)
    if 'is_admin' in update_data and roles_update is None:
        is_admin_flag = update_data['is_admin']
        if is_admin_flag and 'admin' not in user.roles:
            user.roles.append('admin')
        if (is_admin_flag is False) and ('admin' in user.roles):
            user.roles.remove('admin')

    # Update remaining simple fields if present
    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)

    # Persist changes
    await asyncio.to_thread(user.save)

    logger.info(f"Admin {admin_user.email} patched user {user.email} ({user_id})")
    return UserResponse(**user.to_dict())


