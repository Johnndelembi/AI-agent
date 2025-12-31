"""
Google OAuth service for user authentication.
Handles Google OAuth flow and user creation/updates.
"""

import asyncio
from typing import Dict, Any, Optional
import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import HTTPException, status

from app.models.auth import User
from app.services.auth_service import auth_service
from app.config import settings, logger


class GoogleOAuthService:
    """Service for handling Google OAuth authentication."""
    
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        
        if not self.client_id or not self.client_secret:
            logger.warning("Google OAuth credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
    
    def is_configured(self) -> bool:
        """Check if Google OAuth is configured."""
        return bool(self.client_id and self.client_secret)
    
    def get_authorization_url(self, state: Optional[str] = None, redirect_uri: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            redirect_uri: Optional custom redirect URI (defaults to configured redirect_uri)
            
        Returns:
            Authorization URL to redirect user to
        """
        if not self.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth not configured. Please contact administrator."
            )
        
        # Use provided redirect_uri or fall back to configured one
        redirect_uri_to_use = redirect_uri or self.redirect_uri
        
        # Google OAuth endpoints
        authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        
        # Scopes needed to get user profile info
        scopes = [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]
        
        # Create OAuth client
        oauth_client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=redirect_uri_to_use
        )
        
        # Generate authorization URL
        authorization_url, _ = oauth_client.create_authorization_url(
            authorization_base_url,
            scope=scopes,
            state=state
        )
        
        return authorization_url
    
    async def handle_callback(self, code: str, redirect_uri: Optional[str] = None, referral_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle Google OAuth callback and create/update user.
        
        Args:
            code: Authorization code from Google OAuth callback
            redirect_uri: Optional custom redirect URI (must match the one used in authorization URL)
            referral_code: Optional referral code for tracking referrals
            
        Returns:
            Dictionary with access_token, refresh_token, and user info
        """
        if not self.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth not configured. Please contact administrator."
            )
        
        # Use provided redirect_uri or fall back to configured one
        # IMPORTANT: This must match the redirect_uri used in get_authorization_url()
        redirect_uri_to_use = redirect_uri or self.redirect_uri
        
        # Google OAuth endpoints
        token_url = "https://oauth2.googleapis.com/token"
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        # Create OAuth client
        oauth_client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=redirect_uri_to_use
        )
        
        try:
            # Exchange authorization code for tokens
            # Note: Authorization codes can only be used once
            try:
                token_response = await oauth_client.fetch_token(
                    token_url,
                    code=code
                )
            except Exception as token_error:
                error_msg = str(token_error)
                # Check if it's an invalid_grant error (code already used or expired)
                if "invalid_grant" in error_msg.lower():
                    logger.warning(f"Authorization code already used or expired: {code[:20]}...")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This authorization code has already been used or has expired. Please try signing in again."
                    )
                # Re-raise other errors
                raise
            
            access_token = token_response.get('access_token')
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to obtain access token from Google"
                )
            
            # Get user info from Google
            user_info = await self._get_user_info(access_token)
            
            # Create or update user
            user = await asyncio.to_thread(
                self._create_or_update_user,
                user_info,
                referral_code
            )
            
            # Generate JWT tokens
            tokens = auth_service.generate_tokens(user)
            
            # Update last login
            await asyncio.to_thread(user.update_last_login)
            
            logger.info(f"User authenticated via Google OAuth: {user.email}")
            
            return {
                **tokens,
                "user": user.to_dict(),
                "expires_in": 3600  # 1 hour in seconds
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Google OAuth callback error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to authenticate with Google: {str(e)}"
            )
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch user information from Google API.
        
        Args:
            access_token: Google OAuth access token
            
        Returns:
            User information dictionary
        """
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(userinfo_url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    def _create_or_update_user(self, google_user_data: Dict[str, Any], referral_code: Optional[str] = None) -> User:
        """
        Create or update user from Google profile data.
        
        Args:
            google_user_data: User data from Google API
            referral_code: Optional referral code for tracking referrals
            
        Returns:
            User object (created or updated)
        """
        google_id = google_user_data.get('id') or google_user_data.get('sub')
        email = google_user_data.get('email')
        first_name = google_user_data.get('given_name', '')
        last_name = google_user_data.get('family_name', '')
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google"
            )
        
        if not google_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google ID not provided"
            )
        
        # Check if user exists by Google ID
        user = User.get_by_google_id(google_id)
        
        if not user:
            # Check if user exists by email (for migration)
            user = User.get_by_email(email)
        
        if user:
            # Update existing user
            user.google_id = google_id
            user.first_name = first_name
            user.last_name = last_name
            user.fullname = f"{first_name} {last_name}".strip() or user.fullname
            user.is_verified = True  # Google-verified emails are always verified
            user.save()
        else:
            # Create new user
            user = User(
                email=email,
                google_id=google_id,
                first_name=first_name,
                last_name=last_name,
                fullname=f"{first_name} {last_name}".strip(),
                phone_number="",  # To be filled later
                password_hash=None,  # No password for Google OAuth users
                is_verified=True,  # Google-verified emails are always verified
                is_active=True
            )
            user.save()
            
            # Track referral if referral code provided (only for new users)
            if referral_code:
                try:
                    from app.services.referral_service import referral_service
                    referral_service.track_referral(
                        referral_code=referral_code,
                        referred_user_id=str(user.id)
                    )
                    logger.info(f"Referral tracked for new OAuth user {email} with code {referral_code}")
                except Exception as e:
                    # Don't fail registration if referral tracking fails
                    logger.warning(f"Failed to track referral for {email}: {e}")
        
        return user


# Singleton instance
google_oauth_service = GoogleOAuthService()
