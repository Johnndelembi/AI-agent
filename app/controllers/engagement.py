"""
Engagement controller for user engagement data and preferences.
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List

from app.services.engagement_service import engagement_service
from app.utils.auth_utils import get_current_active_user
from app.utils.error_handler import handle_http_errors
from app.models.auth import User
from app.config import logger

router = APIRouter(prefix="/engagement", tags=["engagement"])


# Request/Response Models
class SubmitEngagementInfoRequest(BaseModel):
    """Request model for submitting user engagement information."""
    use_case: Optional[str] = Field(None, max_length=500, description="How you use Artemis")
    profession: Optional[str] = Field(None, max_length=200, description="What you do for a living")
    interests: Optional[List[str]] = Field(None, description="Areas of interest")
    goals: Optional[str] = Field(None, max_length=1000, description="What you want to achieve")


class UpdateEmailPreferencesRequest(BaseModel):
    """Request model for updating email preferences."""
    email_opt_in: Optional[bool] = Field(None, description="Whether to receive emails")
    email_frequency: Optional[str] = Field(
        None,
        description="Email frequency: daily, weekly, biweekly, or monthly"
    )


class EngagementStatsResponse(BaseModel):
    """Response model for engagement statistics."""
    user_id: str
    has_engagement_data: bool
    info_collected: Optional[bool] = None
    use_case: Optional[str] = None
    profession: Optional[str] = None
    interests: Optional[List[str]] = None
    goals: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None


@router.post("/submit-info", summary="Submit user engagement information")
@handle_http_errors("Error submitting engagement information")
async def submit_engagement_info(
    request: SubmitEngagementInfoRequest,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Submit user engagement information from form.
    
    - **use_case**: How you use Artemis
    - **profession**: What you do for a living
    - **interests**: List of interests
    - **goals**: What you want to achieve
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        user_id = str(current_user.id)
        
        result = await asyncio.to_thread(
            engagement_service.save_user_engagement_data,
            user_id=user_id,
            use_case=request.use_case,
            profession=request.profession,
            interests=request.interests,
            goals=request.goals
        )
        
        logger.info(f"User {user_id} submitted engagement information")
        
        return {
            "success": True,
            "message": "Engagement information saved successfully",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error submitting engagement info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save engagement information: {str(e)}"
        )


@router.get("/preferences", summary="Get user email preferences (Deprecated)")
@handle_http_errors("Error getting email preferences")
async def get_email_preferences(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Get current user's email preferences.
    
    Note: Email preferences have been removed from the engagement form.
    This endpoint is kept for API compatibility but returns a deprecation message.
    
    Requires: Valid JWT token in Authorization header.
    """
    return {
        "success": True,
        "message": "Email preferences have been removed from the engagement system",
        "data": {}
    }


@router.put("/preferences", summary="Update user email preferences (Deprecated)")
@handle_http_errors("Error updating email preferences")
async def update_email_preferences(
    request: UpdateEmailPreferencesRequest,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Update user email preferences.
    
    Note: Email preferences have been removed from the engagement form.
    This endpoint is kept for API compatibility but no longer performs any action.
    
    Requires: Valid JWT token in Authorization header.
    """
    user_id = str(current_user.id)
    
    result = await asyncio.to_thread(
        engagement_service.update_email_preferences,
        user_id=user_id,
        email_opt_in=request.email_opt_in,
        email_frequency=request.email_frequency
    )
    
    return {
        "success": True,
        "message": "Email preferences have been removed from the engagement system",
        "data": result
    }


@router.get("/stats", response_model=EngagementStatsResponse, summary="Get user engagement statistics")
@handle_http_errors("Error getting engagement statistics")
async def get_engagement_stats(
    current_user: User = Depends(get_current_active_user)
) -> EngagementStatsResponse:
    """
    Get user engagement statistics.
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        user_id = str(current_user.id)
        
        stats = await asyncio.to_thread(
            engagement_service.get_user_engagement_stats,
            user_id=user_id
        )
        
        return EngagementStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting engagement stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get engagement statistics: {str(e)}"
        )

