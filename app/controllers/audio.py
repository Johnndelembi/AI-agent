"""Audio controller for handling TTS endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
import os
import asyncio
from fastapi.responses import Response
from mongoengine.connection import get_db
from gridfs import GridFS

from app.models.chat import AudioRequest, AudioResponse, TTSVoiceRequest, TTSVoiceResponse, VoiceInfo
from app.models.auth import User
from app.services.audio_service import AudioService
from app.services.chat_service import ChatService
from app.dependencies import get_audio_service, get_chat_service
from app.utils.auth_utils import get_current_user
from app.utils.error_handler import handle_http_errors
from app.config import AVAILABLE_VOICES, VOICE_DESCRIPTIONS, settings, logger

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
    message_found = False  # Track if message was successfully found
    
    # If message_id is provided, retrieve the message content from MongoDB
    if request.message_id:
        if not request.thread_id:
            raise HTTPException(
                status_code=400,
                detail="thread_id is required when using message_id"
            )
        
        # Retrieve the message from MongoDB
        message = await chat_service.get_message(request.thread_id, request.message_id, str(current_user.id))
        
        if not message:
            # If text is also provided, fall back to using text instead of failing
            if request.text:
                # Use the provided text as fallback
                text_to_speak = request.text
            else:
                # Check if conversation exists to provide better error message
                from app.models.database import Conversation
                conversation = await asyncio.to_thread(
                    lambda: Conversation.objects(thread_id=request.thread_id, user_id=str(current_user.id)).first()
                )
                
                if not conversation:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Conversation not found for thread_id: {request.thread_id}. Please ensure the conversation exists before generating audio for a message, or provide 'text' to generate audio directly."
                    )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Message not found: {request.message_id} in thread {request.thread_id}. Provide 'text' to generate audio directly."
                    )
        else:
            # Use the message content for TTS
            text_to_speak = message['content']
            message_found = True  # Mark that message was found
            
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
    
    # Use provided voice, user's stored preference, or default
    # Reload user to ensure we have the latest tts_voice from database
    await asyncio.to_thread(current_user.reload)
    voice_to_use = current_user.tts_voice
    
    logger.info(f"Using voice '{voice_to_use}' for user {current_user.email} (request.voice={request.voice}, user.tts_voice={current_user.tts_voice}, default={settings.TTS_VOICE})")
    
    # Generate audio and save to GridFS
    file_id = await audio_service.generate_audio(
        text=text_to_speak,
        voice=voice_to_use
    )
    
    # Get audio data to estimate duration
    audio_data = await audio_service.get_audio_file(file_id)
    file_size = len(audio_data)
    estimated_duration = file_size / (24000 * 2)  # Rough estimate for 24kHz, 16-bit
    
    # Return GridFS file_id as the audio_url
    audio_url = file_id
    
    # If this was for a specific message and it was found, update the message in MongoDB
    if request.message_id and request.thread_id and message_found:
        await chat_service.update_message_audio(
            request.thread_id,
            request.message_id,
            audio_url,
            str(current_user.id)
        )
    
    return AudioResponse(
        audio_url=audio_url,
        duration=estimated_duration
    )


@router.get("/files/{file_id}", summary="Download audio file")
@handle_http_errors("Error retrieving audio file")
async def get_audio_file(
    file_id: str,
    audio_service: AudioService = Depends(get_audio_service)
) -> Response:
    """
    Download a generated audio file from GridFS.
    
    - **file_id**: GridFS file ID of the audio file to download
    """
    
    # Get audio data from GridFS
    try:
        audio_data = await audio_service.get_audio_file(file_id)
        
        # Get filename from GridFS metadata if available
        from app.services.gridfs_service import gridfs_service
        from bson import ObjectId
        try:
            db = get_db()
            fs = GridFS(db)
            grid_file = fs.get(ObjectId(file_id))
            filename = grid_file.filename or f"audio_{file_id}.wav"
        except:
            filename = f"audio_{file_id}.wav"
        
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Audio file not found: {file_id}"
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


@router.post("/voice/select", response_model=TTSVoiceResponse, summary="Select TTS voice")
@handle_http_errors("Error selecting TTS voice")
async def select_tts_voice(
    request: TTSVoiceRequest,
    current_user: User = Depends(get_current_user)
) -> TTSVoiceResponse:
    """
    Select the TTS voice to use for audio generation.
    
    - **voice**: Voice to use for TTS (must be from available voices)
    
    Requires: Valid JWT token in Authorization header.
    """
    # Validate voice is in available voices
    if request.voice not in AVAILABLE_VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice '{request.voice}'. Available voices: {', '.join(AVAILABLE_VOICES)}"
        )
    
    # Update user's TTS voice preference in database
    current_user.tts_voice = request.voice
    await asyncio.to_thread(current_user.save)
    
    # Reload user to ensure we have the latest data
    await asyncio.to_thread(current_user.reload)
    
    logger.info(f"TTS voice updated to: {request.voice} by user {current_user.email} (saved to DB)")
    
    # Build voice info list
    available_voices_info = [
        VoiceInfo(code=voice, description=VOICE_DESCRIPTIONS.get(voice, "Unknown voice"))
        for voice in AVAILABLE_VOICES
    ]
    
    return TTSVoiceResponse(
        current_voice=request.voice,
        current_voice_description=VOICE_DESCRIPTIONS.get(request.voice, "Unknown voice"),
        available_voices=available_voices_info
    )


@router.get("/voice/current", response_model=TTSVoiceResponse, summary="Get current TTS voice")
async def get_current_tts_voice(
    current_user: User = Depends(get_current_user)
) -> TTSVoiceResponse:
    """
    Get the currently selected TTS voice and list of available voices with descriptions.
    
    Requires: Valid JWT token in Authorization header.
    """
    # Get user's stored voice preference, or fall back to default
    user_voice = current_user.tts_voice or settings.TTS_VOICE
    
    # Build voice info list
    available_voices_info = [
        VoiceInfo(code=voice, description=VOICE_DESCRIPTIONS.get(voice, "Unknown voice"))
        for voice in AVAILABLE_VOICES
    ]
    
    return TTSVoiceResponse(
        current_voice=user_voice,
        current_voice_description=VOICE_DESCRIPTIONS.get(user_voice, "Unknown voice"),
        available_voices=available_voices_info
    )

