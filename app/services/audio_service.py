"""Audio service for handling TTS functionality."""
import asyncio
import os
from typing import Optional

from app.config import logger
from app.services.gridfs_service import gridfs_service


class AudioService:
    """Service for managing audio generation and TTS."""
    
    def __init__(self):
        """Initialize the audio service."""
        self._use_celery = os.getenv("USE_CELERY_FOR_TTS", "true").lower() == "true"
    
    async def generate_audio(self, text: str, voice: Optional[str] = None) -> str:
        """
        Generate audio from text using TTS and save to GridFS.
        
        Runs TTS generation in a background thread to avoid blocking the async event loop.
        This is simpler and faster than using Celery since we need to wait for the result anyway.
        
        Args:
            text: Text to convert to speech
            voice: Optional voice selection
            
        Returns:
            GridFS file_id (as string) of the generated audio file
            
        Raises:
            RuntimeError: If TTS is not available
        """
        # TTS functionality is disabled - email service is the focus
        raise RuntimeError("TTS functionality is not available. Email service is the focus.")
        
        # Direct generation in background thread for ALL text lengths
        # This is simpler than Celery and avoids the overhead of task queuing
        logger.info(f"🎤 Generating TTS audio ({len(text)} chars)")
        
        from app.services.tts_service import generate_tts_audio, clear_tts_cache
        import gc
        
        try:
            # Run TTS in background thread (non-blocking for event loop)
            # This returns a temporary file path
            audio_files = await asyncio.to_thread(generate_tts_audio, text, voice)
            
            if not audio_files or len(audio_files) == 0:
                # This should rarely happen now since we raise exceptions instead of returning []
                raise RuntimeError("TTS generation returned no audio files. Check logs for details.")
            
            # Read the generated audio file and save to GridFS
            audio_file_path = audio_files[0]
            filename = os.path.basename(audio_file_path)
            
            # Read audio file content
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
            
            # Save to GridFS
            file_id = await asyncio.to_thread(
                gridfs_service.save_audio_file,
                audio_data,
                filename,
                metadata={'voice': voice, 'text_length': len(text)}
            )
            
            # Clean up temporary file
            try:
                os.remove(audio_file_path)
            except:
                pass
            
            # Clean up memory after generation
            await asyncio.to_thread(clear_tts_cache)
            await asyncio.to_thread(gc.collect)
            logger.info(f"🧹 Memory cleanup completed")
            
            return file_id
        except Exception as e:
            # Log the full error with traceback for debugging
            logger.error(f"TTS generation failed: {e}", exc_info=True)
            # Clean up even on error
            try:
                await asyncio.to_thread(clear_tts_cache)
                await asyncio.to_thread(gc.collect)
            except:
                pass
            # Re-raise with more context if it's a generic RuntimeError
            if isinstance(e, RuntimeError) and "Failed to generate" in str(e):
                raise RuntimeError(f"Failed to generate audio file: {e}") from e
            raise
    
    async def get_audio_file(self, file_id: str) -> bytes:
        """
        Get audio file data from GridFS.
        
        Args:
            file_id: GridFS file ID (as string)
            
        Returns:
            Binary audio data
        """
        audio_data = await asyncio.to_thread(gridfs_service.get_audio_file, file_id)
        if audio_data is None:
            raise FileNotFoundError(f"Audio file not found: {file_id}")
        return audio_data
    
    async def is_available(self) -> bool:
        """Check if TTS service is available."""
        return False  # TTS is disabled - email service is the focus
    
    async def file_exists(self, file_id: str) -> bool:
        """
        Check if audio file exists in GridFS.
        
        Args:
            file_id: GridFS file ID (as string)
            
        Returns:
            True if exists, False otherwise
        """
        return await asyncio.to_thread(gridfs_service.file_exists, file_id)
    
    async def shutdown(self) -> None:
        """Shutdown the audio service and cleanup resources."""
        # No resources to cleanup with asyncio.to_thread
        pass

