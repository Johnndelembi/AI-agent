"""
Referral controller for referral system and points management.
"""

import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List

from app.services.referral_service import referral_service, VOICE_GRADE_POINTS
from app.utils.auth_utils import get_current_active_user
from app.utils.error_handler import handle_http_errors
from app.models.auth import User
from app.config import logger

router = APIRouter(prefix="/referral", tags=["referral"])


# Request/Response Models
class RegisterReferralRequest(BaseModel):
    """Request model for registering a referral."""
    referral_code: str = Field(..., description="Referral code used during signup")


class RedeemPointsRequest(BaseModel):
    """Request model for redeeming points."""
    reward_type: str = Field(..., description="Type of reward to redeem (e.g., 'voice')")
    voice_name: Optional[str] = Field(None, description="Voice name if redeeming a voice (e.g., 'af_heart')")


class ReferralCodeResponse(BaseModel):
    """Response model for referral code."""
    user_id: str
    referral_code: str
    referral_link: str


class ReferralStatsResponse(BaseModel):
    """Response model for referral statistics."""
    user_id: str
    referral_code: Optional[str] = None
    total_referrals: int
    successful_referrals: int
    total_points: int
    points_from_referrals: int
    error: Optional[str] = None


class PointsResponse(BaseModel):
    """Response model for points balance."""
    user_id: str
    total_points: int
    rewards_redeemed: list
    points_history_count: int


class VoiceReward(BaseModel):
    """Model for voice reward information."""
    type: str
    voice_name: str
    name: str
    description: str
    grade: str
    points_cost: int
    available: bool
    redeemed: bool


class RewardsResponse(BaseModel):
    """Response model for available rewards."""
    rewards: List[VoiceReward]
    points_balance: int


@router.get("/code", response_model=ReferralCodeResponse, summary="Get user's referral code")
@handle_http_errors("Error getting referral code")
async def get_referral_code(
    current_user: User = Depends(get_current_active_user)
) -> ReferralCodeResponse:
    """
    Get user's referral code and link.
    
    Creates a referral code if one doesn't exist.
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        user_id = str(current_user.id)
        
        code = await asyncio.to_thread(
            referral_service.get_referral_code,
            user_id=user_id
        )
        
        if not code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate referral code"
            )
        
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        referral_link = f"{frontend_url}/signup?ref={code}"
        
        return ReferralCodeResponse(
            user_id=user_id,
            referral_code=code,
            referral_link=referral_link
        )
    except Exception as e:
        logger.error(f"Error getting referral code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get referral code: {str(e)}"
        )


@router.post("/register", summary="Register referral when new user signs up")
@handle_http_errors("Error registering referral")
async def register_referral(
    request: RegisterReferralRequest,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Register a referral when a new user signs up with a referral code.
    
    - **referral_code**: Referral code used during signup
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        referred_user_id = str(current_user.id)
        
        result = await asyncio.to_thread(
            referral_service.track_referral,
            referral_code=request.referral_code,
            referred_user_id=referred_user_id
        )
        
        logger.info(f"Referral registered: {request.referral_code} -> {referred_user_id}")
        
        return {
            "success": True,
            "message": "Referral registered successfully",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error registering referral: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register referral: {str(e)}"
        )


@router.get("/stats", response_model=ReferralStatsResponse, summary="Get user's referral statistics")
@handle_http_errors("Error getting referral statistics")
async def get_referral_stats(
    current_user: User = Depends(get_current_active_user)
) -> ReferralStatsResponse:
    """
    Get user's referral statistics (referrals, points earned).
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        user_id = str(current_user.id)
        
        stats = await asyncio.to_thread(
            referral_service.get_referral_stats,
            user_id=user_id
        )
        
        return ReferralStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting referral stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get referral statistics: {str(e)}"
        )


