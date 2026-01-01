"""
Authentication service - JWT tokens, user authentication, and email notifications.
Consolidated for simplicity.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status

from app.models.auth import User
from app.config import logger


# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))  # 30 days


class AuthService:
    """Service for handling authentication and JWT tokens."""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    def get_user_from_token(token: str) -> User:
        """Extract user from JWT token."""
        payload = AuthService.verify_token(token)
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        
        user = User.get_by_id(user_id)
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        
        return user
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        user = User.get_by_email(email)
        
        if not user:
            return None
        
        if not user.verify_password(password):
            return None
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        return user
    
    @staticmethod
    def register_user(
        email: str,
        password: str,
        phone_number: str,
        fullname: str = "",
        city: str = "",
        **kwargs
    ) -> User:
        """Register a new user."""
        
        # Check if email already exists
        if User.email_exists(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check if phone number already exists
        if User.phone_exists(phone_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
        
        # Validate password strength
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Create user
        user = User(
            email=email,
            phone_number=phone_number,
            fullname=fullname,
            city=city,
            **kwargs
        )
        user.set_password(password)
        user.save()
        
        logger.info(f"New user registered: {email}")
        return user
    
    @staticmethod
    def generate_tokens(user: User) -> Dict[str, str]:
        """Generate access and refresh tokens for user."""
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "roles": user.roles
        }
        
        access_token = AuthService.create_access_token(token_data)
        refresh_token = AuthService.create_refresh_token({"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> Dict[str, str]:
        """Generate new access token from refresh token."""
        payload = AuthService.verify_token(refresh_token)
        
        # Check if it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        user = User.get_by_id(user_id)
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Generate new access token
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "roles": user.roles
        }
        
        access_token = AuthService.create_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }


# Singleton instance
auth_service = AuthService()


# ============================================================================
# EMAIL SERVICE (Consolidated here)
# ============================================================================

class EmailService:
    """Service for sending authentication-related emails."""
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.app_name = os.getenv("APP_NAME", "Artemis - AI Assistant")
        self.frontend_url = os.getenv("FRONTEND_URL", "")
        
        if not self.sender_email or not self.sender_password:
            logger.warning("Email not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env")
    
    def is_configured(self) -> bool:
        return bool(self.sender_email and self.sender_password)
    
    def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        if not self.is_configured():
            logger.error("Email service not configured")
            return False
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.app_name} <{self.sender_email}>"
            msg['To'] = to_email
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def send_verification_code(self, to_email: str, code: str, expiry_minutes: int = 1) -> bool:
        subject = f"Your {self.app_name} Verification Code"
        html = f"""
        <!DOCTYPE html>
        <html><body style="font-family:Arial;color:#333;max-width:600px;margin:0 auto;">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0;">
            <h1>🔐 Verify Your Email</h1>
        </div>
        <div style="background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px;">
            <p>Thank you for registering! Use this code to verify your email:</p>
            <div style="background:white;border:2px solid #667eea;border-radius:8px;padding:20px;text-align:center;margin:20px 0;">
                <div style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#667eea;">{code}</div>
                <div style="color:#e74c3c;font-size:14px;margin-top:15px;">⏰ Expires in {expiry_minutes} minute</div>
            </div>
            <p>Enter this code to activate your account.</p>
            <p><strong>Security:</strong> Never share this code. If you didn't request it, ignore this email.</p>
        </div>
        </body></html>
        """
        return self.send_email(to_email, subject, html)
    
    def send_password_reset_email(self, to_email: str, reset_token: str, expiry_hours: int = 1) -> bool:
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        subject = f"Reset Your {self.app_name} Password"
        html = f"""
        <!DOCTYPE html>
        <html><body style="font-family:Arial;color:#333;max-width:600px;margin:0 auto;">
        <div style="background:linear-gradient(135deg,#f093fb,#f5576c);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0;">
            <h1>🔑 Reset Your Password</h1>
        </div>
        <div style="background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px;">
            <p>We received a request to reset your password.</p>
            <p style="text-align:center;">
                <a href="{reset_link}" style="display:inline-block;background:#f5576c;color:white;padding:15px 30px;text-decoration:none;border-radius:5px;margin:20px 0;font-weight:bold;">Reset Password</a>
            </p>
            <div style="color:#e74c3c;font-size:14px;">⏰ This link expires in {expiry_hours} hour</div>
            <p>Or copy this link: <div style="background:white;border:1px solid #ddd;padding:10px;margin:10px 0;word-break:break-all;font-size:12px;">{reset_link}</div></p>
            <p><strong>Security:</strong> If you didn't request this, ignore this email.</p>
        </div>
        </body></html>
        """
        return self.send_email(to_email, subject, html)
    
    def send_welcome_email(self, to_email: str, fullname: str = "") -> bool:
        greeting = f"Hello {fullname}!" if fullname else "Hello!"
        subject = f"Welcome to {self.app_name}!"
        html = f"""
        <!DOCTYPE html>
        <html><body style="font-family:Arial;color:#333;max-width:600px;margin:0 auto;">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0;">
            <h1>🎉 Welcome to {self.app_name}!</h1>
        </div>
        <div style="background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px;">
            <p>{greeting}</p>
            <p>Your account has been successfully created and verified! 🚀</p>
            <p>You can now start using all features of {self.app_name}.</p>
            <p>Thank you for joining us!</p>
        </div>
        </body></html>
        """
        return self.send_email(to_email, subject, html)


email_service = EmailService()

