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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# MONGODB MODELS (Database)
# ============================================================================

class User(Document):
    """User model with authentication support."""
    
    # Authentication
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    
    # Profile
    phone_number = StringField(required=True)
    fullname = StringField(default="")
    
    # Optional physical address
    city = StringField(default="")
    
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
        'indexes': ['email', 'phone_number', 'created_at', {'fields': ['email'], 'unique': True}]
    }
    
    def set_password(self, password: str):
        """Hash and set password."""
        self.password_hash = pwd_context.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
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
            'fullname': self.fullname,
            'address': {
                'city': self.city
            } if self.city else None,
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


class OTPVerification(Document):
    """OTP codes for email verification during registration."""
    
    email = StringField(required=True, unique=True)
    code = StringField(required=True)
    password_hash = StringField(required=True)
    phone_number = StringField(required=True)
    fullname = StringField(default="")
    city = StringField(default="")
    is_verified = BooleanField(default=False)
    attempts = IntField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)
    verified_at = DateTimeField(default=None)
    
    meta = {
        'collection': 'otp_verifications',
        'indexes': ['email', 'expires_at', {'fields': ['email'], 'unique': True}]
    }
    
    @classmethod
    def generate_code(cls) -> str:
        """Generate 4-digit OTP code."""
        return ''.join(random.choices(string.digits, k=4))
    
    @classmethod
    def create_otp(cls, email: str, password_hash: str, phone_number: str, 
                   expiry_minutes: int = 1, **user_data) -> 'OTPVerification':
        """Create new OTP verification entry."""
        cls.objects(email=email).delete()
        otp = cls(
            email=email,
            code=cls.generate_code(),
            password_hash=password_hash,
            phone_number=phone_number,
            fullname=user_data.get('fullname', ''),
            city=user_data.get('city', ''),
            expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes)
        )
        otp.save()
        return otp
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def verify_code(self, code: str) -> bool:
        self.attempts += 1
        self.save()
        if self.is_expired() or self.code != code:
            return False
        self.is_verified = True
        self.verified_at = datetime.utcnow()
        self.save()
        return True
    
    @classmethod
    def get_by_email(cls, email: str) -> 'OTPVerification':
        return cls.objects(email=email).first()


class PasswordResetToken(Document):
    """Password reset tokens for forgot password flow."""
    
    email = StringField(required=True)
    token = StringField(required=True, unique=True)
    is_used = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)
    used_at = DateTimeField(default=None)
    
    meta = {
        'collection': 'password_reset_tokens',
        'indexes': ['email', 'token', 'expires_at', {'fields': ['token'], 'unique': True}]
    }
    
    @classmethod
    def generate_token(cls) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    
    @classmethod
    def create_reset_token(cls, email: str, expiry_hours: int = 1) -> 'PasswordResetToken':
        cls.objects(email=email).delete()
        token = cls(
            email=email,
            token=cls.generate_token(),
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        token.save()
        return token
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired()
    
    def mark_as_used(self):
        self.is_used = True
        self.used_at = datetime.utcnow()
        self.save()
    
    @classmethod
    def get_by_token(cls, token: str) -> 'PasswordResetToken':
        return cls.objects(token=token).first()


# ============================================================================
# PYDANTIC MODELS (API Request/Response)
# ============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    phone_number: str = Field(..., min_length=10, description="Phone number")
    fullname: Optional[str] = ""
    city: Optional[str] = ""
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        return v
    
    @validator('phone_number')
    def validate_phone(cls, v):
        """Basic phone number validation."""
        # Remove common separators
        cleaned = v.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not cleaned.isdigit() or len(cleaned) < 10:
            raise ValueError('Invalid phone number format')
        return v


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


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
    fullname: Optional[str] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        return v


class VerifyEmailRequest(BaseModel):
    """Verify email with OTP code."""
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=4, description="4-digit verification code")
    
    @validator('code')
    def validate_code(cls, v):
        """Validate code is 4 digits."""
        if not v.isdigit() or len(v) != 4:
            raise ValueError('Code must be exactly 4 digits')
        return v


class ResendOTPRequest(BaseModel):
    """Resend OTP code request."""
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password with token."""
    token: str = Field(..., min_length=32, max_length=32)
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        return v


class RegistrationResponse(BaseModel):
    """Response after initiating registration (before verification)."""
    message: str
    email: str
    expires_in_seconds: int

