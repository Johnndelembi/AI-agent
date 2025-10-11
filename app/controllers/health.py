"""Health check controller."""
from fastapi import APIRouter, Depends

from app.models.chat import HealthResponse
from app.services.chat_service import ChatService
from app.services.audio_service import AudioService
from app.dependencies import get_chat_service, get_audio_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(
    chat_service: ChatService = Depends(get_chat_service),
    audio_service: AudioService = Depends(get_audio_service)
) -> HealthResponse:
    """
    Check the health status of the API and its services.
    """
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        services={
            "chat": await chat_service.is_healthy(),
            "audio": await audio_service.is_available(),
        }
    )


@router.get("/", summary="Root endpoint")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": "AI Agent API",
        "version": "2.0.0",
        "description": "FastAPI-based conversational AI assistant",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_schema": "/openapi.json"
        },
        "endpoints": {
            "health": "/health",
            "chat": "/chat/message",
            "audio": "/audio/generate"
        }
    }

