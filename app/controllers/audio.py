"""Audio controller for handling TTS endpoints."""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
import os

from app.models.chat import AudioRequest, AudioResponse
from app.services.audio_service import AudioService
from app.dependencies import get_audio_service
from app.utils.error_handler import handle_http_errors, validate_file_exists

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/generate", response_model=AudioResponse, summary="Generate audio from text")
@handle_http_errors("Error generating audio")
async def generate_audio(
    request: AudioRequest,
    audio_service: AudioService = Depends(get_audio_service)
) -> AudioResponse:
    """
    Generate audio from text using TTS.
    
    - **text**: Text to convert to speech
    - **voice**: Optional voice selection
    """
    audio_file = await audio_service.generate_audio(
        text=request.text,
        voice=request.voice
    )
    
    # Get file size to estimate duration (async to avoid blocking)
    import asyncio
    file_size = await asyncio.to_thread(os.path.getsize, audio_file)
    estimated_duration = file_size / (24000 * 2)  # Rough estimate for 24kHz, 16-bit
    
    # Return relative URL path
    filename = os.path.basename(audio_file)
    audio_url = f"/audio/files/{filename}"
    
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

