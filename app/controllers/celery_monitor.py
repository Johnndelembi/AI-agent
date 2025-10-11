"""
Celery monitoring and management endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from app.services.celery_service import celery_service
from app.utils.error_handler import handle_http_errors, success_response

router = APIRouter(prefix="/celery", tags=["celery"])


@router.get("/health", summary="Celery health check")
@handle_http_errors("Error checking Celery health")
async def celery_health() -> Dict[str, Any]:
    """
    Check Celery worker health and status.
    
    Returns:
        Dict with Celery health status
    """
    health = await celery_service.check_celery_health()
    return success_response("Celery health check completed", data=health)


@router.get("/task/{task_id}", summary="Get task status")
@handle_http_errors("Error retrieving task status")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a Celery task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Dict with task status and result
    """
    status_info = await celery_service.get_task_status(task_id)
    return success_response(f"Task status: {status_info['status']}", data=status_info)


@router.delete("/task/{task_id}", summary="Cancel task")
@handle_http_errors("Error cancelling task")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """
    Cancel a running Celery task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Dict with cancellation status
    """
    result = await celery_service.cancel_task(task_id)
    return success_response("Task cancellation requested", data=result)


