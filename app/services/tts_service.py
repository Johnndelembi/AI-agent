"""
Text-to-Speech (TTS) service - Currently disabled.
TTS functionality has been removed in favor of email service.
"""

from typing import List
from app.config import logger

# TTS is disabled - email service is the focus
TTS_AVAILABLE = False


def clear_tts_cache():
    """Clear the TTS pipeline cache (no-op since TTS is disabled)."""
    pass


def generate_tts_audio(text: str, voice: str = None, lang_code: str = None) -> List[str]:
    """
    Generate TTS audio from text - Currently disabled.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (ignored)
        lang_code: Language code (ignored)
        
    Returns:
        Empty list (TTS is disabled)
    """
    logger.warning("TTS functionality is disabled. Email service is the focus.")
    return []


def prewarm_tts_pipeline():
    """Pre-warm the TTS pipeline - Currently disabled (no-op)."""
    pass


def get_available_voices() -> List[str]:
    """Get list of available TTS voices - Currently returns empty list."""
    return []
