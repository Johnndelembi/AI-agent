"""
Email service for sending emails via Google SMTP.
Handles all email operations using Gmail SMTP server.
"""

import os
import smtplib
import re
from typing import List, Optional, Dict
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
    settings,
    CHATBOT_MODEL,
    MODEL_PROVIDER
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
        self.app_name = os.getenv("APP_NAME", "Artemis - AI Assistant")
        self.frontend_url = os.getenv("FRONTEND_URL", "https://artemis.ares.codes")
        self._warned = False  # Track if we've already warned about missing config
    
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
    
    def _generate_ai_tip(
        self,
        profession: str = "",
        use_case: str = "",
        interests: List[str] = None,
        goals: str = ""
    ) -> str:
        """
        Generate a personalized AI tip based on user engagement data.
        
        Args:
            profession: User's profession
            use_case: How the user uses Artemis
            interests: List of user interests
            goals: User's goals
            
        Returns:
            Generated tip string, or fallback tip if AI generation fails
        """
        if interests is None:
            interests = []
        
        try:
            from app.services.agent_service import init_chat_model
            from langchain_core.messages import HumanMessage
            
            # Initialize LLM
            llm = init_chat_model(CHATBOT_MODEL, model_provider=MODEL_PROVIDER)
            
            # Build context for personalization
            context_parts = []
            if profession:
                context_parts.append(f"Profession: {profession}")
            if use_case:
                context_parts.append(f"Primary use case: {use_case}")
            if interests:
                context_parts.append(f"Interests: {', '.join(interests)}")
            if goals:
                context_parts.append(f"Goals: {goals}")
            
            context = "\n".join(context_parts) if context_parts else "General user"
            
            # Create prompt for personalized tip generation
            prompt = f"""Generate a single, concise, and actionable tip for using Artemis AI assistant. 

User Context:
{context}

Requirements:
- The tip should be personalized to resonate with this user's profession, use case, interests, or goals
- Keep it to one sentence (maximum 2 sentences)
- Make it practical and actionable
- Focus on how Artemis can help them specifically
- Be encouraging and friendly
- Do not include markdown formatting, just plain text

Generate only the tip text, nothing else:"""
            
            # Generate tip using LLM
            response = llm.invoke([HumanMessage(content=prompt)])
            tip = response.content.strip()
            
            # Validate and clean the tip
            if tip and len(tip) > 10:  # Basic validation
                # Remove any quotes or extra formatting
                tip = tip.strip('"\'`').strip()
                logger.info(f"✅ AI-generated personalized tip: {tip[:50]}...")
                return tip
            else:
                raise ValueError("Generated tip is too short or invalid")
                
        except Exception as e:
            logger.warning(f"Failed to generate AI tip: {e}. Using fallback tip.")
            # Fallback to generic but still relevant tip
            if use_case:
                return f"Try using Artemis for {use_case.lower()} - ask specific questions to get the best results!"
            elif profession:
                return f"As a {profession.lower()}, use Artemis to streamline your workflow with targeted questions."
            else:
                return "Use specific questions with Artemis to get more accurate and helpful responses tailored to your needs."
    
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
            if not self._warned:
                logger.warning(
                    "Email service not fully configured. "
                    "Set SENDER_EMAIL and SENDER_PASSWORD in .env for Google SMTP"
                )
                self._warned = True
            logger.error("Email service not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.app_name} <artemis@ares.codes>"
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
    
    def send_welcome_email(self, to_email: str, fullname: str = "") -> bool:
        """
        Send welcome email to new user (enhanced with personalization).
        
        Args:
            to_email: Recipient email address
            fullname: User's full name (optional)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        greeting = f"Hello {fullname}!" if fullname else "Hi there!"
        subject = f"Welcome to {self.app_name}!"
        content = f"""
            <p>{greeting}</p>
            <p>We are thrilled to have you join {self.app_name}. As our most valued user, we aim to provide you with the best experience possible. Your all-in-one AI assistant platform.</p>
            <p>You can now start using all features of {self.app_name}.</p>
            <p><strong>Getting Started:</strong></p>
            <ul>
                <li>Start a conversation with Artemis to get instant AI-powered assistance</li>
                <li>Explore our features and discover how Artemis can help you</li>
                <li>Customize your experience to match your needs</li>
            </ul>
            <p style="text-align: center;">
                <a href="{self.frontend_url}" class="button">Get Started</a>
            </p>
            <p>Thank you for joining us!</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_re_engagement_email(self, to_email: str, fullname: str = "", days_inactive: int = 3) -> bool:
        """
        Send re-engagement email to inactive users.
        
        Args:
            to_email: Recipient email address
            fullname: User's full name (optional)
            days_inactive: Number of days since last activity
            
        Returns:
            True if email sent successfully, False otherwise
        """
        greeting = f"Hello {fullname}!" if fullname else "Hi there!"
        subject = f"We miss you at {self.app_name}!"
        content = f"""
            <p>{greeting}</p>
            <p>We noticed you haven't been active on {self.app_name} in a while. We'd love to have you back!</p>
            <p><strong>What's New:</strong></p>
            <ul>
                <li>Enhanced AI capabilities for better assistance</li>
                <li>New features to make your experience even better</li>
                <li>Improved performance and reliability</li>
            </ul>
            <p>Come back and discover what's new, or simply continue where you left off.</p>
            <p style="text-align: center;">
                <a href="{self.frontend_url}" class="button">Return to {self.app_name}</a>
            </p>
            <p>We're here whenever you need us!</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_engagement_form_email(self, to_email: str, fullname: str = "", total_chats: int = 0) -> bool:
        """
        Send engagement form email to active users to collect information.
        
        Args:
            to_email: Recipient email address
            fullname: User's full name (optional)
            total_chats: Total number of chats the user has had
            
        Returns:
            True if email sent successfully, False otherwise
        """
        greeting = f"Hello {fullname}!" if fullname else "Hi there!"
        subject = f"Help us get to know you better, {fullname or 'there'}!"
        
        # Create embedded form
        form_url = f"{self.frontend_url}/engagement/form"
        
        content = f"""
            <p>{greeting}</p>
            <p>We see you've been actively using {self.app_name} - that's amazing! You've had <strong>{total_chats} conversations</strong> with Artemis so far.</p>
            <p>To help us serve you better and send you personalized tips and valuable information, we'd love to learn more about you.</p>
            <p><strong>Quick Questions:</strong></p>
            <ul>
                <li>How do you use Artemis in your daily work?</li>
                <li>What are your main interests or goals?</li>
            </ul>
            <p style="text-align: center;">
                <a href="{form_url}" class="button">Tell Us About Yourself</a>
            </p>
            <p>This will only take a minute, and it helps us tailor your experience!</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_curated_email(
        self,
        to_email: str,
        fullname: str = "",
        engagement_data: Optional[Dict] = None
    ) -> bool:
        """
        Send curated email with personalized tips based on user engagement data.
        
        Args:
            to_email: Recipient email address
            fullname: User's full name (optional)
            engagement_data: Dictionary with user engagement info (use_case, profession, interests, goals)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        greeting = f"Hello {fullname}!" if fullname else "Hi there!"
        subject = f"Your Daily {self.app_name} Tip"
        
        # Generate personalized content based on engagement data
        profession = engagement_data.get('profession', '') if engagement_data else ''
        use_case = engagement_data.get('use_case', '') if engagement_data else ''
        interests = engagement_data.get('interests', []) if engagement_data else []
        goals = engagement_data.get('goals', '') if engagement_data else ''
        
        # Generate AI-powered personalized tip
        selected_tip = self._generate_ai_tip(
            profession=profession,
            use_case=use_case,
            interests=interests if isinstance(interests, list) else [],
            goals=goals
        )
        
        # Build personalized tip content
        tip_content = "<p><strong>Today's Tip:</strong></p>"
        
        if profession:
            tip_content += f"<p>For {profession.lower()} professionals like you, here's a valuable tip to maximize your productivity with {self.app_name}:</p>"
        else:
            tip_content += f"<p>Here's a valuable tip to help you get the most out of {self.app_name}:</p>"
        
        tip_content += f"<p><em>{selected_tip}</em></p>"
        
        if use_case:
            tip_content += f"<p>Since you use Artemis for <strong>{use_case.lower()}</strong>, this tip should be particularly helpful!</p>"
        
        content = f"""
            <p>{greeting}</p>
            {tip_content}
            <p style="text-align: center;">
                <a href="{self.frontend_url}" class="button">Try It Now</a>
            </p>
            <p>Have a productive day!</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_referral_campaign_email(
        self,
        to_email: str,
        fullname: str = "",
        referral_code: Optional[str] = None,
        referral_link: Optional[str] = None,
        points_balance: int = 0,
        referral_count: int = 0
    ) -> bool:
        """
        Send referral campaign email encouraging users to share Artemis.
        
        Args:
            to_email: Recipient email address
            fullname: User's full name (optional)
            referral_code: User's unique referral code
            referral_link: Full referral link
            points_balance: Current points balance
            referral_count: Number of successful referrals
            
        Returns:
            True if email sent successfully, False otherwise
        """
        greeting = f"Hello {fullname}!" if fullname else "Hi there!"
        subject = f"Share {self.app_name} and Earn Rewards!"
        
        # Build referral content
        referral_section = ""
        if referral_code and referral_link:
            referral_section = f"""
                <div class="code-box">
                    <p><strong>Your Referral Code:</strong></p>
                    <div class="code">{referral_code}</div>
                    <p style="text-align: center; margin-top: 20px;">
                        <a href="{referral_link}" class="button">Share Your Link</a>
                    </p>
                </div>
            """
        else:
            referral_section = f"""
                <p style="text-align: center;">
                    <a href="{self.frontend_url}/referral" class="button">Get Your Referral Code</a>
                </p>
            """
        
        points_section = ""
        if points_balance > 0:
            points_section = f"""
                <p><strong>Your Current Points:</strong> {points_balance}</p>
                <p>You're making great progress! Keep sharing to unlock amazing rewards.</p>
            """
        
        if referral_count > 0:
            points_section += f"<p>You've already referred <strong>{referral_count} friend(s)</strong> - thank you!</p>"
        
        content = f"""
            <p>{greeting}</p>
            <p>Love using {self.app_name}? Share it with your friends and colleagues, and earn rewards!</p>
            <p><strong>How It Works:</strong></p>
            <ul>
                <li>Share your unique referral link with friends</li>
                <li>When they sign up and have 5+ conversations, you earn <strong>100 points</strong></li>
                <li>Redeem points for valuable rewards like a <strong>Custom TTS Voice (500 points)</strong></li>
            </ul>
            {referral_section}
            {points_section}
            <p><strong>Why Share?</strong></p>
            <ul>
                <li>Help your friends discover an amazing AI assistant</li>
                <li>Earn points for every successful referral</li>
                <li>Unlock exclusive rewards and features</li>
            </ul>
            <p>Start sharing today and watch your points grow!</p>
        """
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)
    
    def send_points_notification_email(
        self,
        to_email: str,
        fullname: str = "",
        points_awarded: int = 0,
        reason: str = "referral"
    ) -> bool:
        """
        Send notification email when user earns points.
        
        Args:
            to_email: Recipient email address
            fullname: User's full name (optional)
            points_awarded: Number of points awarded
            reason: Reason for points (e.g., "referral", "milestone")
            
        Returns:
            True if email sent successfully, False otherwise
        """
        greeting = f"Hello {fullname}!" if fullname else "Hi there!"
        subject = f"🎉 You've Earned {points_awarded} Points!"
        
        reason_text = ""
        if reason == "referral":
            reason_text = "A friend you referred has reached 5+ conversations!"
        else:
            reason_text = f"You've reached a new milestone: {reason}!"
        
        content = f"""
            <p>{greeting}</p>
            <p><strong>Congratulations! 🎉</strong></p>
            <p>You've just earned <strong>{points_awarded} points</strong>!</p>
            <p>{reason_text}</p>
            <div class="code-box">
                <p style="font-size: 24px; margin: 0;"><strong>{points_awarded} Points</strong></p>
            </div>
            <p><strong>What's Next?</strong></p>
            <ul>
                <li>Keep sharing to earn more points</li>
                <li>Redeem points for rewards like a Custom TTS Voice (500 points)</li>
                <li>Check your points balance anytime</li>
            </ul>
            <p style="text-align: center;">
                <a href="{self.frontend_url}/referral" class="button">View Your Points</a>
            </p>
            <p>Thank you for being an amazing member of the {self.app_name} community!</p>
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
        subject = f"{title}"
        content = f"<p>{message}</p>"
        
        if action_url and action_text:
            content += f'<p style="text-align: center;"><a href="{action_url}" class="button">{action_text}</a></p>'
        
        html_content = self._create_email_template(subject, content)
        return self.send_email(to_email, subject, html_content)


# Singleton instance
email_service = EmailService()

