"""
Engagement Reader Service - Read-only service for querying engagement data.

This service provides read-only access to engagement, referral, and user data
for email sending purposes. All database operations are read-only.
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from mongoengine import DoesNotExist

from app.models.auth import User
from app.models.database import Conversation
from app.config import logger

# Try to import engagement models (they may not exist yet in this branch)
try:
    from app.models.engagement import UserEngagement, ReferralCode, Referral, UserPoints
    ENGAGEMENT_MODELS_AVAILABLE = True
except ImportError:
    ENGAGEMENT_MODELS_AVAILABLE = False
    logger.warning("Engagement models not available - some features may be limited")


class EngagementReaderService:
    """
    Read-only service for querying engagement data from database.
    
    This service only performs read operations to determine which users
    should receive which emails based on their engagement status.
    """
    
    def __init__(self):
        """Initialize the engagement reader service."""
        self.engagement_enabled = os.getenv("ENGAGEMENT_ENABLED", "true").lower() == "true"
        self.re_engagement_threshold_days = int(os.getenv("RE_ENGAGEMENT_THRESHOLD_DAYS", "3"))
        self.min_chats_for_engagement = int(os.getenv("MIN_CHATS_FOR_ENGAGEMENT", "5"))
    
    def get_new_users(self, hours_ago: int = 1) -> List[Dict[str, Any]]:
        """
        Get users registered in the last N hours (for welcome emails).
        
        Args:
            hours_ago: Number of hours ago to check (default: 1)
            
        Returns:
            List of user dictionaries with email, fullname, and user_id
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_ago)
            
            # Get users created in the time window
            users = User.objects(
                created_at__gte=cutoff_time,
                is_active=True
            ).only('id', 'email', 'first_name', 'last_name', 'fullname', 'created_at')
            
            result = []
            for user in users:
                result.append({
                    'user_id': str(user.id),
                    'email': user.email,
                    'fullname': user.fullname or f"{user.first_name} {user.last_name}".strip() or "there",
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'created_at': user.created_at
                })
            
            logger.info(f"Found {len(result)} new users registered in last {hours_ago} hour(s)")
            return result
            
        except Exception as e:
            logger.error(f"Error getting new users: {e}")
            return []
    
    def get_inactive_users(self) -> List[Dict[str, Any]]:
        """
        Get users who haven't had a chat conversation in the last N days.
        
        Returns:
            List of user dictionaries with email, fullname, and last activity info
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=self.re_engagement_threshold_days)
            
            # Get all active users
            all_users = User.objects(is_active=True).only('id', 'email', 'first_name', 'last_name', 'fullname')
            
            inactive_users = []
            for user in all_users:
                user_id = str(user.id)
                
                # Find the most recent conversation for this user
                latest_conversation = Conversation.objects(
                    user_id=user_id
                ).order_by('-last_message_at').first()
                
                # Check if user is inactive (no conversation or last message > threshold days ago)
                is_inactive = False
                last_activity = None
                
                if not latest_conversation:
                    # User has never had a conversation
                    is_inactive = True
                    last_activity = user.created_at
                elif latest_conversation.last_message_at < cutoff_time:
                    # Last message was more than threshold days ago
                    is_inactive = True
                    last_activity = latest_conversation.last_message_at
                
                if is_inactive:
                    inactive_users.append({
                        'user_id': user_id,
                        'email': user.email,
                        'fullname': user.fullname or f"{user.first_name} {user.last_name}".strip() or "there",
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'last_activity': last_activity
                    })
            
            logger.info(f"Found {len(inactive_users)} inactive users (no activity in {self.re_engagement_threshold_days} days)")
            return inactive_users
            
        except Exception as e:
            logger.error(f"Error getting inactive users: {e}")
            return []
    
    def get_active_users_for_engagement(self) -> List[Dict[str, Any]]:
        """
        Get users with 5+ chats who haven't provided engagement information.
        
        Returns:
            List of user dictionaries eligible for engagement form emails
        """
        try:
            # Get all active users
            all_users = User.objects(is_active=True).only('id', 'email', 'first_name', 'last_name', 'fullname')
            
            eligible_users = []
            for user in all_users:
                user_id = str(user.id)
                
                # Count conversations for this user
                conversations = Conversation.objects(user_id=user_id)
                total_chats = sum(conv.message_count for conv in conversations)
                
                # Check if user has provided engagement info (if model exists)
                has_engagement_info = False
                if ENGAGEMENT_MODELS_AVAILABLE:
                    try:
                        engagement = UserEngagement.objects(user_id=user_id).first()
                        if engagement:
                            # Check if user has provided any engagement info
                            use_case = getattr(engagement, 'use_case', None)
                            profession = getattr(engagement, 'profession', None)
                            if use_case or profession:
                                has_engagement_info = True
                    except Exception:
                        pass
                
                # User is eligible if they have 5+ chats and no engagement info
                if total_chats >= self.min_chats_for_engagement and not has_engagement_info:
                    eligible_users.append({
                        'user_id': user_id,
                        'email': user.email,
                        'fullname': user.fullname or f"{user.first_name} {user.last_name}".strip() or "there",
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'total_chats': total_chats
                    })
            
            logger.info(f"Found {len(eligible_users)} active users eligible for engagement form")
            return eligible_users
            
        except Exception as e:
            logger.error(f"Error getting active users for engagement: {e}")
            return []
    
    def get_users_for_curated_emails(self) -> List[Dict[str, Any]]:
        """
        Get users who have provided engagement information and should receive curated emails.
        
        Returns:
            List of user dictionaries with engagement data for personalization
        """
        try:
            if not ENGAGEMENT_MODELS_AVAILABLE:
                logger.warning("Engagement models not available - cannot get users for curated emails")
                return []
            
            # Get users with engagement data
            engagements = UserEngagement.objects()
            
            users_for_curated = []
            for engagement in engagements:
                try:
                    user = User.objects(id=engagement.user_id).first()
                    if not user or not user.is_active:
                        continue
                    
                    # Get engagement data
                    engagement_data = {
                        'use_case': getattr(engagement, 'use_case', ''),
                        'profession': getattr(engagement, 'profession', ''),
                        'interests': getattr(engagement, 'interests', []),
                        'goals': getattr(engagement, 'goals', '')
                    }
                    
                    users_for_curated.append({
                        'user_id': str(user.id),
                        'email': user.email,
                        'fullname': user.fullname or f"{user.first_name} {user.last_name}".strip() or "there",
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'engagement_data': engagement_data
                    })
                except Exception as e:
                    logger.warning(f"Error processing engagement for user {engagement.user_id}: {e}")
                    continue
            
            logger.info(f"Found {len(users_for_curated)} users for curated emails")
            return users_for_curated
            
        except Exception as e:
            logger.error(f"Error getting users for curated emails: {e}")
            return []
    
    def get_users_for_referral_emails(self) -> List[Dict[str, Any]]:
        """
        Get users who should receive referral campaign emails.
        
        Returns:
            List of user dictionaries with referral code and points info
        """
        try:
            # Get active users who have had at least some conversations
            all_users = User.objects(is_active=True).only('id', 'email', 'first_name', 'last_name', 'fullname')
            
            eligible_users = []
            for user in all_users:
                user_id = str(user.id)
                
                # Check if user has conversations (active user)
                has_conversations = Conversation.objects(user_id=user_id).count() > 0
                
                if not has_conversations:
                    continue
                
                # Get referral code (if available)
                referral_code = None
                referral_link = None
                if ENGAGEMENT_MODELS_AVAILABLE:
                    try:
                        ref_code = ReferralCode.objects(user_id=user_id).first()
                        if ref_code:
                            referral_code = ref_code.code
                            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
                            referral_link = f"{frontend_url}/signup?ref={referral_code}"
                    except Exception:
                        pass
                
                # Get points balance (if available)
                points_balance = 0
                if ENGAGEMENT_MODELS_AVAILABLE:
                    try:
                        user_points = UserPoints.objects(user_id=user_id).first()
                        if user_points:
                            points_balance = user_points.total_points or 0
                    except Exception:
                        pass
                
                # Get referral stats (if available)
                referral_count = 0
                if ENGAGEMENT_MODELS_AVAILABLE:
                    try:
                        referral_count = Referral.objects(referrer_id=user_id).count()
                    except Exception:
                        pass
                
                eligible_users.append({
                    'user_id': user_id,
                    'email': user.email,
                    'fullname': user.fullname or f"{user.first_name} {user.last_name}".strip() or "there",
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'referral_code': referral_code,
                    'referral_link': referral_link,
                    'points_balance': points_balance,
                    'referral_count': referral_count
                })
            
            logger.info(f"Found {len(eligible_users)} users eligible for referral campaign emails")
            return eligible_users
            
        except Exception as e:
            logger.error(f"Error getting users for referral emails: {e}")
            return []
    
    def get_user_engagement_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user engagement data for email personalization.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with engagement data or None
        """
        try:
            if not ENGAGEMENT_MODELS_AVAILABLE:
                return None
            
            engagement = UserEngagement.objects(user_id=user_id).first()
            if not engagement:
                return None
            
            return {
                'use_case': getattr(engagement, 'use_case', ''),
                'profession': getattr(engagement, 'profession', ''),
                'interests': getattr(engagement, 'interests', []),
                'goals': getattr(engagement, 'goals', '')
            }
        except Exception as e:
            logger.warning(f"Error getting engagement data for user {user_id}: {e}")
            return None
    
    def get_user_points(self, user_id: str) -> int:
        """
        Get user's points balance.
        
        Args:
            user_id: User ID
            
        Returns:
            Points balance (0 if not available)
        """
        try:
            if not ENGAGEMENT_MODELS_AVAILABLE:
                return 0
            
            user_points = UserPoints.objects(user_id=user_id).first()
            if user_points:
                return user_points.total_points or 0
            return 0
        except Exception as e:
            logger.warning(f"Error getting points for user {user_id}: {e}")
            return 0
    
    def get_referral_code(self, user_id: str) -> Optional[str]:
        """
        Get user's referral code.
        
        Args:
            user_id: User ID
            
        Returns:
            Referral code or None
        """
        try:
            if not ENGAGEMENT_MODELS_AVAILABLE:
                return None
            
            ref_code = ReferralCode.objects(user_id=user_id).first()
            if ref_code:
                return ref_code.code
            return None
        except Exception as e:
            logger.warning(f"Error getting referral code for user {user_id}: {e}")
            return None
    
    def get_referral_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's referral statistics.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with referral statistics
        """
        try:
            stats = {
                'referral_count': 0,
                'points_earned': 0,
                'points_balance': 0
            }
            
            if not ENGAGEMENT_MODELS_AVAILABLE:
                return stats
            
            # Get referral count
            try:
                stats['referral_count'] = Referral.objects(referrer_id=user_id).count()
            except Exception:
                pass
            
            # Get points balance
            try:
                user_points = UserPoints.objects(user_id=user_id).first()
                if user_points:
                    stats['points_balance'] = user_points.total_points or 0
                    # Calculate points earned from referrals (if history available)
                    points_history = getattr(user_points, 'points_history', None)
                    if points_history:
                        for entry in points_history:
                            if isinstance(entry, dict):
                                if entry.get('source') == 'referral':
                                    stats['points_earned'] += entry.get('amount', 0)
                            elif hasattr(entry, 'source') and entry.source == 'referral':
                                stats['points_earned'] += getattr(entry, 'amount', 0)
            except Exception:
                pass
            
            return stats
        except Exception as e:
            logger.warning(f"Error getting referral stats for user {user_id}: {e}")
            return {'referral_count': 0, 'points_earned': 0, 'points_balance': 0}
    
    def get_users_with_recent_points_awards(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get users who received points in the last N hours (for notification emails).
        
        Args:
            hours: Number of hours to look back (default: 24)
            
        Returns:
            List of user dictionaries who received points
        """
        try:
            if not ENGAGEMENT_MODELS_AVAILABLE:
                return []
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Get users with points history entries in the time window
            users_with_points = []
            
            try:
                all_user_points = UserPoints.objects()
                for user_points in all_user_points:
                    if not user_points.points_history:
                        continue
                    
                    # Check if there are recent points awards
                    points_history = getattr(user_points, 'points_history', None)
                    if not points_history:
                        continue
                    
                    recent_awards = []
                    for entry in points_history:
                        if isinstance(entry, dict):
                            entry_timestamp = entry.get('timestamp')
                            entry_type = entry.get('type')
                            entry_amount = entry.get('amount', 0)
                        else:
                            entry_timestamp = getattr(entry, 'timestamp', None)
                            entry_type = getattr(entry, 'type', None)
                            entry_amount = getattr(entry, 'amount', 0)
                        
                        if entry_timestamp and entry_type == 'earned':
                            # Handle both datetime objects and ISO strings
                            if isinstance(entry_timestamp, str):
                                try:
                                    entry_timestamp = datetime.fromisoformat(entry_timestamp.replace('Z', '+00:00'))
                                except:
                                    continue
                            
                            if entry_timestamp >= cutoff_time:
                                recent_awards.append({
                                    'amount': entry_amount,
                                    'timestamp': entry_timestamp,
                                    'source': entry.get('source') if isinstance(entry, dict) else getattr(entry, 'source', None)
                                })
                    
                    if recent_awards:
                        # Get user info
                        try:
                            user = User.objects(id=user_points.user_id).first()
                            if user and user.is_active:
                                total_recent_points = sum(award.get('amount', 0) for award in recent_awards)
                                users_with_points.append({
                                    'user_id': str(user.id),
                                    'email': user.email,
                                    'fullname': user.fullname or f"{user.first_name} {user.last_name}".strip() or "there",
                                    'points_awarded': total_recent_points,
                                    'awards': recent_awards
                                })
                        except Exception as e:
                            logger.warning(f"Error getting user {user_points.user_id}: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Error querying user points: {e}")
            
            logger.info(f"Found {len(users_with_points)} users with recent points awards")
            return users_with_points
            
        except Exception as e:
            logger.error(f"Error getting users with recent points: {e}")
            return []


# Singleton instance
engagement_reader_service = EngagementReaderService()

