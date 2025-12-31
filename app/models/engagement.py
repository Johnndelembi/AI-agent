"""
Engagement models for user engagement tracking, referrals, and points system.

These models handle write operations for:
- User engagement data collection
- Referral code generation and tracking
- Points system and rewards redemption
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from mongoengine import (
    Document,
    StringField,
    IntField,
    BooleanField,
    DateTimeField,
    DictField,
    ListField,
    EmbeddedDocument,
    EmbeddedDocumentField
)


class PointsHistoryEntry(EmbeddedDocument):
    """Embedded document for points history entries."""
    amount = IntField(required=True)
    type = StringField(required=True, choices=['earned', 'spent', 'redeemed'])
    source = StringField()  # e.g., 'referral', 'milestone', 'reward'
    description = StringField()
    timestamp = DateTimeField(default=datetime.utcnow)
    metadata = DictField(default={})


class UserEngagement(Document):
    """User engagement data collected from forms and preferences."""
    
    meta = {
        'collection': 'user_engagements',
        'indexes': [
            'created_at',
            {'fields': ['user_id'], 'unique': True, 'name': 'uniq_user_engagement_user_id'}
        ]
    }
    
    user_id = StringField(required=True)
    
    # Engagement form data
    use_case = StringField(max_length=500)  # How they use Artemis
    profession = StringField(max_length=200)  # What they do for a living
    interests = ListField(StringField(max_length=100), default=list)  # Areas of interest
    goals = StringField(max_length=1000)  # What they want to achieve
    
    # Email tracking
    welcome_sent = BooleanField(default=False)
    welcome_sent_at = DateTimeField(default=None)
    re_engagement_sent = BooleanField(default=False)
    re_engagement_sent_at = DateTimeField(default=None)
    engagement_form_sent = BooleanField(default=False)
    engagement_form_sent_at = DateTimeField(default=None)
    info_collected = BooleanField(default=False)
    info_collected_at = DateTimeField(default=None)
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(UserEngagement, self).save(*args, **kwargs)
    
    def mark_info_collected(self):
        """Mark that user information has been collected."""
        self.info_collected = True
        self.info_collected_at = datetime.utcnow()
        self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'use_case': self.use_case,
            'profession': self.profession,
            'interests': self.interests,
            'goals': self.goals,
            'info_collected': self.info_collected,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ReferralCode(Document):
    """Referral code for each user."""
    
    meta = {
        'collection': 'referral_codes',
        'indexes': [
            'created_at',
            {'fields': ['user_id'], 'unique': True, 'name': 'uniq_referral_code_user_id'},
            {'fields': ['code'], 'unique': True, 'name': 'uniq_referral_code_code'}
        ]
    }
    
    user_id = StringField(required=True)
    code = StringField(required=True, max_length=50)  # e.g., "ARTEMIS-ABC123"
    is_active = BooleanField(default=True)
    usage_count = IntField(default=0)
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(ReferralCode, self).save(*args, **kwargs)
    
    def increment_usage(self):
        """Increment usage count."""
        self.usage_count += 1
        self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'code': self.code,
            'is_active': self.is_active,
            'usage_count': self.usage_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Referral(Document):
    """Referral relationship tracking."""
    
    meta = {
        'collection': 'referrals',
        'indexes': [
            'referrer_id',
            'referral_code',
            'points_awarded',
            'created_at',
            {'fields': ['referred_user_id'], 'unique': True, 'name': 'uniq_referral_referred_user_id'}  # One referral per user
        ]
    }
    
    referrer_id = StringField(required=True)  # User who made the referral
    referred_user_id = StringField(required=True)  # User who was referred
    referral_code = StringField(required=True)  # Code used for referral
    
    # Engagement tracking
    engagement_milestones = ListField(StringField(), default=list)  # e.g., ['5_chats', '10_chats']
    points_awarded = BooleanField(default=False)
    points_awarded_at = DateTimeField(default=None)
    points_amount = IntField(default=0)  # Points awarded for this referral
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(Referral, self).save(*args, **kwargs)
    
    def mark_milestone_reached(self, milestone: str):
        """Mark that a milestone has been reached."""
        if milestone not in self.engagement_milestones:
            self.engagement_milestones.append(milestone)
            self.save()
    
    def mark_points_awarded(self, points: int):
        """Mark that points have been awarded for this referral."""
        self.points_awarded = True
        self.points_awarded_at = datetime.utcnow()
        self.points_amount = points
        self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'referrer_id': self.referrer_id,
            'referred_user_id': self.referred_user_id,
            'referral_code': self.referral_code,
            'engagement_milestones': self.engagement_milestones,
            'points_awarded': self.points_awarded,
            'points_amount': self.points_amount,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserPoints(Document):
    """User points balance and history."""
    
    meta = {
        'collection': 'user_points',
        'indexes': [
            'total_points',
            'created_at',
            {'fields': ['user_id'], 'unique': True, 'name': 'uniq_user_points_user_id'}
        ]
    }
    
    user_id = StringField(required=True)
    total_points = IntField(default=0)
    points_history = ListField(EmbeddedDocumentField(PointsHistoryEntry), default=list)
    
    # Rewards redeemed
    rewards_redeemed = ListField(StringField(), default=list)  # e.g., ['custom_voice', 'premium_features']
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(UserPoints, self).save(*args, **kwargs)
    
    def add_points(
        self,
        amount: int,
        source: str = 'referral',
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Add points to user's balance."""
        self.total_points += amount
        
        history_entry = PointsHistoryEntry(
            amount=amount,
            type='earned',
            source=source,
            description=description or f"Points earned from {source}",
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        self.points_history.append(history_entry)
        self.save()
    
    def spend_points(
        self,
        amount: int,
        reason: str = 'redemption',
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Spend points from user's balance."""
        if self.total_points < amount:
            raise ValueError(f"Insufficient points. Balance: {self.total_points}, Required: {amount}")
        
        self.total_points -= amount
        
        history_entry = PointsHistoryEntry(
            amount=-amount,
            type='spent',
            source=reason,
            description=description or f"Points spent on {reason}",
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        self.points_history.append(history_entry)
        self.save()
    
    def redeem_reward(self, reward_type: str):
        """Mark a reward as redeemed."""
        if reward_type not in self.rewards_redeemed:
            self.rewards_redeemed.append(reward_type)
            self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'total_points': self.total_points,
            'rewards_redeemed': self.rewards_redeemed,
            'points_history_count': len(self.points_history),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

