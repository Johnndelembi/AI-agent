"""Authentication controller for user registration, login, and profile management."""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.auth import (
    # Pydantic models
    RegisterRequest, LoginRequest, TokenResponse, RefreshTokenRequest,
    UserResponse, UpdateProfileRequest, ChangePasswordRequest,
    VerifyEmailRequest, ResendOTPRequest, ForgotPasswordRequest, ResetPasswordRequest,
    RegistrationResponse,
    # MongoDB models
    User, OTPVerification, PasswordResetToken
)
from app.services.auth_service import auth_service, email_service, ACCESS_TOKEN_EXPIRE_MINUTES
from app.utils.auth_utils import get_current_user, get_current_active_user
from app.utils.error_handler import handle_http_errors
from app.config import logger


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=RegistrationResponse, summary="Step 1: Initiate registration (sends OTP)")
@handle_http_errors("Registration failed")
async def register(request: RegisterRequest) -> RegistrationResponse:
    """
    **Step 1 of Registration:** Submit registration details and receive OTP code via email.
    
    - **email**: Valid email address (must be unique)
    - **password**: At least 8 characters with letters and numbers
    - **phone_number**: Phone number (must be unique)
    - **first_name**: Optional first name
    - **last_name**: Optional last name
    - **address fields**: Optional address information
    
    **Next Step:** Call `/auth/verify-email` with the OTP code sent to your email.
    """
    # Check if email service is configured
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Please contact administrator."
        )
    
    # Check if email already exists (in both User and pending OTP)
    if await asyncio.to_thread(User.email_exists, request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if phone already exists
    if await asyncio.to_thread(User.phone_exists, request.phone_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Hash password
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password_hash = pwd_context.hash(request.password)
    
    # Create OTP verification entry
    otp = await asyncio.to_thread(
        OTPVerification.create_otp,
        email=request.email,
        password_hash=password_hash,
        phone_number=request.phone_number,
        expiry_minutes=1,  # 1 minute expiry
        fullname=request.fullname,
        city=request.city
    )
    
    # Send verification email
    email_sent = await asyncio.to_thread(
        email_service.send_verification_code,
        to_email=request.email,
        code=otp.code,
        expiry_minutes=1
    )
    
    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again."
        )
    
    logger.info(f"Registration initiated for: {request.email}")
    
    return RegistrationResponse(
        message="Verification code sent to your email. Please check your inbox.",
        email=request.email,
        expires_in_seconds=60  # 1 minute
    )


@router.post("/verify-email", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Step 2: Verify email with OTP")
@handle_http_errors("Email verification failed")
async def verify_email(request: VerifyEmailRequest) -> UserResponse:
    """
    **Step 2 of Registration:** Verify email with the 4-digit OTP code.
    
    - **email**: Your email address
    - **code**: 4-digit code sent to your email
    
    After successful verification, your account is created and you can login.
    """
    # Get OTP verification entry
    otp = await asyncio.to_thread(OTPVerification.get_by_email, request.email)
    
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending registration found for this email. Please register first."
        )
    
    # Check if already verified
    if otp.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified. Please login."
        )
    
    # Verify the code
    is_valid = await asyncio.to_thread(otp.verify_code, request.code)
    
    if not is_valid:
        if otp.is_expired():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired. Please request a new one."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification code. {3 - otp.attempts} attempts remaining."
            )
    
    # Create the actual user account
    user = User(
        email=otp.email,
        password_hash=otp.password_hash,
        phone_number=otp.phone_number,
        fullname=otp.fullname,
        city=otp.city,
        is_verified=True  # Mark as verified
    )
    await asyncio.to_thread(user.save)
    
    # Send welcome email
    await asyncio.to_thread(
        email_service.send_welcome_email,
        to_email=user.email,
        fullname=user.fullname
    )
    
    # Delete OTP entry
    await asyncio.to_thread(otp.delete)
    
    logger.info(f"User registration completed: {user.email}")
    
    return UserResponse(**user.to_dict())


@router.post("/resend-otp", response_model=RegistrationResponse, summary="Resend OTP code")
@handle_http_errors("Failed to resend OTP")
async def resend_otp(request: ResendOTPRequest) -> RegistrationResponse:
    """
    Resend OTP verification code if the previous one expired.
    
    - **email**: Your email address
    
    A new 4-digit code will be sent to your email with 1-minute validity.
    """
    # Get existing OTP entry
    otp = await asyncio.to_thread(OTPVerification.get_by_email, request.email)
    
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending registration found for this email. Please register first."
        )
    
    if otp.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified. Please login."
        )
    
    # Generate new code and update expiry
    from datetime import datetime, timedelta
    otp.code = OTPVerification.generate_code()
    otp.expires_at = datetime.utcnow() + timedelta(minutes=1)
    otp.attempts = 0  # Reset attempts
    await asyncio.to_thread(otp.save)
    
    # Send new verification email
    email_sent = await asyncio.to_thread(
        email_service.send_verification_code,
        to_email=request.email,
        code=otp.code,
        expiry_minutes=1
    )
    
    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again."
        )
    
    logger.info(f"OTP resent to: {request.email}")
    
    return RegistrationResponse(
        message="New verification code sent to your email.",
        email=request.email,
        expires_in_seconds=60
    )


