"""
Database models for the Meal Management System.
Contains MongoEngine Document models for employees, meal selections, reminders, and options.
"""

from mongoengine import (
    Document, 
    StringField, 
    EmailField, 
    BooleanField, 
    DateTimeField,
    ReferenceField,
    IntField,
    ListField,
    DictField,
    EmbeddedDocument,
    EmbeddedDocumentField,
    PULL
)
from datetime import datetime
from typing import Optional, Dict, Any


class Employee(Document):
    """Employee model for storing user information."""
    meta = {
        'collection': 'employees',
        'indexes': [
            'email',  # Index for faster email lookups
            'is_active',
            ('email', 'is_active')  # Compound index
        ]
    }
    
    name = StringField(required=True, max_length=100)
    email = EmailField(required=True, unique=True)
    department = StringField(max_length=50)
    password_hash = StringField(required=True, max_length=255)  # Store hashed passwords
    role = StringField(max_length=20, default='client', choices=['admin', 'client'])
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(Employee, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.email})"


class MealSelection(Document):
    """Meal selection model for storing weekly meal choices."""
    meta = {
        'collection': 'meal_selections',
        'indexes': [
            'user',
            'week_start_date',
            ('user', 'week_start_date')  # Compound index for queries
        ]
    }
    
    user = ReferenceField('User', required=True, reverse_delete_rule=PULL)
    week_start_date = DateTimeField(required=True)  # Monday of the week
    monday_meal = StringField()
    tuesday_meal = StringField()
    wednesday_meal = StringField()
    thursday_meal = StringField()
    friday_meal = StringField()
    special_dietary_requirements = StringField()
    submitted_at = DateTimeField(default=datetime.utcnow)
    is_submitted = BooleanField(default=False)
    
    def __str__(self):
        return f"Meal selection for {self.user.fullname} - Week of {self.week_start_date.strftime('%Y-%m-%d')}"


class MealReminder(Document):
    """Meal reminder model for tracking sent reminders."""
    meta = {
        'collection': 'meal_reminders',
        'indexes': [
            'user',
            'week_start_date',
            'reminder_sent_at'
        ]
    }
    
    user = ReferenceField('User', required=True, reverse_delete_rule=PULL)
    week_start_date = DateTimeField(required=True)
    reminder_sent_at = DateTimeField(default=datetime.utcnow)
    reminder_type = StringField(max_length=20, default='weekly', choices=['weekly', 'reminder', 'final'])
    
    def __str__(self):
        return f"{self.reminder_type} reminder for {self.user.fullname} - {self.week_start_date.strftime('%Y-%m-%d')}"


