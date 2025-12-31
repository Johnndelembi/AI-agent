"""
Admin controller for admin dashboard endpoints.
Provides endpoints for viewing users, tracking emails, monitoring referrals, and activity metrics.
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.services.admin_service import admin_service
from app.utils.auth_utils import get_current_admin_user
from app.utils.error_handler import handle_http_errors
from app.models.auth import User
from app.config import logger

router = APIRouter(prefix="/admin", tags=["admin"])


# Response Models
class UserListResponse(BaseModel):
    """Response model for paginated user list."""
    users: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserDetailResponse(BaseModel):
    """Response model for detailed user information."""
    user: Dict[str, Any]
    engagement: Optional[Dict[str, Any]] = None
    points: Optional[Dict[str, Any]] = None
    referral_code: Optional[Dict[str, Any]] = None
    referrals_made: List[Dict[str, Any]]
    referral_received: Optional[Dict[str, Any]] = None
    conversation_count: int
    email_count: int


class EmailLogResponse(BaseModel):
    """Response model for email log entry."""
    id: str
    user_id: str
    email_type: str
    recipient_email: str
    subject: str
    sent_at: Optional[str]
    status: str
    metadata: Dict[str, Any]


class EmailLogsResponse(BaseModel):
    """Response model for paginated email logs."""
    logs: List[EmailLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReferralStatsResponse(BaseModel):
    """Response model for referral statistics."""
    total_referrals: int
    successful_referrals: int
    total_points_awarded: int
    top_referrers: List[Dict[str, Any]]


class UserReferralsResponse(BaseModel):
    """Response model for user referrals."""
    referral_code: Optional[Dict[str, Any]] = None
    total_referrals: int
    successful_referrals: int
    referrals: List[Dict[str, Any]]


class UserActivityResponse(BaseModel):
    """Response model for user activity metrics."""
    user_id: str
    last_login: Optional[str] = None
    days_since_login: Optional[int] = None
    account_created_at: Optional[str] = None
    days_since_creation: Optional[int] = None
    conversation_count: int
    total_messages: int
    email_count: int
    last_email_sent: Optional[Dict[str, Any]] = None


class DashboardStatsResponse(BaseModel):
    """Response model for dashboard statistics."""
    users: Dict[str, Any]
    emails: Dict[str, Any]
    referrals: Dict[str, Any]
    conversations: Dict[str, Any]


# Endpoints
@router.get("/users", response_model=UserListResponse, summary="List all users")
@handle_http_errors("Error getting users")
async def get_all_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verified status"),
    is_admin: Optional[bool] = Query(None, description="Filter by admin status"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    start_date: Optional[str] = Query(None, description="Filter users created after this date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter users created before this date (ISO format)"),
    admin_user: User = Depends(get_current_admin_user)
) -> UserListResponse:
    """
    Get paginated list of all users with optional filters.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    - **is_active**: Filter by active status
    - **is_verified**: Filter by verified status
    - **is_admin**: Filter by admin status
    - **search**: Search by email or name
    - **start_date**: Filter users created after this date
    - **end_date**: Filter users created before this date
    
    Requires: Admin privileges.
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        result = await asyncio.to_thread(
            admin_service.get_all_users,
            page=page,
            page_size=page_size,
            is_active=is_active,
            is_verified=is_verified,
            is_admin=is_admin,
            search=search,
            start_date=start_dt,
            end_date=end_dt
        )
        
        return UserListResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}"
        )


@router.get("/users/{user_id}", response_model=UserDetailResponse, summary="Get user details")
@handle_http_errors("Error getting user details")
async def get_user_details(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user)
) -> UserDetailResponse:
    """
    Get detailed information about a specific user.
    
    Includes:
    - User profile
    - Engagement data
    - Points balance
    - Referral code and referrals
    - Conversation count
    - Email count
    
    Requires: Admin privileges.
    """
    try:
        result = await asyncio.to_thread(
            admin_service.get_user_details,
            user_id=user_id
        )
        
        return UserDetailResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user details: {str(e)}"
        )


