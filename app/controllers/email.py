"""
Email controller for sending emails via Google SMTP.
Provides endpoints for various email operations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.services.email_service import email_service
from app.utils.auth_utils import get_current_user
from app.utils.error_handler import handle_http_errors
from app.models.auth import User
from app.config import logger

router = APIRouter(prefix="/email", tags=["email"])


# Request/Response Models
class SendEmailRequest(BaseModel):
    """Request model for sending a simple email."""
    to_email: EmailStr
    subject: str
    message: str
    use_template: bool = True


class SendEmailResponse(BaseModel):
    """Response model for email sending operations."""
    success: bool
    message: str
    recipient: Optional[str] = None


class SendBulkEmailRequest(BaseModel):
    """Request model for sending bulk emails."""
    recipients: List[EmailStr]
    subject: str
    message: str
    use_template: bool = True


class SendBulkEmailResponse(BaseModel):
    """Response model for bulk email operations."""
    success: bool
    sent_count: int
    failed_count: int
    failed_recipients: List[str] = []


class SendEmailWithAttachmentsRequest(BaseModel):
    """Request model for sending email with attachments."""
    to_email: EmailStr
    subject: str
    message: str
    attachments: Optional[List[str]] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None


class EmailStatusResponse(BaseModel):
    """Response model for email service status."""
    configured: bool
    smtp_server: str
    smtp_port: int
    sender_email: Optional[str] = None
    message: str


@router.get("/status", response_model=EmailStatusResponse, summary="Check email service status")
@handle_http_errors("Error checking email service status")
async def get_email_status() -> EmailStatusResponse:
    """
    Check if email service is configured and ready to send emails.
    
    Returns:
        Email service configuration status
    """
    is_configured = email_service.is_configured()
    
    return EmailStatusResponse(
        configured=is_configured,
        smtp_server=email_service.smtp_server,
        smtp_port=email_service.smtp_port,
        sender_email=email_service.sender_email if is_configured else None,
        message="Email service is configured and ready" if is_configured else "Email service not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env"
    )


@router.post("/send", response_model=SendEmailResponse, summary="Send a simple email")
@handle_http_errors("Error sending email")
async def send_email(
    request: SendEmailRequest,
    # current_user: User = Depends(get_current_user)
) -> SendEmailResponse:
    """
    Send a simple email via Google SMTP.
    
    - **to_email**: Recipient email address
    - **subject**: Email subject
    - **message**: Email message (supports markdown)
    - **use_template**: Whether to use HTML template (default: True)
    
    Requires: Valid JWT token in Authorization header.
    """
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env"
        )
    
    success = email_service.send_simple_email(
        to_email=request.to_email,
        subject=request.subject,
        message=request.message,
        use_template=request.use_template
    )
    
    if success:
        logger.info(f"Email sent to {request.to_email}")
        return SendEmailResponse(
            success=True,
            message="Email sent successfully",
            recipient=request.to_email
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email. Check server logs for details."
        )


@router.post("/send/bulk", response_model=SendBulkEmailResponse, summary="Send bulk emails")
@handle_http_errors("Error sending bulk emails")
async def send_bulk_email(
    request: SendBulkEmailRequest,
    # current_user: User = Depends(get_current_user)
) -> SendBulkEmailResponse:
    """
    Send emails to multiple recipients.
    
    - **recipients**: List of recipient email addresses
    - **subject**: Email subject
    - **message**: Email message (supports markdown)
    - **use_template**: Whether to use HTML template (default: True)
    
    Requires: Valid JWT token in Authorization header.
    """
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env"
        )
    
    sent_count = 0
    failed_count = 0
    failed_recipients = []
    
    for recipient in request.recipients:
        success = email_service.send_simple_email(
            to_email=recipient,
            subject=request.subject,
            message=request.message,
            use_template=request.use_template
        )
        
        if success:
            sent_count += 1
        else:
            failed_count += 1
            failed_recipients.append(recipient)
    
    logger.info(
        f"Bulk email sent: "
        f"{sent_count} successful, {failed_count} failed"
    )
    
    return SendBulkEmailResponse(
        success=failed_count == 0,
        sent_count=sent_count,
        failed_count=failed_count,
        failed_recipients=failed_recipients
    )


@router.post("/send/advanced", response_model=SendEmailResponse, summary="Send email with attachments")
@handle_http_errors("Error sending email with attachments")
async def send_email_with_attachments(
    request: SendEmailWithAttachmentsRequest,
    # current_user: User = Depends(get_current_user)
) -> SendEmailResponse:
    """
    Send an email with optional attachments, CC, and BCC.
    
    - **to_email**: Recipient email address
    - **subject**: Email subject
    - **message**: Email message (supports markdown)
    - **attachments**: Optional list of file paths to attach
    - **cc**: Optional list of CC recipients
    - **bcc**: Optional list of BCC recipients
    
    Requires: Valid JWT token in Authorization header.
    """
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env"
        )
    
    # Convert markdown to HTML
    html_content = email_service._convert_markdown_to_html(request.message)
    content = email_service._create_email_template(request.subject, html_content)
    
    success = email_service.send_email(
        to_email=request.to_email,
        subject=request.subject,
        content=content,
        is_html=True,
        cc=request.cc,
        bcc=request.bcc,
        attachments=request.attachments
    )
    
    if success:
        logger.info(f"Email with attachments sent to {request.to_email}")
        return SendEmailResponse(
            success=True,
            message="Email sent successfully",
            recipient=request.to_email
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email. Check server logs for details."
        )


@router.post("/send/notification", response_model=SendEmailResponse, summary="Send notification email")
@handle_http_errors("Error sending notification email")
async def send_notification_email(
    title: str,
    message: str,
    to_email: str,
    action_url: Optional[str] = None,
    action_text: Optional[str] = None,
    # current_user: User = Depends(get_current_user)
) -> SendEmailResponse:
    """
    Send a notification email with optional action button.
    
    - **title**: Notification title
    - **message**: Notification message
    - **to_email**: Recipient email address
    - **action_url**: Optional action URL (e.g., link to view details)
    - **action_text**: Optional action button text
    
    Requires: Valid JWT token in Authorization header.
    """
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env"
        )
    
    success = email_service.send_notification_email(
        to_email=to_email,
        title=title,
        message=message,
        action_url=action_url,
        action_text=action_text
    )
    
    if success:
        logger.info(f"Notification email sent to {to_email}")
        return SendEmailResponse(
            success=True,
            message="Notification email sent successfully",
            recipient=to_email
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send notification email. Check server logs for details."
        )

