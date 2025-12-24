"""
All authentication models - MongoDB models and Pydantic request/response models.
Consolidated for simplicity.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator
from mongoengine import (
    Document, StringField, EmailField, DateTimeField, 
    BooleanField, DictField, ListField, IntField
)
from passlib.context import CryptContext


# ============================================================================
# PASSWORD HASHING
# ============================================================================

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


# ============================================================================
# MONGODB MODELS (Database)
# ============================================================================

class User(Document):
    """User model with authentication support."""
    
    # Authentication
    email = EmailField(required=True, unique=True)
    password_hash = StringField(default=None)  # Optional for Google OAuth users
    google_id = StringField(default=None)  # Google OAuth user ID (unique, sparse)
    
    # Profile
    phone_number = StringField(default="")  # Optional, to be filled later
    first_name = StringField(default="")
    last_name = StringField(default="")
    fullname = StringField(default="")
    
    # Optional physical address
    city = StringField(default="")
    
    # Meal Management System Fields
    department = StringField(max_length=50, default="")
    employee_id = StringField(max_length=50, default=None)  # Company employee ID (unique via sparse index)
    is_employee = BooleanField(default=False)  # Can access meal management system
    meal_preferences = DictField(default={})  # Store dietary preferences, allergies, etc.
    
    # Account status
    is_active = BooleanField(default=True)
    is_verified = BooleanField(default=False)
    is_admin = BooleanField(default=False)
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=None)
    
    # Metadata
    metadata = DictField(default={})
    roles = ListField(StringField(), default=["user"])
    
    meta = {
        'collection': 'users',
        'indexes': [
            # Non-unique helpful indexes
            'phone_number',
            'department',
            'is_employee',
            'created_at',
            # Explicit unique sparse for optional employee_id
            {'fields': ['employee_id'], 'unique': True, 'sparse': True, 'name': 'uniq_employee_id'},
            # Explicit unique sparse for optional google_id
            {'fields': ['google_id'], 'unique': True, 'sparse': True, 'name': 'uniq_google_id'}
        ]
    }
    
    def set_password(self, password: str):
        """Hash and set password."""
        self.password_hash = pwd_context.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        if not self.password_hash:
            return False  # Google OAuth users don't have passwords
        return pwd_context.verify(password, self.password_hash)
    
    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()
        self.save()
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert user to dictionary (excluding password)."""
        data = {
            'id': str(self.id),
            'email': self.email,
            'phone_number': self.phone_number,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'fullname': self.fullname or f"{self.first_name} {self.last_name}".strip(),
            'address': {
                'city': self.city
            } if self.city else None,
            # Meal Management Fields
            'department': self.department,
            'employee_id': self.employee_id,
            'is_employee': self.is_employee,
            'meal_preferences': self.meal_preferences,
            # Account Status
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'is_admin': self.is_admin,
            'roles': self.roles,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data['metadata'] = self.metadata
        
        return data
    
    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """Get user by email."""
        return cls.objects(email=email).first()
    
    @classmethod
    def get_by_id(cls, user_id: str) -> Optional['User']:
        """Get user by ID."""
        try:
            return cls.objects(id=user_id).first()
        except:
            return None
    
    @classmethod
    def email_exists(cls, email: str) -> bool:
        """Check if email already exists."""
        return cls.objects(email=email).count() > 0
    
    @classmethod
    def phone_exists(cls, phone_number: str) -> bool:
        """Check if phone number already exists."""
        return cls.objects(phone_number=phone_number).count() > 0
    
    # Meal Management Helper Methods
    def set_employee_info(self, employee_id: str, department: str = ""):
        """Set employee information for meal management access."""
        self.employee_id = employee_id
        self.department = department
        self.is_employee = True
        if "employee" not in self.roles:
            self.roles.append("employee")
        self.save()
    
    def remove_employee_access(self):
        """Remove employee access to meal management."""
        self.employee_id = None
        self.department = ""
        self.is_employee = False
        if "employee" in self.roles:
            self.roles.remove("employee")
        self.save()
    
    def update_meal_preferences(self, preferences: dict):
        """Update meal preferences and dietary requirements."""
        self.meal_preferences.update(preferences)
        self.save()
    
    @classmethod
    def get_employees(cls) -> List['User']:
        """Get all users who are employees (can access meal management)."""
        return cls.objects(is_employee=True, is_active=True)
    
    @classmethod
    def get_by_employee_id(cls, employee_id: str) -> Optional['User']:
        """Get user by employee ID."""
        return cls.objects(employee_id=employee_id).first()
    
    @classmethod
    def get_by_google_id(cls, google_id: str) -> Optional['User']:
        """Get user by Google ID."""
        return cls.objects(google_id=google_id).first()


# ============================================================================
# PYDANTIC MODELS (API Request/Response)
# ============================================================================




class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None  # seconds


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class UserResponse(BaseModel):
    """User profile response."""
    id: str
    email: str
    phone_number: str
    first_name: str = ""
    last_name: str = ""
    fullname: str
    address: Optional[dict] = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    roles: List[str]
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    
    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    """Update user profile request."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    fullname: Optional[str] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None




class AdminPatchUserRequest(BaseModel):
    """Admin-only partial update for User fields, including meal management fields."""
    # Profile fields
    fullname: Optional[str] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None

    # Account flags
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_admin: Optional[bool] = None

    # Roles
    roles: Optional[List[str]] = None

    # Meal management fields
    department: Optional[str] = None
    employee_id: Optional[str] = None  # unique, sparse
    is_employee: Optional[bool] = None
    meal_preferences: Optional[dict] = None

    class Config:
        extra = 'forbid'

