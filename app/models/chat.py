"""Chat-related request and response models."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat messages."""
    message: str = Field(..., description="The user's message to the chatbot")
    thread_id: Optional[str] = Field(default="default", description="Thread ID for conversation context")


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str = Field(..., description="The chatbot's response")
    thread_id: str = Field(..., description="Thread ID used for this conversation")


class ChatHistoryRequest(BaseModel):
    """Request model for retrieving chat history."""
    thread_id: str = Field(default="default", description="Thread ID to retrieve history for")


class ChatHistoryResponse(BaseModel):
    """Response model for chat history."""
    thread_id: str = Field(..., description="Thread ID for this history")
    messages: List[Dict[str, Any]] = Field(..., description="List of messages in the conversation")


class AudioRequest(BaseModel):
    """Request model for generating audio."""
    text: str = Field(..., description="Text to convert to speech")
    voice: Optional[str] = Field(default=None, description="Voice to use for TTS")


class AudioResponse(BaseModel):
    """Response model for audio generation."""
    audio_url: str = Field(..., description="URL to the generated audio file")
    duration: Optional[float] = Field(None, description="Duration of the audio in seconds")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    services: Dict[str, bool] = Field(..., description="Status of dependent services")

