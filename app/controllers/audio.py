"""Audio controller for handling TTS endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import os

from app.models.chat import AudioRequest, AudioResponse
from app.models.auth import User
from app.services.audio_service import AudioService
from app.services.chat_service import ChatService
from app.dependencies import get_audio_service, get_chat_service
from app.utils.auth_utils import get_current_user
from app.utils.error_handler import handle_http_errors, validate_file_exists

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/generate", response_model=AudioResponse, summary="Generate audio from text or message")
@handle_http_errors("Error generating audio")
async def generate_audio(
    request: AudioRequest,
    current_user: User = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service),
    chat_service: ChatService = Depends(get_chat_service)
) -> AudioResponse:
    """
    Generate audio from text or a specific message using TTS.
    
    - **text**: Text to convert to speech (required if message_id not provided)
    - **message_id**: Message ID to generate audio for (alternative to text)
    - **thread_id**: Thread ID (required if using message_id)
    - **voice**: Optional voice selection
    """
    text_to_speak = request.text
    
    # If message_id is provided, retrieve the message content from MongoDB
    if request.message_id:
        if not request.thread_id:
            raise HTTPException(
                status_code=400,
                detail="thread_id is required when using message_id"
            )
        
        # Retrieve the message from MongoDB
        message = await chat_service.get_message(request.thread_id, request.message_id, current_user.id)
        
        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"Message not found: {request.message_id} in thread {request.thread_id}"
            )
        
        # Use the message content for TTS
        text_to_speak = message['content']
        
        # Check if audio was already generated
        if message.get('audio_generated') and message.get('audio_url'):
            return AudioResponse(
                audio_url=message['audio_url'],
                duration=None
            )
    
    # Validate that we have text to speak
    if not text_to_speak:
        raise HTTPException(
            status_code=400,
            detail="Either text or message_id must be provided"
        )
    
    # Generate audio
    audio_file = await audio_service.generate_audio(
        text=text_to_speak,
        voice=request.voice
    )
    
    # Get file size to estimate duration (async to avoid blocking)
    import asyncio
    file_size = await asyncio.to_thread(os.path.getsize, audio_file)
    estimated_duration = file_size / (24000 * 2)  # Rough estimate for 24kHz, 16-bit
    
    # Return relative URL path
    filename = os.path.basename(audio_file)
    audio_url = f"/audio/files/{filename}"
    
    # If this was for a specific message, update the message in MongoDB
    if request.message_id and request.thread_id:
        await chat_service.update_message_audio(
            request.thread_id,
            request.message_id,
            audio_url,
            current_user.id
        )
    
    return AudioResponse(
        audio_url=audio_url,
        duration=estimated_duration
    )


@router.get("/files/{filename}", summary="Download audio file")
@handle_http_errors("Error retrieving audio file")
async def get_audio_file(
    filename: str,
    audio_service: AudioService = Depends(get_audio_service)
) -> FileResponse:
    """
    Download a generated audio file.
    
    - **filename**: Name of the audio file to download
    """
    audio_file = await audio_service.get_audio_file(filename)
    validate_file_exists(audio_file, f"Audio file not found: {filename}")
    
    return FileResponse(
        audio_file,
        media_type="audio/wav",
        filename=filename
    )


@router.get("/available", summary="Check if TTS is available")
async def check_tts_available(
    audio_service: AudioService = Depends(get_audio_service)
) -> dict:
    """Check if TTS service is available."""
    is_available = await audio_service.is_available()
    return {
        "available": is_available,
        "message": "TTS service is available" if is_available else "TTS service is not available"
    }