@router.get("/emails", response_model=EmailLogsResponse, summary="List email logs")
@handle_http_errors("Error getting email logs")
async def get_email_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    email_type: Optional[str] = Query(None, description="Filter by email type"),
    start_date: Optional[str] = Query(None, description="Filter emails sent after this date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter emails sent before this date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
    admin_user: User = Depends(get_current_admin_user)
) -> EmailLogsResponse:
    """
    Get paginated list of email logs with optional filters.
    
    - **user_id**: Filter by user ID
    - **email_type**: Filter by email type (welcome, re_engagement, curated, etc.)
    - **start_date**: Filter emails sent after this date
    - **end_date**: Filter emails sent before this date
    - **page**: Page number
    - **page_size**: Items per page (max: 500)
    
    Requires: Admin privileges.
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        result = await asyncio.to_thread(
            admin_service.get_email_logs,
            user_id=user_id,
            email_type=email_type,
            start_date=start_dt,
            end_date=end_dt,
            page=page,
            page_size=page_size
        )
        
        # Convert logs to EmailLogResponse
        logs = [EmailLogResponse(**log) for log in result["logs"]]
        
        return EmailLogsResponse(
            logs=logs,
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting email logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get email logs: {str(e)}"
        )


@router.get("/emails/user/{user_id}", response_model=List[EmailLogResponse], summary="Get user email history")
@handle_http_errors("Error getting user email history")
async def get_user_email_history(
    user_id: str,
    email_type: Optional[str] = Query(None, description="Filter by email type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    admin_user: User = Depends(get_current_admin_user)
) -> List[EmailLogResponse]:
    """
    Get email history for a specific user.
    
    - **user_id**: User ID
    - **email_type**: Optional filter by email type
    - **limit**: Maximum number of results (max: 500)
    
    Requires: Admin privileges.
    """
    try:
        result = await asyncio.to_thread(
            admin_service.get_user_email_history,
            user_id=user_id,
            email_type=email_type,
            limit=limit
        )
        
        return [EmailLogResponse(**log) for log in result]
        
    except Exception as e:
        logger.error(f"Error getting user email history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user email history: {str(e)}"
        )


@router.get("/referrals", response_model=ReferralStatsResponse, summary="Get referral statistics")
@handle_http_errors("Error getting referral statistics")
async def get_referral_stats(
    admin_user: User = Depends(get_current_admin_user)
) -> ReferralStatsResponse:
    """
    Get aggregate referral statistics.
    
    Includes:
    - Total referrals
    - Successful referrals
    - Total points awarded
    - Top referrers
    
    Requires: Admin privileges.
    """
    try:
        result = await asyncio.to_thread(
            admin_service.get_referral_stats
        )
        
        return ReferralStatsResponse(**result)
        
    except Exception as e:
        logger.error(f"Error getting referral stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get referral statistics: {str(e)}"
        )


@router.get("/referrals/user/{user_id}", response_model=UserReferralsResponse, summary="Get user referrals")
@handle_http_errors("Error getting user referrals")
async def get_user_referrals(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user)
) -> UserReferralsResponse:
    """
    Get referrals made by a specific user.
    
    Includes:
    - Referral code
    - Total referrals
    - Successful referrals
    - List of referrals with details
    
    Requires: Admin privileges.
    """
    try:
        result = await asyncio.to_thread(
            admin_service.get_user_referrals,
            user_id=user_id
        )
        
        return UserReferralsResponse(**result)
        
    except Exception as e:
        logger.error(f"Error getting user referrals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user referrals: {str(e)}"
        )


@router.get("/activity/{user_id}", response_model=UserActivityResponse, summary="Get user activity metrics")
@handle_http_errors("Error getting user activity metrics")
async def get_user_activity(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user)
) -> UserActivityResponse:
    """
    Get activity metrics for a specific user.
    
    Includes:
    - Last login timestamp
    - Days since last login
    - Account creation date
    - Conversation count
    - Total messages
    - Email count
    - Last email sent
    
    Requires: Admin privileges.
    """
    try:
        result = await asyncio.to_thread(
            admin_service.get_user_activity_metrics,
            user_id=user_id
        )
        
        return UserActivityResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting user activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user activity: {str(e)}"
        )


@router.get("/dashboard/stats", response_model=DashboardStatsResponse, summary="Get dashboard statistics")
@handle_http_errors("Error getting dashboard statistics")
async def get_dashboard_stats(
    admin_user: User = Depends(get_current_admin_user)
) -> DashboardStatsResponse:
    """
    Get dashboard overview statistics.
    
    Includes:
    - User statistics (total, active, verified, new users)
    - Email statistics (total, by type, recent)
    - Referral statistics
    - Conversation statistics
    
    Requires: Admin privileges.
    """
    try:
        result = await asyncio.to_thread(
            admin_service.get_dashboard_stats
        )
        
        return DashboardStatsResponse(**result)
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard statistics: {str(e)}"
        )