class MealOptions(Document):
    """Meal options model for storing available meal choices by day."""
    meta = {
        'collection': 'meal_options',
        'indexes': [
            'day',
            'is_active',
            ('name', 'day'),  # Compound unique index
            ('day', 'is_active')
        ]
    }
    
    name = StringField(required=True, max_length=100)
    day = StringField(
        required=True, 
        max_length=20,
        choices=['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    )
    is_active = BooleanField(default=True)
    created_by = ReferenceField('User', required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(MealOptions, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.day})"
    
    @classmethod
    def ensure_unique_meal_per_day(cls, name, day, exclude_id=None):
        """Check if a meal with the same name already exists for the day."""
        query = cls.objects(name=name, day=day)
        if exclude_id:
            query = query.filter(id__ne=exclude_id)
        return query.first() is None


class ChatMessage(EmbeddedDocument):
    """Embedded document for individual chat messages."""
    message_id = StringField(required=True)  # Unique identifier for each message
    role = StringField(
        required=True,
        choices=['user', 'assistant', 'system', 'ai', 'human']
    )
    content = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    metadata = DictField(default=dict)  # For storing additional info like tokens, model used, etc.
    audio_generated = BooleanField(default=False)  # Track if audio was generated for this message
    audio_url = StringField()  # URL/path to generated audio file
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            'message_id': self.message_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': self.metadata,
            'audio_generated': self.audio_generated,
            'audio_url': self.audio_url
        }


class Conversation(Document):
    """Conversation model for storing chat threads and messages."""
    meta = {
        'collection': 'conversations',
        'indexes': [
            'thread_id',
            'user_id',
            'created_at',
            ('thread_id', 'user_id'),  # Compound index
            {'fields': ['updated_at'], 'expireAfterSeconds': 2592000}  # Auto-delete after 30 days (TTL index)
        ]
    }
    
    thread_id = StringField(required=True, unique=True, max_length=255)
    user_id = StringField(max_length=255)  # Optional: to associate with a specific user
    title = StringField(max_length=500)  # Optional: conversation title
    messages = ListField(EmbeddedDocumentField(ChatMessage), default=list)
    message_count = IntField(default=0)
    
    # Metadata
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    last_message_at = DateTimeField(default=datetime.utcnow)
    
    # Optional: categorization and tagging
    tags = ListField(StringField(max_length=50), default=list)
    category = StringField(max_length=100)
    
    # Optional: status tracking
    is_active = BooleanField(default=True)
    is_archived = BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        """Override save to update timestamps and message count."""
        self.updated_at = datetime.utcnow()
        self.message_count = len(self.messages)
        if self.messages:
            self.last_message_at = self.messages[-1].timestamp
        return super(Conversation, self).save(*args, **kwargs)
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None, message_id: Optional[str] = None) -> tuple['Conversation', str]:
        """
        Add a message to the conversation.
        
        Args:
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata dict
            message_id: Optional message ID (auto-generated if not provided)
            
        Returns:
            Tuple of (Updated conversation instance, message_id)
        """
        from uuid import uuid4
        
        if not message_id:
            message_id = str(uuid4())
        
        message = ChatMessage(
            message_id=message_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
            audio_generated=False
        )
        self.messages.append(message)
        self.save()
        return self, message_id
    
    def get_messages_dict(self) -> list:
        """Get all messages as list of dicts."""
        return [msg.to_dict() for msg in self.messages]
    
    def clear_messages(self) -> 'Conversation':
        """Clear all messages from the conversation."""
        self.messages = []
        return self.save()
    
    def get_last_n_messages(self, n: int = 10) -> list:
        """Get last N messages."""
        return [msg.to_dict() for msg in self.messages[-n:]]
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific message by its ID.
        
        Args:
            message_id: The unique message identifier
            
        Returns:
            Message dict or None if not found
        """
        for msg in self.messages:
            if msg.message_id == message_id:
                return msg.to_dict()
        return None
    
    def update_message_audio(self, message_id: str, audio_url: str) -> bool:
        """
        Update a message to mark that audio has been generated.
        
        Args:
            message_id: The unique message identifier
            audio_url: URL/path to the generated audio
            
        Returns:
            True if updated, False if message not found
        """
        for msg in self.messages:
            if msg.message_id == message_id:
                msg.audio_generated = True
                msg.audio_url = audio_url
                self.save()
                return True
        return False
    
    @classmethod
    def get_or_create(cls, thread_id: str, user_id: Optional[str] = None) -> 'Conversation':
        """
        Get existing conversation or create new one.
        
        Args:
            thread_id: Thread identifier
            user_id: Optional user identifier
            
        Returns:
            Conversation instance
        """
        # Filter by both thread_id and user_id to ensure user-specific conversations
        if user_id:
            conversation = cls.objects(thread_id=thread_id, user_id=user_id).first()
        else:
            # If no user_id provided, only check thread_id (for backward compatibility)
            conversation = cls.objects(thread_id=thread_id).first()
        
        if not conversation:
            conversation = cls(
                thread_id=thread_id,
                user_id=user_id
            ).save()
        return conversation
    
    def __str__(self):
        return f"Conversation {self.thread_id} ({self.message_count} messages)"

