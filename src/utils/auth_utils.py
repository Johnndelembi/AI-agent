"""
Authentication middleware and dependencies for protected routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from src.models.auth import User
from src.services.auth_service import auth_service


# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Dependency to get current authenticated user from JWT token.
    
    Usage in endpoints:
        @router.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}
    """
    token = credentials.credentials
    
    try:
        user = auth_service.get_user_from_token(token)
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user.
    Raises 403 if user is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current admin user.
    Raises 403 if user is not an admin.
    
    Usage:
        @router.get("/admin-only")
        async def admin_route(admin_user: User = Depends(get_current_admin_user)):
            return {"message": "Admin access granted"}
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current verified user.
    Raises 403 if user is not verified.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    return current_user


def has_role(required_role: str):
    """
    Dependency factory to check if user has a specific role.
    
    Usage:
        @router.get("/moderator-only")
        async def moderator_route(current_user: User = Depends(has_role("moderator"))):
            return {"message": "Moderator access granted"}
    """
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if required_role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return current_user
    return check_role


# Optional authentication (doesn't fail if no token provided)
async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """
    Optional authentication dependency.
    Returns User if valid token provided, None otherwise.
    
    Usage:
        @router.get("/maybe-protected")
        async def maybe_protected(user: Optional[User] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello anonymous"}
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        user = auth_service.get_user_from_token(token)
        return user
    except:
        return None