@router.get("/points", response_model=PointsResponse, summary="Get user's points balance")
@handle_http_errors("Error getting points balance")
async def get_user_points(
    current_user: User = Depends(get_current_active_user)
) -> PointsResponse:
    """
    Get user's points balance and history.
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        user_id = str(current_user.id)
        
        points_data = await asyncio.to_thread(
            referral_service.get_user_points,
            user_id=user_id
        )
        
        return PointsResponse(**points_data)
    except Exception as e:
        logger.error(f"Error getting points: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get points balance: {str(e)}"
        )


@router.post("/redeem", summary="Redeem points for rewards")
@handle_http_errors("Error redeeming points")
async def redeem_points(
    request: RedeemPointsRequest,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Redeem points for rewards (e.g., custom voice, premium features).
    
    - **reward_type**: Type of reward to redeem (e.g., 'custom_voice')
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        user_id = str(current_user.id)
        
        result = await asyncio.to_thread(
            referral_service.redeem_points,
            user_id=user_id,
            reward_type=request.reward_type,
            voice_name=request.voice_name
        )
        
        logger.info(f"User {user_id} redeemed {request.reward_type}")
        
        return {
            "success": True,
            "message": f"Successfully redeemed {request.reward_type}",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error redeeming points: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to redeem points: {str(e)}"
        )


@router.get("/rewards", response_model=RewardsResponse, summary="Get available rewards and point costs")
@handle_http_errors("Error getting rewards")
async def get_rewards(
    current_user: User = Depends(get_current_active_user)
) -> RewardsResponse:
    """
    Get available rewards and their point costs.
    
    Shows all available TTS voices organized by grade with their point costs.
    
    Requires: Valid JWT token in Authorization header.
    """
    try:
        from app.config import VOICE_DESCRIPTIONS, AVAILABLE_VOICES
        import re
        
        user_id = str(current_user.id)
        
        # Get user's points balance
        points_data = await asyncio.to_thread(
            referral_service.get_user_points,
            user_id=user_id
        )
        
        points_balance = points_data["total_points"]
        
        # Get already redeemed voices
        redeemed_voices = [r.replace('voice:', '') for r in points_data.get("rewards_redeemed", []) if r.startswith('voice:')]
        
        # Organize voices by grade
        rewards = []
        
        for voice_name in AVAILABLE_VOICES:
            voice_desc = VOICE_DESCRIPTIONS.get(voice_name, "")
            
            # Extract grade from description
            grade_match = re.search(r'Grade\s+([A-F][+-]?)', voice_desc)
            if not grade_match:
                continue
            
            grade = grade_match.group(1)
            points_cost = VOICE_GRADE_POINTS.get(grade, 0)
            
            if points_cost == 0:
                continue
            
            # Check if already redeemed
            is_redeemed = voice_name in redeemed_voices
            
            # Extract voice description without grade
            voice_display = voice_desc.split(' - Grade')[0].strip()
            
            rewards.append({
                "type": "voice",
                "voice_name": voice_name,
                "name": voice_display,
                "description": f"Grade {grade} TTS Voice",
                "grade": grade,
                "points_cost": points_cost,
                "available": points_balance >= points_cost and not is_redeemed,
                "redeemed": is_redeemed
            })
        
        # Sort by grade (A to F) and then by points cost (descending)
        grade_order = {'A': 0, 'A-': 1, 'B+': 2, 'B': 3, 'B-': 4, 'C+': 5, 'C': 6, 'C-': 7, 
                      'D+': 8, 'D': 9, 'D-': 10, 'F+': 11, 'F': 12}
        
        def sort_key(r):
            grade = r.get('grade', 'F')
            base_grade = grade[0]
            modifier = grade[1:] if len(grade) > 1 else ''
            # Sort by grade order, then by points cost descending
            return (grade_order.get(base_grade, 99), -r.get('points_cost', 0))
        
        rewards.sort(key=sort_key)
        
        # Convert to VoiceReward objects
        voice_rewards = [VoiceReward(**r) for r in rewards]
        
        return RewardsResponse(
            rewards=voice_rewards,
            points_balance=points_balance
        )
    except Exception as e:
        logger.error(f"Error getting rewards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get rewards: {str(e)}"
        )

