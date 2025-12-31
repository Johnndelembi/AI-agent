"""
Referral Service - Write operations for referral system and points.

This service handles:
- Referral code generation
- Referral tracking
- Points awarding
- Points redemption
"""

import os
import random
import string
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.engagement import ReferralCode, Referral, UserPoints
from app.models.database import Conversation
from app.config import logger

# Configuration
POINTS_PER_REFERRAL = int(os.getenv("POINTS_PER_REFERRAL", "100"))
CUSTOM_VOICE_POINTS_COST = int(os.getenv("CUSTOM_VOICE_POINTS_COST", "500"))
MIN_CHATS_FOR_REFERRAL_POINTS = int(os.getenv("MIN_CHATS_FOR_REFERRAL_POINTS", "5"))


class ReferralService:
    """
    Service for managing referrals and points system (write operations).
    
    This service handles:
    - Generating unique referral codes
    - Tracking referrals when users sign up
    - Checking engagement milestones
    - Awarding points when milestones are reached
    - Redeeming points for rewards
    """
    
    def generate_referral_code(self, user_id: str) -> str:
        """
        Generate a unique referral code for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Unique referral code (e.g., "ARTEMIS-ABC123")
        """
        try:
            # Check if user already has a referral code
            existing_code = ReferralCode.objects(user_id=user_id).first()
            if existing_code:
                return existing_code.code
            
            # Generate unique code
            max_attempts = 10
            for _ in range(max_attempts):
                # Generate code: ARTEMIS-XXXXXX (6 random alphanumeric)
                random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                code = f"ARTEMIS-{random_part}"
                
                # Check if code already exists
                if not ReferralCode.objects(code=code).first():
                    # Create new referral code
                    referral_code = ReferralCode(
                        user_id=user_id,
                        code=code
                    )
                    referral_code.save()
                    
                    logger.info(f"Generated referral code {code} for user {user_id}")
                    return code
            
            raise Exception("Failed to generate unique referral code after multiple attempts")
            
        except Exception as e:
            logger.error(f"Error generating referral code for user {user_id}: {e}")
            raise
    
    def get_referral_code(self, user_id: str) -> Optional[str]:
        """
        Get user's referral code, creating one if it doesn't exist.
        
        Args:
            user_id: User ID
            
        Returns:
            Referral code or None
        """
        try:
            referral_code = ReferralCode.objects(user_id=user_id).first()
            if referral_code:
                return referral_code.code
            else:
                # Generate new code if doesn't exist
                return self.generate_referral_code(user_id)
        except Exception as e:
            logger.error(f"Error getting referral code for user {user_id}: {e}")
            return None
    
    def track_referral(self, referral_code: str, referred_user_id: str) -> Dict[str, Any]:
        """
        Track a referral when a new user signs up with a referral code.
        
        Args:
            referral_code: The referral code used
            referred_user_id: ID of the user who was referred
            
        Returns:
            Dictionary with referral tracking info
        """
        try:
            # Find the referrer by code
            ref_code_obj = ReferralCode.objects(code=referral_code, is_active=True).first()
            if not ref_code_obj:
                raise ValueError(f"Invalid or inactive referral code: {referral_code}")
            
            referrer_id = ref_code_obj.user_id
            
            # Check if referral already exists
            existing_referral = Referral.objects(referred_user_id=referred_user_id).first()
            if existing_referral:
                logger.warning(f"Referral already exists for user {referred_user_id}")
                return existing_referral.to_dict()
            
            # Create new referral
            referral = Referral(
                referrer_id=referrer_id,
                referred_user_id=referred_user_id,
                referral_code=referral_code
            )
            referral.save()
            
            # Increment usage count
            ref_code_obj.increment_usage()
            
            logger.info(f"Tracked referral: {referrer_id} referred {referred_user_id} with code {referral_code}")
            
            return referral.to_dict()
            
        except Exception as e:
            logger.error(f"Error tracking referral: {e}")
            raise
    
    def check_engagement_milestones(self, referred_user_id: str) -> Dict[str, Any]:
        """
        Check if referred user has reached engagement milestones (e.g., 5+ chats).
        
        Args:
            referred_user_id: ID of the referred user
            
        Returns:
            Dictionary with milestone status
        """
        try:
            # Find referral
            referral = Referral.objects(referred_user_id=referred_user_id).first()
            if not referral:
                return {
                    'has_referral': False,
                    'milestones_reached': []
                }
            
            # Count conversations for referred user
            conversations = Conversation.objects(user_id=referred_user_id)
            total_chats = sum(conv.message_count for conv in conversations)
            
            milestones_reached = []
            
            # Check 5 chats milestone
            if total_chats >= MIN_CHATS_FOR_REFERRAL_POINTS:
                milestone = '5_chats'
                if milestone not in referral.engagement_milestones:
                    milestones_reached.append(milestone)
                    referral.mark_milestone_reached(milestone)
            
            return {
                'has_referral': True,
                'referrer_id': referral.referrer_id,
                'total_chats': total_chats,
                'milestones_reached': milestones_reached,
                'points_awarded': referral.points_awarded
            }
            
        except Exception as e:
            logger.error(f"Error checking milestones for user {referred_user_id}: {e}")
            return {
                'has_referral': False,
                'error': str(e)
            }
    
    def award_referral_points(self, referrer_id: str, milestone: str = '5_chats') -> Dict[str, Any]:
        """
        Award points to referrer when referred user reaches a milestone.
        
        Args:
            referrer_id: ID of the referrer
            milestone: Milestone reached (e.g., '5_chats')
            
        Returns:
            Dictionary with points award info
        """
        try:
            # Find referral by referrer and milestone
            referrals = Referral.objects(
                referrer_id=referrer_id,
                engagement_milestones__in=[milestone],
                points_awarded=False
            )
            
            points_awarded = 0
            referrals_processed = []
            
            for referral in referrals:
                # Award points
                points_amount = POINTS_PER_REFERRAL
                
                # Get or create user points
                user_points = UserPoints.objects(user_id=referrer_id).first()
                if not user_points:
                    user_points = UserPoints(user_id=referrer_id)
                
                # Add points
                user_points.add_points(
                    amount=points_amount,
                    source='referral',
                    description=f"Referral milestone reached: {milestone}",
                    metadata={
                        'referred_user_id': referral.referred_user_id,
                        'milestone': milestone
                    }
                )
                
                # Mark referral as points awarded
                referral.mark_points_awarded(points_amount)
                
                points_awarded += points_amount
                referrals_processed.append(referral.referred_user_id)
            
            if points_awarded > 0:
                logger.info(f"Awarded {points_awarded} points to referrer {referrer_id} for {len(referrals_processed)} referrals")
            
            return {
                'referrer_id': referrer_id,
                'points_awarded': points_awarded,
                'referrals_processed': referrals_processed,
                'milestone': milestone
            }
            
        except Exception as e:
            logger.error(f"Error awarding points to referrer {referrer_id}: {e}")
            raise
    
    def get_user_points(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's points balance and history.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with points info
        """
        try:
            user_points = UserPoints.objects(user_id=user_id).first()
            
            if not user_points:
                return {
                    'user_id': user_id,
                    'total_points': 0,
                    'rewards_redeemed': [],
                    'points_history_count': 0
                }
            
            return user_points.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting points for user {user_id}: {e}")
            return {
                'user_id': user_id,
                'total_points': 0,
                'error': str(e)
            }
    
    def redeem_points(self, user_id: str, reward_type: str) -> Dict[str, Any]:
        """
        Redeem points for a reward.
        
        Args:
            user_id: User ID
            reward_type: Type of reward (e.g., 'custom_voice')
            
        Returns:
            Dictionary with redemption info
        """
        try:
            # Get user points
            user_points = UserPoints.objects(user_id=user_id).first()
            if not user_points:
                raise ValueError("User has no points account")
            
            # Determine points cost
            reward_costs = {
                'custom_voice': CUSTOM_VOICE_POINTS_COST,
                # Add more rewards here
            }
            
            if reward_type not in reward_costs:
                raise ValueError(f"Unknown reward type: {reward_type}")
            
            points_cost = reward_costs[reward_type]
            
            # Check if user has enough points
            if user_points.total_points < points_cost:
                raise ValueError(
                    f"Insufficient points. Balance: {user_points.total_points}, Required: {points_cost}"
                )
            
            # Check if already redeemed
            if reward_type in user_points.rewards_redeemed:
                raise ValueError(f"Reward {reward_type} already redeemed")
            
            # Spend points
            user_points.spend_points(
                amount=points_cost,
                reason='redemption',
                description=f"Redeemed {reward_type}",
                metadata={'reward_type': reward_type}
            )
            
            # Mark reward as redeemed
            user_points.redeem_reward(reward_type)
            
            logger.info(f"User {user_id} redeemed {reward_type} for {points_cost} points")
            
            return {
                'user_id': user_id,
                'reward_type': reward_type,
                'points_spent': points_cost,
                'remaining_points': user_points.total_points,
                'rewards_redeemed': user_points.rewards_redeemed
            }
            
        except Exception as e:
            logger.error(f"Error redeeming points for user {user_id}: {e}")
            raise
    
    def get_referral_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's referral statistics.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with referral statistics
        """
        try:
            # Get referral code
            referral_code = ReferralCode.objects(user_id=user_id).first()
            code = referral_code.code if referral_code else None
            
            # Get referrals
            referrals = Referral.objects(referrer_id=user_id)
            total_referrals = referrals.count()
            successful_referrals = referrals.filter(points_awarded=True).count()
            
            # Get points
            user_points = UserPoints.objects(user_id=user_id).first()
            total_points = user_points.total_points if user_points else 0
            
            # Calculate points from referrals
            points_from_referrals = 0
            if user_points:
                for entry in user_points.points_history:
                    if hasattr(entry, 'source') and entry.source == 'referral':
                        if hasattr(entry, 'amount'):
                            points_from_referrals += entry.amount
                    elif isinstance(entry, dict) and entry.get('source') == 'referral':
                        points_from_referrals += entry.get('amount', 0)
            
            return {
                'user_id': user_id,
                'referral_code': code,
                'total_referrals': total_referrals,
                'successful_referrals': successful_referrals,
                'total_points': total_points,
                'points_from_referrals': points_from_referrals
            }
            
        except Exception as e:
            logger.error(f"Error getting referral stats for user {user_id}: {e}")
            return {
                'user_id': user_id,
                'error': str(e)
            }


# Singleton instance
referral_service = ReferralService()

