import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional
import os
import json

from app.config import settings
from app.services.news_service import news_service
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class EmailService:
    """Service for handling email operations"""
    
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.sender_email = settings.sender_email
        self.sender_password = settings.sender_password
    
    def send_daily_news_email(self, recipient_email: str = "williamjohnie61@gmail.com", 
                             news_topics: Optional[List[str]] = None, 
                             custom_content: Optional[str] = None) -> str:
        """Send daily news digest email with flexible content"""
        try:
            # Check email configuration
            if not all([self.sender_email, self.sender_password, recipient_email]):
                return "Email configuration incomplete. Please set SENDER_EMAIL, SENDER_PASSWORD, and provide recipient_email in .env file"
            
            # Start building email content
            email_content = self._build_email_html(news_topics, custom_content)
            
            # Send email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📰 Daily News Digest - {datetime.now().strftime('%B %d, %Y')}"
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            html_part = MIMEText(email_content, 'html')
            msg.attach(html_part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            return f"✅ Daily news digest email sent successfully to {recipient_email}"
            
        except Exception as e:
            logger.error(f"Error sending daily news email: {e}")
            return f"Error sending email: {e}"
    
    def _build_email_html(self, news_topics: Optional[List[str]], custom_content: Optional[str]) -> str:
        """Build the HTML email content"""
        email_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; }}
                .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .section {{ margin: 20px 0; padding: 20px; border-left: 4px solid #3498db; background-color: #f8f9fa; border-radius: 5px; }}
                .news-item {{ margin: 15px 0; padding: 15px; background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .news-title {{ font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 10px; }}
                .news-summary {{ color: #555; margin-bottom: 10px; line-height: 1.5; }}
                .news-source {{ color: #7f8c8d; font-size: 0.9em; margin-top: 10px; }}
                .news-source a {{ color: #3498db; text-decoration: none; }}
                .news-source a:hover {{ text-decoration: underline; }}
                .footer {{ text-align: center; margin-top: 30px; padding: 20px; background-color: #ecf0f1; border-radius: 5px; }}
                .emoji {{ font-size: 1.2em; }}
                hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
                strong {{ color: #2c3e50; }}
                .custom-content {{ background-color: #e8f4fd; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1><span class="emoji">📰</span> Daily News Digest</h1>
                <p>{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
        """
        
        # Add custom content if provided
        if custom_content:
            custom_html = self._convert_content_to_html(custom_content)
            email_content += f"""
            <div class="custom-content">
                <h2><span class="emoji">🤖</span> AI Generated Content</h2>
                <div class="news-content">
                    {custom_html}
                </div>
            </div>
            """
        
        # Add news topics if provided
        if news_topics:
            for topic in news_topics:
                try:
                    # Get news for this topic
                    topic_news = news_service.search_news(
                        topic=topic,
                        location="Global",
                        age_group="general",
                        max_results=3,
                        time_period="recent"
                    )
                    
                    # Convert the content to HTML
                    topic_html = self._convert_content_to_html(topic_news)
                    topic_emoji = self._get_topic_emoji(topic)
                    
                    email_content += f"""
                    <div class="section">
                        <h2><span class="emoji">{topic_emoji}</span> {topic} News</h2>
                        <div class="news-content">
                            {topic_html}
                        </div>
                    </div>
                    """
                    
                except Exception as e:
                    logger.error(f"Error getting news for topic {topic}: {e}")
                    email_content += f"""
                    <div class="section">
                        <h2><span class="emoji">❌</span> {topic} News</h2>
                        <p>Unable to fetch news for this topic at the moment.</p>
                    </div>
                    """
        
        # If no custom content or topics provided, get some default news
        if not custom_content and not news_topics:
            try:
                # Get some general news
                general_news = news_service.search_news(
                    topic="latest news",
                    location="Global",
                    age_group="general",
                    max_results=5,
                    time_period="recent"
                )
                
                general_html = self._convert_content_to_html(general_news)
                
                email_content += f"""
                <div class="section">
                    <h2><span class="emoji">🌍</span> Latest News</h2>
                    <div class="news-content">
                        {general_html}
                    </div>
                </div>
                """
                
            except Exception as e:
                logger.error(f"Error getting default news: {e}")
                email_content += f"""
                <div class="section">
                    <h2><span class="emoji">❌</span> News</h2>
                    <p>Unable to fetch news at the moment. Please try again later.</p>
                </div>
                """
        
        email_content += f"""
            <div class="footer">
                <p><span class="emoji">🤖</span> Generated by Artemis AI News Assistant</p>
                <p style="font-size: 0.9em; color: #7f8c8d;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </body>
        </html>
        """
        
        return email_content
    
    def _convert_content_to_html(self, content: str) -> str:
        """Convert markdown-style content to HTML for email"""
        if not content:
            return ""
        
        # Convert **bold** to <strong>
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        
        # Convert markdown links [text](url) to HTML links
        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #3498db; text-decoration: none;">\1</a>', content)
        
        # Convert line breaks to <br> tags
        content = content.replace('\n', '<br>')
        
        # Convert separator lines
        content = re.sub(r'─{10,}', '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">', content)
        
        return content
    
    def _get_topic_emoji(self, topic: str) -> str:
        """Get emoji for topic"""
        topic_lower = topic.lower()
        if any(word in topic_lower for word in ['tech', 'technology', 'ai', 'artificial intelligence']):
            return "💻"
        elif any(word in topic_lower for word in ['business', 'economy', 'finance']):
            return "💰"
        elif any(word in topic_lower for word in ['sports', 'football', 'basketball']):
            return "⚽"
        elif any(word in topic_lower for word in ['politics', 'government']):
            return "🏛️"
        elif any(word in topic_lower for word in ['health', 'medical', 'covid']):
            return "🏥"
        elif any(word in topic_lower for word in ['entertainment', 'movie', 'music']):
            return "🎬"
        elif any(word in topic_lower for word in ['science', 'research']):
            return "🔬"
        elif any(word in topic_lower for word in ['tanzania', 'africa']):
            return "🇹🇿"
        else:
            return "📰"
    
    def setup_daily_news_schedule(self, recipient_email: str = "williamjohnie61@gmail.com", 
                                 time: str = "08:00", include_tanzania: bool = True, 
                                 include_tech: bool = True) -> str:
        """Setup daily news email schedule"""
        try:
            # Create schedule configuration
            schedule_config = {
                'recipient_email': recipient_email,
                'time': time,
                'include_tanzania': include_tanzania,
                'include_tech': include_tech,
                'created_at': datetime.now().isoformat(),
                'active': True
            }
            
            # Save configuration
            config_dir = settings.data_dir
            os.makedirs(config_dir, exist_ok=True)
            config_file = os.path.join(config_dir, 'news_schedule.json')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(schedule_config, f, indent=2)
            
            return f"✅ Daily news schedule configured successfully!\n\n" \
                   f"📧 Recipient: {recipient_email}\n" \
                   f"⏰ Time: {time}\n" \
                   f"🇹🇿 Tanzania News: {'Yes' if include_tanzania else 'No'}\n" \
                   f"🌍 Tech News: {'Yes' if include_tech else 'No'}\n\n" \
                   f"To start the scheduler, run: python news_scheduler.py"
            
        except Exception as e:
            logger.error(f"Error setting up news schedule: {e}")
            return f"Error setting up schedule: {e}"

# Global email service instance
email_service = EmailService() 