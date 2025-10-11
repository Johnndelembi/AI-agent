"""Audio service for handling TTS functionality."""
import asyncio
import os
from typing import Optional

from app.config import TTS_AVAILABLE, logger


class AudioService:
    """Service for managing audio generation and TTS."""
    
    def __init__(self):
        """Initialize the audio service."""
        self._audio_output_dir = "audio_output"
        self._use_celery = os.getenv("USE_CELERY_FOR_TTS", "true").lower() == "true"
        
        # Ensure audio output directory exists
        os.makedirs(self._audio_output_dir, exist_ok=True)
    
    async def generate_audio(self, text: str, voice: Optional[str] = None) -> str:
        """
        Generate audio from text using TTS.
        
        For long texts or when Celery is enabled, uses Celery for background processing.
        For short texts, generates directly.
        
        Args:
            text: Text to convert to speech
            voice: Optional voice selection
            
        Returns:
            Path to the generated audio file
            
        Raises:
            RuntimeError: If TTS is not available
        """
        if not TTS_AVAILABLE:
            raise RuntimeError("TTS functionality is not available")
        
        # Use Celery for long texts (CPU-intensive) if available
        if self._use_celery and len(text) > 500:
            try:
                from app.services.celery_service import celery_service
                
                logger.info(f"📤 Using Celery for TTS generation ({len(text)} chars)")
                
                # Submit to Celery and wait for result
                result = await celery_service.submit_tts_task(
                    text=text,
                    voice=voice,
                    wait_for_result=True,
                    timeout=60.0
                )
                
                if result["status"] == "completed" and result["result"]["audio_files"]:
                    return result["result"]["audio_files"][0]
                else:
                    raise RuntimeError("Celery TTS generation failed")
            except Exception as e:
                logger.warning(f"Celery TTS failed, falling back to direct generation: {e}")
                # Fall through to direct generation
        
        # Direct generation (for short texts or fallback)
        logger.info(f"🎤 Direct TTS generation ({len(text)} chars)")
        from app.services.tts_service import generate_tts_audio
        
        audio_files = await asyncio.to_thread(generate_tts_audio, text, voice)
        
        if audio_files and len(audio_files) > 0:
            return audio_files[0]
        raise RuntimeError("Failed to generate audio file")
    
    async def get_audio_file(self, filename: str) -> str:
        """
        Get the full path to an audio file.
        
        Args:
            filename: Name of the audio file
            
        Returns:
            Full path to the audio file
        """
        return os.path.join(self._audio_output_dir, filename)
    
    async def is_available(self) -> bool:
        """Check if TTS service is available."""
        return TTS_AVAILABLE
    
    async def shutdown(self) -> None:
        """Shutdown the audio service and cleanup resources."""
        # No resources to cleanup with asyncio.to_thread
        pass

