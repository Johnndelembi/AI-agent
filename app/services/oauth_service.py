"""
OAuth service for Google authentication.
Handles OAuth flow and user creation/authentication via Google.
"""

import os
import httpx
from typing import Dict, Any

from app.models.auth import User
from app.services.auth_service import auth_service
from app.config import logger


class GoogleOAuthService:
    """Service for handling Google OAuth authentication."""
    
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
        
        if not self.client_id or not self.client_secret:
            logger.warning("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
        
        # Google OAuth endpoints
        self.authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_endpoint = "https://oauth2.googleapis.com/token"
        self.userinfo_endpoint = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        # Scopes
        self.scope = "openid email profile"
    
    def is_configured(self) -> bool:
        """Check if Google OAuth is properly configured."""
        return bool(self.client_id and self.client_secret)
    
    def get_authorization_url(self, redirect_uri: str = None) -> str:
        """
        Generate Google OAuth authorization URL.
        
        Args:
            redirect_uri: OAuth redirect URI (defaults to configured redirect_uri)
            
        Returns:
            Authorization URL for Google OAuth
        """
        if not self.is_configured():
            raise ValueError("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
        
        redirect = redirect_uri or self.redirect_uri
        
        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": self.scope,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Force consent screen to get refresh token
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{self.authorization_endpoint}?{query_string}"
        
        logger.info(f"Generated Google OAuth URL with redirect_uri: {redirect}")
        return auth_url
    
    async def handle_callback(self, code: str, redirect_uri: str = None) -> Dict[str, Any]:
        """
        Handle OAuth callback - exchange code for tokens and get user info.
        
        Args:
            code: Authorization code from Google
            redirect_uri: OAuth redirect URI (must match the one used in authorization)
            
        Returns:
            Dictionary with access_token, refresh_token, token_type, expires_in, and user
        """
        if not self.is_configured():
            raise ValueError("Google OAuth not configured")
        
        redirect = redirect_uri or self.redirect_uri
        
        try:
            # Exchange code for tokens
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    self.token_endpoint,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": redirect,
                        "grant_type": "authorization_code",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                token_response.raise_for_status()
                token_data = token_response.json()
            
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)
            
            if not access_token:
                raise ValueError("Failed to get access token from Google")
            
            # Get user info from Google
            async with httpx.AsyncClient() as client:
                userinfo_response = await client.get(
                    self.userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                userinfo_response.raise_for_status()
                userinfo = userinfo_response.json()
            
            # Extract user information
            google_email = userinfo.get("email")
            google_name = userinfo.get("name", "")
            google_picture = userinfo.get("picture", "")
            
            if not google_email:
                raise ValueError("Email not provided by Google")
            
            # Find or create user
            user = User.get_by_email(google_email)
            
            if not user:
                # Create new user from Google OAuth
                # Generate a random password since OAuth users don't need password
                import secrets
                random_password = secrets.token_urlsafe(32)
                
                # Extract first and last name if available
                fullname_parts = google_name.split(" ", 1) if google_name else ["", ""]
                first_name = fullname_parts[0] if len(fullname_parts) > 0 else ""
                last_name = fullname_parts[1] if len(fullname_parts) > 1 else ""
                
                # Create user with minimal required fields
                # Phone number is required, so we'll use a placeholder
                user = User(
                    email=google_email,
                    fullname=google_name,
                    phone_number=f"oauth_{google_email}",  # Placeholder, user can update later
                    city="",
                )
                user.set_password(random_password)  # Set random password
                user.is_verified = True  # Google email is already verified
                user.save()
                
                logger.info(f"New user created via Google OAuth: {google_email}")
            else:
                # Update existing user info if needed
                if google_name and not user.fullname:
                    user.fullname = google_name
                    user.save()
                
                logger.info(f"Existing user logged in via Google OAuth: {google_email}")
            
            # Generate JWT tokens
            tokens = auth_service.generate_tokens(user)
            
            # Return response in expected format
            return {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": tokens["token_type"],
                "expires_in": expires_in,
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "fullname": user.fullname,
                    "is_verified": user.is_verified,
                    "is_active": user.is_active,
                }
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Google OAuth callback: {e.response.text}")
            raise ValueError(f"OAuth token exchange failed: {e.response.text}")
        except Exception as e:
            logger.error(f"Error during Google OAuth callback: {str(e)}", exc_info=True)
            raise ValueError(f"OAuth callback failed: {str(e)}")


# Singleton instance
google_oauth_service = GoogleOAuthService()

