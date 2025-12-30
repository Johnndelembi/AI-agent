"""
Email service for sending emails via Google SMTP.
Handles all email operations using Gmail SMTP server.
"""

import os
import smtplib
import re
from typing import List, Optional
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from app.config import (
    SMTP_SERVER,
    SMTP_PORT,
    SENDER_EMAIL,
    SENDER_PASSWORD,
    logger,
    settings
)


class EmailService:
    """
    Service for sending emails via Google SMTP.
    Configured via environment variables in .env file.
    """
    
    def __init__(self):
        """Initialize email service with Google SMTP configuration."""
        self.smtp_server = SMTP_SERVER or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = SMTP_PORT or int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = SENDER_EMAIL or os.getenv("SENDER_EMAIL")
        self.sender_password = SENDER_PASSWORD or os.getenv("SENDER_PASSWORD")
        self.app_name = os.getenv("APP_NAME", "AI Agent")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        if not self.sender_email or not self.sender_password:
            logger.warning(
                "Email service not fully configured. "
                "Set SENDER_EMAIL and SENDER_PASSWORD in .env for Google SMTP"
            )
    
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(self.sender_email and self.sender_password)
    
    def _convert_markdown_to_html(self, content: str) -> str:
        """Convert markdown-style content to HTML."""
        if not content:
            return ""
        
        # Convert **bold** to <strong>
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        # Convert *italic* to <em>
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        # Convert markdown links [text](url) to HTML links
        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #3498db;">\1</a>', content)
        # Convert line breaks
        content = content.replace('\n', '<br>')
        # Convert separator lines
        content = re.sub(r'^---+\s*$', '<hr style="border: 1px solid #ddd; margin: 20px 0;">', content, flags=re.MULTILINE)
        
        return content
    
    def _create_email_template(self, subject: str, content: str, footer_text: Optional[str] = None) -> str:
        """Create a standardized HTML email template."""
        footer = footer_text or f"Sent from {self.app_name} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }}
        .email-container {{
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .content {{
            padding: 30px;
            background-color: #ffffff;
        }}
        .content p {{
            margin: 15px 0;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            background-color: #f8f9fa;
            color: #666;
            font-size: 12px;
            border-top: 1px solid #e9ecef;
        }}
        .button {{
            display: inline-block;
            padding: 12px 30px;
            background-color: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .button:hover {{
            background-color: #5568d3;
        }}
        .code-box {{
            background-color: #f8f9fa;
            border: 2px solid #667eea;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
        }}
        .code {{
            font-size: 36px;
            font-weight: bold;
            letter-spacing: 8px;
            color: #667eea;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>{subject}</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>{footer}</p>
            <p>© {datetime.now().year} {self.app_name}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
        return html_content
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        content: str,
        is_html: bool = True,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send an email via Google SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            content: Email content (HTML or plain text)
            is_html: Whether content is HTML (default: True)
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            attachments: Optional list of file paths to attach
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.error("Email service not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.app_name} <{self.sender_email}>"
            msg['To'] = to_email
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add content
            if is_html:
                msg.attach(MIMEText(content, 'html'))
            else:
                msg.attach(MIMEText(content, 'plain'))
            
            # Add attachments if provided
            if attachments:
                for file_path in attachments:
                    try:
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}'
                            )
                            msg.attach(part)
                    except Exception as e:
                        logger.warning(f"Failed to attach {file_path}: {e}")
            
            # Determine all recipients
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            # Send email via Google SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg, to_addrs=recipients)
            
            logger.info(f"✅ Email sent successfully to {to_email} (subject: {subject})")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP authentication failed: {e}. Check SENDER_EMAIL and SENDER_PASSWORD")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}", exc_info=True)
            return False
    
    def send_simple_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        use_template: bool = True
    ) -> bool:
        """
        Send a simple email with optional template.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Plain text or markdown message
            use_template: Whether to use HTML template (default: True)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if use_template:
            html_content = self._convert_markdown_to_html(message)
            content = self._create_email_template(subject, html_content)
        else:
            content = message
        
        return self.send_email(to_email, subject, content, is_html=use_template)
    
    def send_verification_code(self, to_email: str, code: str, expiry_minutes: int = 10) -> bool:
        """
        Send email verification code.
        
        Args:
            to_email: Recipient email address
            code: Verification code
            expiry_minutes: Code expiry time in minutes
            
        Returns:
            True if email sent successfully, False otherwise
        """
        subject = f"Your {self.app_name} Verification Code"
        content = f"""
            <p>Thank you for registering! Use this code to verify your email:</p>
            <div class="code-box">
                <div class="code">{code}</div>
                <div style="color: #e74c3c; font-size: 14px; margin-top: 10px;">
                    ⏰ Expires in {expiry_minutes} minute{'s' if expiry_minutes != 1 else ''}
                </div>
            </div>
            <p>Enter this code to activate your account.</p>
            <p><strong>Security:</strong> Never share this code. If you didn't request it, ignore this email.</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_password_reset_email(self, to_email: str, reset_token: str, expiry_hours: int = 1) -> bool:
        """
        Send password reset email with reset link.
        
        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            expiry_hours: Token expiry time in hours
            
        Returns:
            True if email sent successfully, False otherwise
        """
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        subject = f"Reset Your {self.app_name} Password"
        content = f"""
            <p>We received a request to reset your password.</p>
            <p style="text-align: center;">
                <a href="{reset_link}" class="button">Reset Password</a>
            </p>
            <div style="color: #e74c3c; font-size: 14px; text-align: center;">
                ⏰ This link expires in {expiry_hours} hour{'s' if expiry_hours != 1 else ''}
            </div>
            <p>Or copy this link:</p>
            <div style="background: #f8f9fa; border: 1px solid #ddd; padding: 10px; margin: 10px 0; word-break: break-all; font-size: 12px; border-radius: 5px;">
                {reset_link}
            </div>
            <p><strong>Security:</strong> If you didn't request this, ignore this email.</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_welcome_email(self, to_email: str, fullname: str = "") -> bool:
        """
        Send welcome email to new user.
        
        Args:
            to_email: Recipient email address
            fullname: User's full name (optional)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        greeting = f"Hello {fullname}!" if fullname else "Hello!"
        subject = f"Welcome to {self.app_name}!"
        content = f"""
            <p>{greeting}</p>
            <p>Your account has been successfully created and verified! 🚀</p>
            <p>You can now start using all features of {self.app_name}.</p>
            <p>Thank you for joining us!</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_notification_email(
        self,
        to_email: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None
    ) -> bool:
        """
        Send a notification email.
        
        Args:
            to_email: Recipient email address
            title: Notification title
            message: Notification message
            action_url: Optional action URL (e.g., link to view details)
            action_text: Optional action button text
            
        Returns:
            True if email sent successfully, False otherwise
        """
        subject = f"{self.app_name} - {title}"
        content = f"<h2>{title}</h2><p>{message}</p>"
        
        if action_url and action_text:
            content += f'<p style="text-align: center;"><a href="{action_url}" class="button">{action_text}</a></p>'
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)


# Singleton instance
email_service = EmailService()

