"""
Celery application configuration for background task processing.

This handles CPU-intensive and long-running tasks that should not block
the async event loop or web server processes.
"""

import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from kombu import Exchange, Queue

from app.config import logger

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Create Celery application
celery_app = Celery(
    "ai_agent",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.celery_tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=270,  # 4.5 minutes soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
    worker_disable_rate_limits=False,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=False,
    
    # Retry settings
    task_default_retry_delay=60,  # Retry after 1 minute
    task_max_retries=3,
    
    # Queue configuration
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("cpu_intensive", Exchange("cpu_intensive"), routing_key="cpu_intensive"),
        Queue("io_bound", Exchange("io_bound"), routing_key="io_bound"),
        Queue("priority", Exchange("priority"), routing_key="priority", priority=10),
    ),
    
    # Task routing
    task_routes={
        "app.celery_tasks.generate_tts_task": {"queue": "cpu_intensive"},
        "app.celery_tasks.send_email_task": {"queue": "io_bound"},
        "app.celery_tasks.scrape_webpage_task": {"queue": "io_bound"},
        "app.celery_tasks.process_document_task": {"queue": "cpu_intensive"},
        "app.celery_tasks.generate_response_task": {"queue": "cpu_intensive"},
    },
    
    # Beat scheduler (for periodic tasks)
    beat_schedule={
        "cleanup-old-audio-files": {
            "task": "app.celery_tasks.cleanup_old_files_task",
            "schedule": 86400.0,  # Every day
        },
        "health-check": {
            "task": "app.celery_tasks.health_check_task",
            "schedule": 86400.0,  # Every day
        },
    },
)


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Called when worker is ready."""
    logger.info("🚀 Celery worker is ready and waiting for tasks")


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Called when worker is shutting down."""
    logger.info("👋 Celery worker is shutting down")


# Task decorators for convenience
def cpu_intensive_task(**kwargs):
    """Decorator for CPU-intensive tasks."""
    kwargs.setdefault("queue", "cpu_intensive")
    kwargs.setdefault("time_limit", 300)
    return celery_app.task(**kwargs)


def io_bound_task(**kwargs):
    """Decorator for I/O-bound background tasks."""
    kwargs.setdefault("queue", "io_bound")
    kwargs.setdefault("time_limit", 120)
    return celery_app.task(**kwargs)


def priority_task(**kwargs):
    """Decorator for high-priority tasks."""
    kwargs.setdefault("queue", "priority")
    kwargs.setdefault("priority", 10)
    return celery_app.task(**kwargs)


if __name__ == "__main__":
    celery_app.start()


