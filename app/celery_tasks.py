"""
Celery tasks for background processing.

Tasks here handle CPU-intensive and long-running operations that should
not block the async event loop or web server.
"""

import os
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from app.celery_app import celery_app, cpu_intensive_task, io_bound_task
from app.config import logger, AUDIO_OUTPUT_DIR

# Import MongoEngine models to ensure they're registered in the worker process
# This is necessary because Celery workers run in separate processes
from app.models.auth import User, OTPVerification, PasswordResetToken
from app.models.database import Employee, MealSelection, MealReminder, MealOptions, Conversation

# Import engagement models if available
try:
    from app.models.engagement import UserEngagement, ReferralCode, Referral, UserPoints
except ImportError:
    pass  # Engagement models may not exist yet


# ============================================================================
# TTS TASKS (CPU-Intensive)
# ============================================================================

@cpu_intensive_task(
    name="app.celery_tasks.generate_tts_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
    soft_time_limit=600,  # 10 minutes soft limit
    time_limit=720,  # 12 minutes hard limit
)
def generate_tts_task(self, text: str, voice: Optional[str] = None, lang_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate TTS audio in background (CPU-intensive).
    
    Args:
        text: Text to convert to speech
        voice: Optional voice selection
        lang_code: Optional language code
        
    Returns:
        Dict with audio file paths and metadata
    """
    import gc
    
    try:
        from app.services.tts_service import generate_tts_audio, clear_tts_cache
        
        logger.info(f"🎤 Celery: Generating TTS for {len(text)} characters")
        start_time = time.time()
        
        audio_files = generate_tts_audio(text, voice=voice, lang_code=lang_code)
        
        duration = time.time() - start_time
        logger.info(f"✅ Celery: TTS generation completed in {duration:.2f}s")
        
        # Clear pipeline cache and force garbage collection to free memory
        clear_tts_cache()
        gc.collect()
        logger.info(f"🧹 Memory cleanup completed")
        
        return {
            "status": "success",
            "audio_files": audio_files,
            "duration": duration,
            "text_length": len(text),
        }
    except Exception as e:
        logger.error(f"❌ Celery: TTS generation failed: {e}")
        # Still clean up on error
        try:
            from app.services.tts_service import clear_tts_cache
            clear_tts_cache()
            gc.collect()
        except:
            pass
        raise


# ============================================================================
# EMAIL TASKS (I/O-Bound)
# ============================================================================

@io_bound_task(
    name="app.celery_tasks.send_email_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def send_email_task(
    self,
    recipient_email: str,
    subject: str,
    content: str,
    sender_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send email in background (I/O-bound).
    
    Args:
        recipient_email: Recipient email address
        subject: Email subject
        content: Email content (HTML supported)
        sender_email: Optional sender email
        
    Returns:
        Dict with send status
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import re
        from datetime import datetime
        
        from app.config import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD
        
        logger.info(f"📧 Celery: Sending email to {recipient_email}")
        
        if not all([SENDER_EMAIL, SENDER_PASSWORD, recipient_email]):
            raise ValueError("Email configuration incomplete")
        
        # Convert content to HTML
        def convert_to_html(content: str) -> str:
            if not content:
                return ""
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', content)
            content = content.replace('\n', '<br>')
            return content
        
        email_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <div style="background-color: #2c3e50; color: white; padding: 20px; text-align: center;">
                <h1>{subject}</h1>
            </div>
            <div style="padding: 20px; background-color: #f8f9fa;">
                {convert_to_html(content)}
            </div>
            <div style="text-align: center; padding: 20px; background-color: #ecf0f1;">
                <p>🤖 Sent via Celery Background Task</p>
                <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email or SENDER_EMAIL
        msg['To'] = recipient_email
        msg.attach(MIMEText(email_html, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"✅ Celery: Email sent successfully to {recipient_email}")
        
        return {
            "status": "success",
            "recipient": recipient_email,
            "subject": subject,
            "sent_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Celery: Email send failed: {e}")
        raise


# ============================================================================
# WEB SCRAPING TASKS (I/O-Bound)
# ============================================================================

@io_bound_task(
    name="app.celery_tasks.scrape_webpage_task",
    bind=True,
    time_limit=60,
)
def scrape_webpage_task(self, url: str) -> Dict[str, Any]:
    """
    Scrape webpage content in background (I/O-bound).
    
    Args:
        url: URL to scrape
        
    Returns:
        Dict with scraped content
    """
    try:
        import asyncio
        from app.services.agent_service import _browse_regular_webpage
        
        logger.info(f"🌐 Celery: Scraping {url}")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            content = loop.run_until_complete(_browse_regular_webpage(url))
        finally:
            loop.close()
        
        logger.info(f"✅ Celery: Scraped {len(content)} characters from {url}")
        
        return {
            "status": "success",
            "url": url,
            "content": content,
            "content_length": len(content),
        }
    except Exception as e:
        logger.error(f"❌ Celery: Web scraping failed: {e}")
        raise


# ============================================================================
# MODEL/AI TASKS (CPU-Intensive)
# ============================================================================

@cpu_intensive_task(
    name="app.celery_tasks.generate_response_task",
    bind=True,
    time_limit=120,
)
def generate_response_task(
    self,
    message: str,
    thread_id: str = "background-task"
) -> Dict[str, Any]:
    """
    Generate AI response in background (CPU-intensive for model inference).
    
    Args:
        message: User message
        thread_id: Thread ID for context
        
    Returns:
        Dict with AI response
    """
    try:
        import asyncio
        from app.services.agent_service import ConversationalAgent
        
        logger.info(f"🤖 Celery: Generating response for message: {message[:50]}...")
        start_time = time.time()
        
        agent = ConversationalAgent()
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                agent.stream_conversation(message, thread_id=thread_id)
            )
        finally:
            loop.close()
        
        duration = time.time() - start_time
        logger.info(f"✅ Celery: Response generated in {duration:.2f}s")
        
        return {
            "status": "success",
            "response": response,
            "duration": duration,
            "thread_id": thread_id,
        }
    except Exception as e:
        logger.error(f"❌ Celery: Response generation failed: {e}")
        raise


# ============================================================================
# MAINTENANCE TASKS
# ============================================================================

@celery_app.task(name="app.celery_tasks.cleanup_old_files_task")
def cleanup_old_files_task(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up old temporary files (periodic task).
    
    Note: Audio files are now stored in GridFS, not filesystem.
    This task only cleans up any leftover temporary files.
    
    Args:
        max_age_hours: Maximum age of files to keep
        
    Returns:
        Dict with cleanup statistics
    """
    try:
        logger.info(f"🧹 Celery: Starting temporary file cleanup (max age: {max_age_hours}h)")
        
        # Audio files are now in GridFS, so we only clean up any leftover temporary files
        if not os.path.exists(AUDIO_OUTPUT_DIR):
            return {"status": "success", "files_deleted": 0, "message": "No audio directory (files are in GridFS)"}
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        deleted_count = 0
        total_size = 0
        
        # Only clean up very old temporary files (older than max_age_hours)
        # Most temporary files should be cleaned up immediately after GridFS save
        for filename in os.listdir(AUDIO_OUTPUT_DIR):
            filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)
            
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if file_time < cutoff_time:
                    file_size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted_count += 1
                    total_size += file_size
        
        if deleted_count > 0:
            logger.info(f"✅ Celery: Cleaned up {deleted_count} temporary files ({total_size / 1024 / 1024:.2f} MB)")
        else:
            logger.info("✅ Celery: No old temporary files to clean up (audio files are in GridFS)")
        
        return {
            "status": "success",
            "files_deleted": deleted_count,
            "space_freed_mb": total_size / 1024 / 1024,
            "cutoff_time": cutoff_time.isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Celery: Cleanup failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="app.celery_tasks.health_check_task")