@router.post("/login", response_model=TokenResponse, summary="Login")
@handle_http_errors("Login failed")
async def login(request: LoginRequest) -> TokenResponse:
    """
    Authenticate user and return JWT tokens.
    
    - **email**: User email
    - **password**: User password
    
    Returns access token (expires in 1 hour) and refresh token (expires in 30 days).
    """
    # Authenticate user
    user = await asyncio.to_thread(
        auth_service.authenticate_user,
        email=request.email,
        password=request.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    await asyncio.to_thread(user.update_last_login)
    
    # Generate tokens
    tokens = auth_service.generate_tokens(user)
    
    logger.info(f"User logged in: {user.email}")
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
@handle_http_errors("Token refresh failed")
async def refresh_token(request: RefreshTokenRequest) -> TokenResponse:
    """
    Generate new access token using refresh token.
    
    - **refresh_token**: Valid refresh token from login
    
    Returns new access token.
    """
    result = await asyncio.to_thread(
        auth_service.refresh_access_token,
        refresh_token=request.refresh_token
    )
    
    return TokenResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
@handle_http_errors("Failed to get profile")
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current authenticated user's profile.
    
    Requires: Valid JWT token in Authorization header.
    """
    return UserResponse(**current_user.to_dict())


@router.put("/me", response_model=UserResponse, summary="Update current user profile")
@handle_http_errors("Failed to update profile")
async def update_current_user_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Update current user's profile information.
    
    Requires: Valid JWT token in Authorization header.
    """
    # Update fields if provided
    update_data = request.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(current_user, field) and value is not None:
            setattr(current_user, field, value)
    
    # Save changes
    await asyncio.to_thread(current_user.save)
    
    logger.info(f"User profile updated: {current_user.email}")
    
    return UserResponse(**current_user.to_dict())


@router.post("/change-password", summary="Change password")
@handle_http_errors("Failed to change password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Change current user's password.
    
    Requires: Valid JWT token in Authorization header.
    """
    # Verify current password
    if not current_user.verify_password(request.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Set new password
    current_user.set_password(request.new_password)
    await asyncio.to_thread(current_user.save)
    
    logger.info(f"Password changed for user: {current_user.email}")
    
    return {"message": "Password changed successfully"}


@router.post("/logout", summary="Logout (client-side)")
async def logout(current_user: User = Depends(get_current_user)) -> dict:
    """
    Logout endpoint (for completeness).
    
    Note: JWT tokens are stateless, so logout is handled client-side
    by deleting the token. This endpoint just validates the token is valid.
    
    For true token invalidation, implement a token blacklist in Redis.
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return {
        "message": "Logged out successfully",
        "note": "Please delete the token on client side"
    }


@router.delete("/me", summary="Delete current user account")
@handle_http_errors("Failed to delete account")
async def delete_current_user(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Delete current user's account.
    
    Requires: Valid JWT token in Authorization header.
    Warning: This action cannot be undone!
    """
    email = current_user.email
    await asyncio.to_thread(current_user.delete)
    
    logger.warning(f"User account deleted: {email}")
    
    return {"message": "Account deleted successfully"}


@router.post("/forgot-password", summary="Request password reset")
@handle_http_errors("Failed to process password reset request")
async def forgot_password(request: ForgotPasswordRequest) -> dict:
    """
    Request password reset link (for users who forgot their password).
    
    - **email**: Your registered email address
    
    A password reset link will be sent to your email if the account exists.
    The link expires in 1 hour.
    """
    # Check if email service is configured
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Please contact administrator."
        )
    
    # Always return success (don't reveal if email exists)
    # This prevents email enumeration attacks
    
    # Check if user exists
    user = await asyncio.to_thread(User.get_by_email, request.email)
    
    if user:
        # Create reset token
        reset_token = await asyncio.to_thread(
            PasswordResetToken.create_reset_token,
            email=request.email,
            expiry_hours=1  # 1 hour expiry
        )
        
        # Send reset email
        email_sent = await asyncio.to_thread(
            email_service.send_password_reset_email,
            to_email=request.email,
            reset_token=reset_token.token,
            expiry_hours=1
        )
        
        if email_sent:
            logger.info(f"Password reset email sent to: {request.email}")
        else:
            logger.error(f"Failed to send password reset email to: {request.email}")
    else:
        logger.info(f"Password reset requested for non-existent email: {request.email}")
    
    # Always return success message (security best practice)
    return {
        "message": "If an account exists with that email, a password reset link has been sent.",
        "note": "Please check your email inbox and spam folder."
    }


@router.post("/reset-password", summary="Reset password with token")
@handle_http_errors("Failed to reset password")
async def reset_password(request: ResetPasswordRequest) -> dict:
    """
    Reset password using the token from email link.
    
    - **token**: Reset token from email link
    - **new_password**: New password (at least 8 characters with letters and numbers)
    
    After successful reset, you can login with your new password.
    """
    # Get reset token
    reset_token = await asyncio.to_thread(
        PasswordResetToken.get_by_token,
        request.token
    )
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Check if token is valid
    if not reset_token.is_valid():
        if reset_token.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset link has already been used. Please request a new one."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset link expired. Please request a new one."
            )
    
    # Get user
    user = await asyncio.to_thread(User.get_by_email, reset_token.email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found"
        )
    
    # Update password
    user.set_password(request.new_password)
    await asyncio.to_thread(user.save)
    
    # Mark token as used
    await asyncio.to_thread(reset_token.mark_as_used)
    
    logger.info(f"Password reset successful for: {user.email}")
    
    return {
        "message": "Password reset successfully. You can now login with your new password."
    }

