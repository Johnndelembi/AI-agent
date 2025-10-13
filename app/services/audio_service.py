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
        
        Runs TTS generation in a background thread to avoid blocking the async event loop.
        This is simpler and faster than using Celery since we need to wait for the result anyway.
        
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
        
        # Direct generation in background thread for ALL text lengths
        # This is simpler than Celery and avoids the overhead of task queuing
        logger.info(f"🎤 Generating TTS audio ({len(text)} chars)")
        
        from app.services.tts_service import generate_tts_audio, clear_tts_cache
        import gc
        
        try:
            # Run TTS in background thread (non-blocking for event loop)
            audio_files = await asyncio.to_thread(generate_tts_audio, text, voice)
            
            # Clean up memory after generation
            await asyncio.to_thread(clear_tts_cache)
            await asyncio.to_thread(gc.collect)
            logger.info(f"🧹 Memory cleanup completed")
            
            if audio_files and len(audio_files) > 0:
                return audio_files[0]
            raise RuntimeError("Failed to generate audio file")
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            # Clean up even on error
            try:
                await asyncio.to_thread(clear_tts_cache)
                await asyncio.to_thread(gc.collect)
            except:
                pass
            raise
    
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