def health_check_task() -> Dict[str, Any]:
    """
    Periodic health check task.
    
    Returns:
        Dict with health status
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "worker": "celery",
        }
    except Exception as e:
        logger.error(f"❌ Celery: Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# ============================================================================
# WELCOME EMAIL TASKS (I/O-Bound)
# ============================================================================

@io_bound_task(
    name="app.celery_tasks.send_welcome_emails_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
)
def send_welcome_emails_task(self) -> Dict[str, Any]:
    """
    Send welcome emails to new users who haven't received them yet.
    
    This task finds users created in the last 24 hours who are verified
    but haven't received a welcome email, and sends them one.
    
    Returns:
        Dict with email sending statistics
    """
    try:
        from datetime import datetime, timedelta
        from app.services.database_service import connect_db, is_connected
        from app.models.auth import User
        from app.services.auth_service import email_service
        
        # Ensure MongoDB connection
        from app.services.database_service import ensure_connection
        
        if not ensure_connection():
            raise Exception("MongoDB connection not available")
        
        logger.info("📧 Celery: Starting welcome emails task")
        
        # Get users created in the last 24 hours who are verified
        # and haven't received a welcome email (check metadata)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Find new verified users who don't have welcome email sent flag
        new_users = User.objects(
            created_at__gte=cutoff_time,
            is_verified=True,
            is_active=True
        ).exclude('password_hash').all()
        
        sent_count = 0
        failed_count = 0
        total_users = len(new_users)
        
        for user in new_users:
            try:
                # Check if welcome email was already sent (stored in metadata)
                if user.metadata and user.metadata.get('welcome_email_sent'):
                    continue
                
                # Send welcome email
                success = email_service.send_welcome_email(
                    to_email=user.email,
                    fullname=user.fullname or f"{user.first_name} {user.last_name}".strip(),
                    user_id=str(user.id)
                )
                
                if success:
                    # Mark welcome email as sent in user metadata
                    if not user.metadata:
                        user.metadata = {}
                    user.metadata['welcome_email_sent'] = True
                    user.metadata['welcome_email_sent_at'] = datetime.utcnow().isoformat()
                    user.save()
                    sent_count += 1
                    logger.info(f"✅ Sent welcome email to {user.email}")
                else:
                    failed_count += 1
                    logger.warning(f"⚠️ Failed to send welcome email to {user.email}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error sending welcome email to {user.email}: {e}")
                continue
        
        logger.info(f"✅ Celery: Welcome emails sent: {sent_count} successful, {failed_count} failed")
        
        return {
            "status": "success",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": total_users,
        }
    except Exception as e:
        logger.error(f"Error getting new users: {e}")
        return {
            "status": "error",
            "sent_count": 0,
            "failed_count": 0,
            "total_users": 0,
            "error": str(e)
        }


# ============================================================================
# REFERRAL MILESTONE CHECKING TASKS (I/O-Bound)
# ============================================================================

@io_bound_task(
    name="app.celery_tasks.send_welcome_emails_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
)
def send_welcome_emails_task(self) -> Dict[str, Any]:
    """
    Send welcome emails to users registered 1 hour ago.
    
    This task reads user data from database and sends welcome emails.
    All database operations are read-only.
    
    Returns:
        Dict with send statistics
    """
    try:
        from app.services.referral_service import referral_service
        from app.services.database_service import connect_db, is_connected
        from app.models.engagement import Referral
        
        # Ensure MongoDB connection
        from app.services.database_service import ensure_connection
        
        if not ensure_connection():
            raise Exception("MongoDB connection not available")
        
        logger.info("🔍 Celery: Starting referral milestone check")
        
        # Get users registered 1 hour ago
        new_users = engagement_reader_service.get_new_users(hours_ago=1)
        
        sent_count = 0
        failed_count = 0
        
        for user in new_users:
            try:
                success = email_service.send_welcome_email(
                    to_email=user['email'],
                    fullname=user['fullname']
                )
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send welcome email to {user['email']}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Celery: Welcome emails sent: {sent_count} successful, {failed_count} failed")
        
        return {
            "status": "success",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(new_users)
        }
    except Exception as e:
        logger.error(f"❌ Celery: Welcome emails task failed: {e}")
        raise


@io_bound_task(
    name="app.celery_tasks.send_re_engagement_emails_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
)
def send_re_engagement_emails_task(self) -> Dict[str, Any]:
    """
    Send re-engagement emails to inactive users (3+ days since last activity).
    
    This task reads conversation data from database and sends re-engagement emails.
    All database operations are read-only.
    
    Returns:
        Dict with send statistics
    """
    try:
        from app.services.email_service import email_service
        from app.services.engagement_reader_service import engagement_reader_service
        
        logger.info("📧 Celery: Starting re-engagement emails task")
        
        # Get inactive users
        inactive_users = engagement_reader_service.get_inactive_users()
        
        sent_count = 0
        failed_count = 0
        
        for user in inactive_users:
            try:
                days_inactive = 3  # Default threshold
                if user.get('last_activity'):
                    from datetime import datetime
                    if isinstance(user['last_activity'], str):
                        last_activity = datetime.fromisoformat(user['last_activity'].replace('Z', '+00:00'))
                    else:
                        last_activity = user['last_activity']
                    days_inactive = (datetime.utcnow() - last_activity).days
                
                success = email_service.send_re_engagement_email(
                    to_email=user['email'],
                    fullname=user['fullname'],
                    days_inactive=days_inactive
                )
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send re-engagement email to {user['email']}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Celery: Re-engagement emails sent: {sent_count} successful, {failed_count} failed")
        
        return {
            "status": "success",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(inactive_users)
        }
    except Exception as e:
        logger.error(f"❌ Celery: Re-engagement emails task failed: {e}")
        raise


@io_bound_task(
    name="app.celery_tasks.send_engagement_form_emails_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
)
def send_engagement_form_emails_task(self) -> Dict[str, Any]:
    """
    Send engagement form emails to active users (5+ chats) who haven't provided info.
    
    This task reads user and conversation data from database and sends engagement form emails.
    All database operations are read-only.
    
    Returns:
        Dict with send statistics
    """
    try:
        from app.services.email_service import email_service
        from app.services.engagement_reader_service import engagement_reader_service
        
        logger.info("📧 Celery: Starting engagement form emails task")
        
        # Get active users eligible for engagement form
        eligible_users = engagement_reader_service.get_active_users_for_engagement()
        
        sent_count = 0
        failed_count = 0
        
        for user in eligible_users:
            try:
                success = email_service.send_engagement_form_email(
                    to_email=user['email'],
                    fullname=user['fullname'],
                    total_chats=user.get('total_chats', 0)
                )
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send engagement form email to {user['email']}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Celery: Engagement form emails sent: {sent_count} successful, {failed_count} failed")
        
        return {
            "status": "success",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(eligible_users)
        }
    except Exception as e:
        logger.error(f"❌ Celery: Engagement form emails task failed: {e}")
        raise


@io_bound_task(
    name="app.celery_tasks.send_curated_emails_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
)
def send_curated_emails_task(self) -> Dict[str, Any]:
    """
    Send curated daily emails with personalized tips to users who provided engagement info.
    
    This task reads user engagement data from database and sends personalized curated emails.
    All database operations are read-only.
    
    Returns:
        Dict with send statistics
    """
    try:
        from app.services.email_service import email_service
        from app.services.engagement_reader_service import engagement_reader_service
        
        logger.info("📧 Celery: Starting curated emails task")
        
        # Get users eligible for curated emails
        eligible_users = engagement_reader_service.get_users_for_curated_emails()
        
        sent_count = 0
        failed_count = 0
        
        for user in eligible_users:
            try:
                success = email_service.send_curated_email(
                    to_email=user['email'],
                    fullname=user['fullname'],
                    engagement_data=user.get('engagement_data')
                )
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send curated email to {user['email']}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Celery: Curated emails sent: {sent_count} successful, {failed_count} failed")
        
        return {
            "status": "success",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(eligible_users)
        }
    except Exception as e:
        logger.error(f"❌ Celery: Curated emails task failed: {e}")
        raise


@io_bound_task(
    name="app.celery_tasks.send_referral_campaign_emails_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
)
def send_referral_campaign_emails_task(self) -> Dict[str, Any]:
    """
    Send referral campaign emails to active users encouraging them to share Artemis.
    
    This task reads user data, referral codes, and points from database and sends referral emails.
    All database operations are read-only.
    
    Returns:
        Dict with send statistics
    """
    try:
        from app.services.email_service import email_service
        from app.services.engagement_reader_service import engagement_reader_service
        
        logger.info("📧 Celery: Starting referral campaign emails task")
        
        # Get users eligible for referral campaign
        eligible_users = engagement_reader_service.get_users_for_referral_emails()
        
        sent_count = 0
        failed_count = 0
        
        for user in eligible_users:
            try:
                success = email_service.send_referral_campaign_email(
                    to_email=user['email'],
                    fullname=user['fullname'],
                    referral_code=user.get('referral_code'),
                    referral_link=user.get('referral_link'),
                    points_balance=user.get('points_balance', 0),
                    referral_count=user.get('referral_count', 0)
                )
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send referral campaign email to {user['email']}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Celery: Referral campaign emails sent: {sent_count} successful, {failed_count} failed")
        
        return {
            "status": "success",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(eligible_users)
        }
    except Exception as e:
        logger.error(f"❌ Celery: Referral campaign emails task failed: {e}")
        raise


@io_bound_task(
    name="app.celery_tasks.send_points_notification_emails_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
)
def send_points_notification_emails_task(self) -> Dict[str, Any]:
    """
    Send points notification emails to users who received points in the last 24 hours.
    
    This task reads user points data from database and sends notification emails.
    All database operations are read-only.
    
    Returns:
        Dict with send statistics
    """
    try:
        from app.services.email_service import email_service
        from app.services.engagement_reader_service import engagement_reader_service
        
        logger.info("📧 Celery: Starting points notification emails task")
        
        # Get users with recent points awards
        users_with_points = engagement_reader_service.get_users_with_recent_points_awards(hours=24)
        
        sent_count = 0
        failed_count = 0
        
        for user in users_with_points:
            try:
                points_awarded = user.get('points_awarded', 0)
                awards = user.get('awards', [])
                
                # Determine reason from awards
                reason = "referral"
                if awards:
                    first_award = awards[0]
                    if isinstance(first_award, dict):
                        reason = first_award.get('source', 'milestone')
                    else:
                        reason = getattr(first_award, 'source', 'milestone')
                
                success = email_service.send_points_notification_email(
                    to_email=user['email'],
                    fullname=user['fullname'],
                    points_awarded=points_awarded,
                    reason=reason
                )
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send points notification email to {user['email']}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Celery: Points notification emails sent: {sent_count} successful, {failed_count} failed")
        
        return {
            "status": "success",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_users": len(users_with_points)
        }
    except Exception as e:
        logger.error(f"❌ Celery: Points notification emails task failed: {e}")
        raise


# ============================================================================
# DOCUMENT PROCESSING TASKS (CPU-Intensive)
# ============================================================================

@cpu_intensive_task(
    name="app.celery_tasks.process_document_task",
    bind=True,
)
def process_document_task(self, document_path: str, options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Process document in background (CPU-intensive).
    
    Args:
        document_path: Path to document
        options: Processing options
        
    Returns:
        Dict with processing results
    """
    try:
        logger.info(f"📄 Celery: Processing document {document_path}")
        
        # Placeholder for document processing logic
        # Add your document processing here (OCR, parsing, etc.)
        
        return {
            "status": "success",
            "document": document_path,
            "message": "Document processed successfully",
        }
    except Exception as e:
        logger.error(f"❌ Celery: Document processing failed: {e}")
        raise


