"""
Admin Service - Read operations for admin dashboard.

This service handles:
- User management and listing
- Email tracking and history
- Referral statistics
- User activity metrics
- Dashboard statistics
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from app.models.auth import User
from app.models.email_log import EmailLog
from app.models.engagement import Referral, ReferralCode, UserPoints, UserEngagement
from app.models.database import Conversation
from app.config import logger


class AdminService:
    """
    Service for admin dashboard operations (read operations).
    
    This service handles:
    - User listing and details
    - Email tracking and history
    - Referral statistics
    - User activity metrics
    - Dashboard overview statistics
    """
    
    def get_all_users(
        self,
        page: int = 1,
        page_size: int = 50,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        is_admin: Optional[bool] = None,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get paginated list of users with filters.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            is_active: Filter by active status
            is_verified: Filter by verified status
            is_admin: Filter by admin status
            search: Search by email or name
            start_date: Filter users created after this date
            end_date: Filter users created before this date
            
        Returns:
            Dictionary with users list and pagination info
        """
        try:
            query = User.objects()
            
            # Apply filters
            if is_active is not None:
                query = query.filter(is_active=is_active)
            if is_verified is not None:
                query = query.filter(is_verified=is_verified)
            if is_admin is not None:
                query = query.filter(is_admin=is_admin)
            if start_date:
                query = query.filter(created_at__gte=start_date)
            if end_date:
                query = query.filter(created_at__lte=end_date)
            if search:
                # Search by email or fullname
                query = query.filter(
                    __raw__={
                        "$or": [
                            {"email": {"$regex": search, "$options": "i"}},
                            {"fullname": {"$regex": search, "$options": "i"}},
                            {"first_name": {"$regex": search, "$options": "i"}},
                            {"last_name": {"$regex": search, "$options": "i"}}
                        ]
                    }
                )
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            skip = (page - 1) * page_size
            users = query.order_by('-created_at').skip(skip).limit(page_size)
            
            # Convert to dict (excluding password)
            users_list = [user.to_dict(include_sensitive=False) for user in users]
            
            return {
                "users": users_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            raise
    
    def get_user_details(self, user_id: str) -> Dict[str, Any]:
        """
        Get complete user details with all related data.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with complete user information
        """
        try:
            user = User.get_by_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Get user data
            user_data = user.to_dict(include_sensitive=False)
            
            # Get engagement data
            engagement = UserEngagement.objects(user_id=user_id).first()
            engagement_data = engagement.to_dict() if engagement else None
            
            # Get points data
            points = UserPoints.objects(user_id=user_id).first()
            points_data = points.to_dict() if points else None
            
            # Get referral code
            referral_code = ReferralCode.objects(user_id=user_id).first()
            referral_code_data = referral_code.to_dict() if referral_code else None
            
            # Get referrals made by this user
            referrals_made = Referral.objects(referrer_id=user_id)
            referrals_made_data = [r.to_dict() for r in referrals_made]
            
            # Get referral received (if this user was referred)
            referral_received = Referral.objects(referred_user_id=user_id).first()
            referral_received_data = referral_received.to_dict() if referral_received else None
            
            # Get conversation count
            conversation_count = Conversation.objects(user_id=user_id).count()
            
            # Get email count
            email_count = EmailLog.objects(user_id=user_id).count()
            
            return {
                "user": user_data,
                "engagement": engagement_data,
                "points": points_data,
                "referral_code": referral_code_data,
                "referrals_made": referrals_made_data,
                "referral_received": referral_received_data,
                "conversation_count": conversation_count,
                "email_count": email_count
            }
            
        except Exception as e:
            logger.error(f"Error getting user details for {user_id}: {e}")
            raise
    
    def get_email_logs(
        self,
        user_id: Optional[str] = None,
        email_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Get email logs with filters.
        
        Args:
            user_id: Filter by user ID
            email_type: Filter by email type
            start_date: Filter emails sent after this date
            end_date: Filter emails sent before this date
            page: Page number
            page_size: Number of items per page
            
        Returns:
            Dictionary with email logs and pagination info
        """
        try:
            query = EmailLog.objects()
            
            # Apply filters
            if user_id:
                query = query.filter(user_id=user_id)
            if email_type:
                query = query.filter(email_type=email_type)
            if start_date:
                query = query.filter(sent_at__gte=start_date)
            if end_date:
                query = query.filter(sent_at__lte=end_date)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            skip = (page - 1) * page_size
            logs = query.order_by('-sent_at').skip(skip).limit(page_size)
            
            # Convert to dict
            logs_list = [log.to_dict() for log in logs]
            
            return {
                "logs": logs_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error getting email logs: {e}")
            raise
    
    def get_user_email_history(
        self,
        user_id: str,
        email_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get email history for a specific user.
        
        Args:
            user_id: User ID
            email_type: Optional filter by email type
            limit: Maximum number of results
            
        Returns:
            List of email log dictionaries
        """
        try:
            logs = EmailLog.get_user_emails(user_id, email_type=email_type, limit=limit)
            return [log.to_dict() for log in logs]
            
        except Exception as e:
            logger.error(f"Error getting email history for user {user_id}: {e}")
            raise
    
    def get_referral_stats(self) -> Dict[str, Any]:
        """
        Get aggregate referral statistics.
        
        Returns:
            Dictionary with referral statistics
        """
        try:
            # Total referrals
            total_referrals = Referral.objects().count()
            
            # Successful referrals (points awarded)
            successful_referrals = Referral.objects(points_awarded=True).count()
            
            # Total points awarded
            referrals_with_points = Referral.objects(points_awarded=True)
            total_points_awarded = sum(r.points_amount for r in referrals_with_points)
            
            # Top referrers
            pipeline = [
                {"$match": {"points_awarded": True}},
                {"$group": {
                    "_id": "$referrer_id",
                    "count": {"$sum": 1},
                    "total_points": {"$sum": "$points_amount"}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            top_referrers = list(Referral.objects().aggregate(*pipeline))
            
            # Get user details for top referrers
            top_referrers_with_details = []
            for ref in top_referrers:
                user = User.get_by_id(ref["_id"])
                if user:
                    top_referrers_with_details.append({
                        "user_id": ref["_id"],
                        "email": user.email,
                        "fullname": user.fullname or f"{user.first_name} {user.last_name}".strip(),
                        "referral_count": ref["count"],
                        "total_points": ref["total_points"]
                    })
            
            return {
                "total_referrals": total_referrals,
                "successful_referrals": successful_referrals,
                "total_points_awarded": total_points_awarded,
                "top_referrers": top_referrers_with_details
            }
            
        except Exception as e:
            logger.error(f"Error getting referral stats: {e}")
            raise
    
    def get_user_referrals(self, user_id: str) -> Dict[str, Any]:
        """
        Get referrals made by a specific user.
        
        Args:
            user_id: User ID (referrer)
            
        Returns:
            Dictionary with referral information
        """
        try:
            # Get referrals made by this user
            referrals = Referral.objects(referrer_id=user_id)
            
            # Get referral code
            referral_code = ReferralCode.objects(user_id=user_id).first()
            
            referrals_list = []
            for ref in referrals:
                ref_dict = ref.to_dict()
                # Get referred user details
                referred_user = User.get_by_id(ref.referred_user_id)
                if referred_user:
                    ref_dict["referred_user"] = {
                        "id": str(referred_user.id),
                        "email": referred_user.email,
                        "fullname": referred_user.fullname or f"{referred_user.first_name} {referred_user.last_name}".strip()
                    }
                referrals_list.append(ref_dict)
            
            return {
                "referral_code": referral_code.to_dict() if referral_code else None,
                "total_referrals": referrals.count(),
                "successful_referrals": referrals.filter(points_awarded=True).count(),
                "referrals": referrals_list
            }
            
        except Exception as e:
            logger.error(f"Error getting referrals for user {user_id}: {e}")
            raise
    
    def get_user_activity_metrics(self, user_id: str) -> Dict[str, Any]:
        """
        Get user activity metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with activity metrics
        """
        try:
            user = User.get_by_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Get conversation count
            conversation_count = Conversation.objects(user_id=user_id).count()
            
            # Get total messages across all conversations
            conversations = Conversation.objects(user_id=user_id)
            total_messages = sum(conv.message_count for conv in conversations)
            
            # Get email count
            email_count = EmailLog.objects(user_id=user_id).count()
            
            # Get last email sent
            last_email = EmailLog.objects(user_id=user_id).order_by('-sent_at').first()
            
            # Calculate days since last login
            days_since_login = None
            if user.last_login:
                days_since_login = (datetime.utcnow() - user.last_login).days
            
            # Calculate days since account creation
            days_since_creation = None
            if user.created_at:
                days_since_creation = (datetime.utcnow() - user.created_at).days
            
            return {
                "user_id": user_id,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "days_since_login": days_since_login,
                "account_created_at": user.created_at.isoformat() if user.created_at else None,
                "days_since_creation": days_since_creation,
                "conversation_count": conversation_count,
                "total_messages": total_messages,
                "email_count": email_count,
                "last_email_sent": last_email.to_dict() if last_email else None
            }
            
        except Exception as e:
            logger.error(f"Error getting activity metrics for user {user_id}: {e}")
            raise
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get dashboard overview statistics.
        
        Returns:
            Dictionary with dashboard statistics
        """
        try:
            # User statistics
            total_users = User.objects().count()
            active_users = User.objects(is_active=True).count()
            verified_users = User.objects(is_verified=True).count()
            admin_users = User.objects(is_admin=True).count()
            
            # New users in last 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            new_users_7d = User.objects(created_at__gte=seven_days_ago).count()
            
            # New users in last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            new_users_30d = User.objects(created_at__gte=thirty_days_ago).count()
            
            # Email statistics
            total_emails = EmailLog.objects().count()
            emails_7d = EmailLog.objects(sent_at__gte=seven_days_ago).count()
            emails_30d = EmailLog.objects(sent_at__gte=thirty_days_ago).count()
            
            # Email type breakdown
            email_types = ['welcome', 're_engagement', 'curated', 'referral_campaign', 'points_notification', 'engagement_form']
            email_type_counts = {}
            for email_type in email_types:
                email_type_counts[email_type] = EmailLog.objects(email_type=email_type).count()
            
            # Referral statistics
            total_referrals = Referral.objects().count()
            successful_referrals = Referral.objects(points_awarded=True).count()
            
            # Conversation statistics
            total_conversations = Conversation.objects().count()
            total_messages = sum(conv.message_count for conv in Conversation.objects())
            
            # Active users (logged in last 7 days)
            active_users_7d = User.objects(last_login__gte=seven_days_ago).count()
            
            return {
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "verified": verified_users,
                    "admins": admin_users,
                    "new_7d": new_users_7d,
                    "new_30d": new_users_30d,
                    "active_7d": active_users_7d
                },
                "emails": {
                    "total": total_emails,
                    "sent_7d": emails_7d,
                    "sent_30d": emails_30d,
                    "by_type": email_type_counts
                },
                "referrals": {
                    "total": total_referrals,
                    "successful": successful_referrals
                },
                "conversations": {
                    "total": total_conversations,
                    "total_messages": total_messages
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            raise


# Singleton instance
admin_service = AdminService()

