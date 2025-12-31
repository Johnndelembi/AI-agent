"""
Engagement Service - Write operations for user engagement data.

This service handles writing engagement data, form submissions, and preferences.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from app.models.engagement import UserEngagement
from app.config import logger


class EngagementService:
    """
    Service for managing user engagement data (write operations).
    
    This service handles:
    - Saving user engagement form submissions
    - Updating email preferences
    - Tracking engagement status
    """
    
    def save_user_engagement_data(
        self,
        user_id: str,
        use_case: Optional[str] = None,
        profession: Optional[str] = None,
        interests: Optional[list] = None,
        goals: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save user engagement data from form submission.
        
        Args:
            user_id: User ID
            use_case: How they use Artemis
            profession: What they do for a living
            interests: List of interests
            goals: What they want to achieve
            
        Returns:
            Dictionary with saved engagement data
        """
        try:
            # Get or create user engagement
            engagement = UserEngagement.objects(user_id=user_id).first()
            
            if not engagement:
                engagement = UserEngagement(user_id=user_id)
            
            # Update fields if provided
            if use_case is not None:
                engagement.use_case = use_case
            if profession is not None:
                engagement.profession = profession
            if interests is not None:
                engagement.interests = interests
            if goals is not None:
                engagement.goals = goals
            
            # Mark info as collected
            engagement.mark_info_collected()
            engagement.save()
            
            logger.info(f"Saved engagement data for user {user_id}")
            
            return engagement.to_dict()
            
        except Exception as e:
            logger.error(f"Error saving engagement data for user {user_id}: {e}")
            raise
    
    def update_email_preferences(
        self,
        user_id: str,
        email_opt_in: Optional[bool] = None,
        email_frequency: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update user email preferences.
        
        Args:
            user_id: User ID
            email_opt_in: Whether user wants to receive emails
            email_frequency: Email frequency preference (daily, weekly, biweekly, monthly)
            
        Returns:
            Dictionary with updated preferences
        """
        try:
            # Get or create user engagement
            engagement = UserEngagement.objects(user_id=user_id).first()
            
            if not engagement:
                engagement = UserEngagement(user_id=user_id)
            
            # Update preferences if provided
            if email_opt_in is not None:
                engagement.email_opt_in = email_opt_in
            if email_frequency is not None:
                if email_frequency not in ['daily', 'weekly', 'biweekly', 'monthly']:
                    raise ValueError(f"Invalid email frequency: {email_frequency}")
                engagement.email_frequency = email_frequency
            
            engagement.save()
            
            logger.info(f"Updated email preferences for user {user_id}")
            
            return {
                'user_id': user_id,
                'email_opt_in': engagement.email_opt_in,
                'email_frequency': engagement.email_frequency
            }
            
        except Exception as e:
            logger.error(f"Error updating email preferences for user {user_id}: {e}")
            raise
    
    def get_user_engagement_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get user engagement statistics.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with engagement statistics
        """
        try:
            engagement = UserEngagement.objects(user_id=user_id).first()
            
            if not engagement:
                return {
                    'user_id': user_id,
                    'has_engagement_data': False,
                    'info_collected': False
                }
            
            return {
                'user_id': user_id,
                'has_engagement_data': True,
                'info_collected': engagement.info_collected,
                'use_case': engagement.use_case,
                'profession': engagement.profession,
                'interests': engagement.interests,
                'goals': engagement.goals,
                'email_opt_in': engagement.email_opt_in,
                'email_frequency': engagement.email_frequency,
                'created_at': engagement.created_at.isoformat() if engagement.created_at else None,
                'updated_at': engagement.updated_at.isoformat() if engagement.updated_at else None
            }
            
        except Exception as e:
            # Check if it's an index error - handle gracefully
            error_str = str(e)
            if 'IndexKeySpecsConflict' in error_str or 'index' in error_str.lower():
                logger.warning(f"Index conflict when getting engagement stats for user {user_id}: {e}")
                # Try to get data even with index conflict
                try:
                    from mongoengine.connection import get_db
                    db = get_db()
                    engagement_doc = db['user_engagements'].find_one({'user_id': user_id})
                    if engagement_doc:
                        return {
                            'user_id': user_id,
                            'has_engagement_data': True,
                            'info_collected': engagement_doc.get('info_collected', False),
                            'use_case': engagement_doc.get('use_case'),
                            'profession': engagement_doc.get('profession'),
                            'interests': engagement_doc.get('interests', []),
                            'goals': engagement_doc.get('goals'),
                            'email_opt_in': engagement_doc.get('email_opt_in', True),
                            'email_frequency': engagement_doc.get('email_frequency', 'daily'),
                            'created_at': engagement_doc.get('created_at').isoformat() if engagement_doc.get('created_at') else None,
                            'updated_at': engagement_doc.get('updated_at').isoformat() if engagement_doc.get('updated_at') else None
                        }
                except Exception:
                    pass
            
            logger.error(f"Error getting engagement stats for user {user_id}: {e}")
            # Return proper structure even on error
            return {
                'user_id': user_id,
                'has_engagement_data': False,
                'info_collected': False
            }


# Singleton instance
engagement_service = EngagementService()

