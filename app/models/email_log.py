"""
Email log model for tracking all email sends to users.
Tracks email types, recipients, status, and metadata.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from mongoengine import (
    Document,
    StringField,
    BooleanField,
    DateTimeField,
    DictField
)


class EmailLog(Document):
    """Email log for tracking all email sends."""
    
    meta = {
        'collection': 'email_logs',
        'indexes': [
            'user_id',
            'email_type',
            'sent_at',
            'status',
            ('user_id', 'email_type'),
            ('user_id', 'sent_at'),
            ('email_type', 'sent_at')
        ]
    }
    
    user_id = StringField(required=True)  # User who received the email
    email_type = StringField(
        required=True,
        choices=[
            'welcome',
            're_engagement',
            'curated',
            'referral_campaign',
            'points_notification',
            'engagement_form',
            'notification',
            'other'
        ]
    )
    recipient_email = StringField(required=True)
    subject = StringField(required=True)
    sent_at = DateTimeField(default=datetime.utcnow)
    status = StringField(
        required=True,
        default='sent',
        choices=['sent', 'failed']
    )
    metadata = DictField(default={})  # Additional data (points_amount, referral_code, etc.)
    
    def save(self, *args, **kwargs):
        """Override save to ensure sent_at is set."""
        if not self.sent_at:
            self.sent_at = datetime.utcnow()
        return super(EmailLog, self).save(*args, **kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'user_id': self.user_id,
            'email_type': self.email_type,
            'recipient_email': self.recipient_email,
            'subject': self.subject,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status,
            'metadata': self.metadata
        }
    
    @classmethod
    def create_log(
        cls,
        user_id: str,
        email_type: str,
        recipient_email: str,
        subject: str,
        status: str = 'sent',
        metadata: Optional[Dict] = None
    ) -> 'EmailLog':
        """
        Create a new email log entry.
        
        Args:
            user_id: User ID who received the email
            email_type: Type of email (welcome, re_engagement, etc.)
            recipient_email: Recipient email address
            subject: Email subject
            status: Email status (sent, failed)
            metadata: Optional metadata dictionary
            
        Returns:
            EmailLog instance
        """
        log = cls(
            user_id=user_id,
            email_type=email_type,
            recipient_email=recipient_email,
            subject=subject,
            status=status,
            metadata=metadata or {}
        )
        log.save()
        return log
    
    @classmethod
    def get_user_emails(
        cls,
        user_id: str,
        email_type: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """
        Get email logs for a specific user.
        
        Args:
            user_id: User ID
            email_type: Optional filter by email type
            limit: Maximum number of results
            
        Returns:
            List of EmailLog instances
        """
        query = cls.objects(user_id=user_id)
        if email_type:
            query = query.filter(email_type=email_type)
        return query.order_by('-sent_at').limit(limit)
    
    @classmethod
    def get_emails_by_type(
        cls,
        email_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> list:
        """
        Get email logs by type within date range.
        
        Args:
            email_type: Email type to filter
            start_date: Optional start date
            end_date: Optional end date
            limit: Maximum number of results
            
        Returns:
            List of EmailLog instances
        """
        query = cls.objects(email_type=email_type)
        if start_date:
            query = query.filter(sent_at__gte=start_date)
        if end_date:
            query = query.filter(sent_at__lte=end_date)
        return query.order_by('-sent_at').limit(limit)

