"""
Service for integrating Celery background tasks with FastAPI.

This service provides async-friendly wrappers for Celery tasks, allowing
the FastAPI application to submit background tasks without blocking.
"""

import asyncio
from typing import Optional, Dict, Any
from celery.result import AsyncResult

from app.celery_tasks import (
    generate_tts_task,
    send_email_task,
    scrape_webpage_task,
    generate_response_task,
)
from app.config import logger


class CeleryService:
    """Service for managing Celery background tasks."""
    
    @staticmethod
    async def submit_tts_task(
        text: str,
        voice: Optional[str] = None,
        lang_code: Optional[str] = None,
        wait_for_result: bool = False,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Submit TTS generation task to Celery.
        
        Args:
            text: Text to convert to speech
            voice: Optional voice selection
            lang_code: Optional language code
            wait_for_result: Whether to wait for task completion
            timeout: Maximum time to wait if waiting for result
            
        Returns:
            Dict with task_id (and result if wait_for_result=True)
        """
        try:
            # Submit task to Celery (non-blocking)
            task = generate_tts_task.apply_async(
                args=[text],
                kwargs={"voice": voice, "lang_code": lang_code},
                queue="cpu_intensive"
            )
            
            logger.info(f"🎤 Submitted TTS task: {task.id} ({len(text)} chars)")
            
            if wait_for_result:
                # Wait for result asynchronously
                logger.info(f"⏳ Waiting for TTS task {task.id} (timeout: {timeout:.0f}s)")
                result = await asyncio.to_thread(task.get, timeout=timeout)
                logger.info(f"✅ TTS task {task.id} completed successfully")
                return {
                    "task_id": task.id,
                    "status": "completed",
                    "result": result
                }
            else:
                return {
                    "task_id": task.id,
                    "status": "pending",
                    "message": "Task submitted, processing in background"
                }
        except asyncio.TimeoutError as e:
            logger.error(f"⏱️ TTS task {task.id} timed out after {timeout:.0f}s")
            raise RuntimeError(f"TTS generation timed out after {timeout:.0f}s. Try with shorter text or increase timeout.") from e
        except Exception as e:
            logger.error(f"❌ TTS task submission failed: {e}")
            raise
    
    @staticmethod
    async def submit_email_task(
        recipient_email: str,
        subject: str,
        content: str,
        wait_for_result: bool = False
    ) -> Dict[str, Any]:
        """
        Submit email sending task to Celery.
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            content: Email content
            wait_for_result: Whether to wait for task completion
            
        Returns:
            Dict with task_id (and result if waiting)
        """
        task = send_email_task.apply_async(
            args=[recipient_email, subject, content],
            queue="io_bound"
        )
        
        logger.info(f"📧 Submitted email task: {task.id}")
        
        if wait_for_result:
            result = await asyncio.to_thread(task.get, timeout=30)
            return {"task_id": task.id, "status": "completed", "result": result}
        else:
            return {"task_id": task.id, "status": "pending"}
    
    @staticmethod
    async def submit_scraping_task(
        url: str,
        wait_for_result: bool = True,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """
        Submit web scraping task to Celery.
        
        Args:
            url: URL to scrape
            wait_for_result: Whether to wait for task completion
            timeout: Maximum time to wait
            
        Returns:
            Dict with task_id and scraped content
        """
        task = scrape_webpage_task.apply_async(
            args=[url],
            queue="io_bound"
        )
        
        logger.info(f"🌐 Submitted scraping task: {task.id}")
        
        if wait_for_result:
            result = await asyncio.to_thread(task.get, timeout=timeout)
            return {"task_id": task.id, "status": "completed", "result": result}
        else:
            return {"task_id": task.id, "status": "pending"}
    
    @staticmethod
    async def get_task_status(task_id: str) -> Dict[str, Any]:
        """
        Get the status of a Celery task.
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Dict with task status and result (if ready)
        """
        task = AsyncResult(task_id)
        
        status_info = {
            "task_id": task_id,
            "status": task.status,
            "ready": task.ready(),
            "successful": task.successful() if task.ready() else None,
        }
        
        if task.ready():
            if task.successful():
                status_info["result"] = task.result
            else:
                status_info["error"] = str(task.info)
        
        return status_info
    
    @staticmethod
    async def cancel_task(task_id: str) -> Dict[str, Any]:
        """
        Cancel a running Celery task.
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Dict with cancellation status
        """
        task = AsyncResult(task_id)
        task.revoke(terminate=True)
        
        logger.info(f"❌ Cancelled task: {task_id}")
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "Task cancellation requested"
        }
    
    @staticmethod
    async def check_celery_health() -> Dict[str, Any]:
        """
        Check Celery worker health.
        
        Returns:
            Dict with health status
        """
        try:
            from app.celery_app import celery_app
            
            # Ping workers
            inspect = celery_app.control.inspect()
            stats = await asyncio.to_thread(inspect.stats)
            active = await asyncio.to_thread(inspect.active)
            
            if stats:
                return {
                    "status": "healthy",
                    "workers": list(stats.keys()),
                    "active_tasks": sum(len(tasks) for tasks in (active or {}).values()),
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "No workers responding"
                }
        except Exception as e:
            logger.error(f"Celery health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global instance
celery_service = CeleryService()


