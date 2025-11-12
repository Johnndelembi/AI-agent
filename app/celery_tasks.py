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


