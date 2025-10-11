"""
Text-to-Speech (TTS) service for audio generation using Kokoro TTS.
Handles audio generation, text processing, and pipeline management.
"""

import os
import re
import time
import warnings
from typing import List, Optional
from pathlib import Path

from app.config import (
    TTS_AVAILABLE,
    TTS_ENGINE,
    TTS_VOICE,
    TTS_LANG_CODE,
    AUDIO_OUTPUT_DIR,
    configure_kokoro_environment,
    logger
)

# Global TTS pipeline cache
_TTS_PIPELINE_CACHE = {}


def _strip_markdown_to_text(text: str) -> str:
    """
    Convert common Markdown to plain text for clean TTS.
    Removes emphasis markers, headings, code markers, links/images markup, list bullets, blockquotes, and extra whitespace.
    """
    if not text:
        return ""
    
    cleaned = text
    # Triple backtick code blocks -> keep content
    cleaned = re.sub(r"```(.*?)```", r"\1", cleaned, flags=re.DOTALL)
    # Inline code
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    # Images ![alt](url) -> alt
    cleaned = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", cleaned)
    # Links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    # Bold/italic **text**, __text__, *text*, _text_
    cleaned = re.sub(r"(\*\*|__)(.*?)\1", r"\2", cleaned)
    cleaned = re.sub(r"(\*|_)(.*?)\1", r"\2", cleaned)
    # Headings #### Title -> Title
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    # Blockquotes > quote -> quote
    cleaned = re.sub(r"^\s*>\s?", "", cleaned, flags=re.MULTILINE)
    # Lists (-, *, +, 1.) -> strip markers
    cleaned = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", cleaned, flags=re.MULTILINE)
    # Horizontal rules
    cleaned = re.sub(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", "", cleaned, flags=re.MULTILINE)
    # Remove any remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _split_text_for_tts(full_text: str, max_chars_per_chunk: int = 800) -> List[str]:
    """
    Split long text into sentence-aware chunks not exceeding max_chars_per_chunk.
    Keeps punctuation boundaries where possible to avoid mid-sentence cuts.
    """
    text = full_text.strip()
    if len(text) <= max_chars_per_chunk:
        return [text]
    
    # Split on sentence enders while preserving delimiters
    sentences = re.split(r"(?<=[\.!?])\s+", text)
    chunks = []
    current = []
    current_len = 0
    
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        if current_len + len(s) + (1 if current else 0) <= max_chars_per_chunk:
            current.append(s)
            current_len += len(s) + (1 if current_len > 0 else 0)
        else:
            if current:
                chunks.append(" ".join(current))
            # If a single sentence is longer than max, hard-split it
            if len(s) > max_chars_per_chunk:
                for i in range(0, len(s), max_chars_per_chunk):
                    part = s[i:i+max_chars_per_chunk]
                    chunks.append(part)
                current = []
                current_len = 0
            else:
                current = [s]
                current_len = len(s)
    
    if current:
        chunks.append(" ".join(current))
    return chunks


def get_tts_pipeline(lang_code: str = None):
    """Get or create TTS pipeline with caching for better performance."""
    global _TTS_PIPELINE_CACHE
    
    if not TTS_AVAILABLE or TTS_ENGINE != "kokoro":
        return None
    
    try:
        lang_to_use = lang_code or TTS_LANG_CODE
        cache_key = f"pipeline_{lang_to_use}"
        
        if cache_key not in _TTS_PIPELINE_CACHE:
            logger.info(f"🔧 Initializing Kokoro TTS pipeline for language code: {lang_to_use}")
            
            # Configure environment
            configure_kokoro_environment()
            
            # Import and create pipeline
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from kokoro import KPipeline
                _TTS_PIPELINE_CACHE[cache_key] = KPipeline(lang_code=lang_to_use)
            
            if _TTS_PIPELINE_CACHE[cache_key]:
                logger.info("✅ Kokoro TTS pipeline initialized successfully")
            else:
                logger.error("❌ Kokoro pipeline failed to initialize")
                return None
        
        return _TTS_PIPELINE_CACHE[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to initialize Kokoro pipeline: {e}")
        return None


def generate_tts_audio(text: str, voice: str = None, lang_code: str = None) -> List[str]:
    """
    Generate TTS audio from text and return list of file paths.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (optional, defaults to TTS_VOICE)
        lang_code: Language code (optional, defaults to TTS_LANG_CODE)
        
    Returns:
        List of audio file paths (usually one file)
    """
    if not TTS_AVAILABLE:
        logger.warning("TTS not available")
        return []
    
    try:
        # Generate unique filename with timestamp
        timestamp = int(time.time())
        filename = f'response_{timestamp}.wav'
        filepath = str(AUDIO_OUTPUT_DIR / filename)
        
        # Generate audio using Kokoro
        if TTS_ENGINE == "kokoro":
            result = _generate_kokoro_audio(text, voice, lang_code, filepath)
            return result
        else:
            logger.error(f"TTS engine not supported: {TTS_ENGINE}")
            return []
            
    except Exception as e:
        logger.error(f"Error generating TTS audio: {e}")
        return []


def _generate_kokoro_audio(text: str, voice: str, lang_code: str, filepath: str) -> List[str]:
    """
    Generate audio using Kokoro TTS with improved long-text handling.
    Synthesizes long inputs in sequential chunks and concatenates into a single WAV.
    """
    try:
        # Use provided voice/lang_code or defaults
        voice_to_use = voice or TTS_VOICE
        lang_to_use = lang_code or TTS_LANG_CODE
        
        # Get cached pipeline
        pipeline = get_tts_pipeline(lang_to_use)
        if not pipeline:
            logger.error("Kokoro pipeline not available")
            return []
        
        # Sanitize markdown so audio doesn't read asterisks/hashtags
        sanitized = _strip_markdown_to_text(text)
        logger.info(f"🎵 Generating Kokoro TTS audio for {len(sanitized)} characters with voice '{voice_to_use}'...")
        
        # Configure environment
        configure_kokoro_environment()
        
        import torch
        torch.set_warn_always(False)
        
        import numpy as np
        import soundfile as sf
        
        # Split text into chunks and synthesize sequentially
        chunks = _split_text_for_tts(sanitized, max_chars_per_chunk=900)
        logger.info(f"🧩 TTS will synthesize in {len(chunks)} chunk(s)")
        
        all_segments = []
        total_segments = 0
        first_segment_logged = False
        
        for ci, chunk_text in enumerate(chunks, start=1):
            logger.info(f"🗣️ Synthesizing chunk {ci}/{len(chunks)} ({len(chunk_text)} chars)")
            generator = pipeline(chunk_text, voice=voice_to_use)
            for i, (gs, ps, audio) in enumerate(generator):
                all_segments.append(audio)
                total_segments += 1
                if not first_segment_logged:
                    first_segment_logged = True
                    logger.info("✅ Model loaded, processing audio segments...")
                if total_segments % 5 == 0:
                    logger.info(f"📊 TTS progress: {total_segments} segments accumulated")
        
        if not all_segments:
            logger.warning("No audio segments generated")
            return []
        
        concatenated_audio = np.concatenate(all_segments)
        sf.write(filepath, concatenated_audio, 24000)
        logger.info(f"🎉 Kokoro TTS audio saved: {filepath}")
        
        _cleanup_old_audio_files()
        return [filepath]
        
    except Exception as e:
        logger.error(f"❌ Error generating Kokoro TTS audio: {e}")
        return []


def _cleanup_old_audio_files():
    """Clean up old audio files (keep only last 5 for better performance)."""
    try:
        audio_files = [f for f in AUDIO_OUTPUT_DIR.iterdir() if f.name.startswith('response_') and f.suffix == '.wav']
        audio_files.sort(key=lambda x: x.stat().st_ctime, reverse=True)
        
        # Keep only the 5 most recent files
        for old_file in audio_files[5:]:
            old_file.unlink()
            logger.info(f"Cleaned up old audio file: {old_file.name}")
    except Exception as e:
        logger.warning(f"Could not clean up old audio files: {e}")


def get_available_voices() -> List[str]:
    """Get list of available Kokoro TTS voices."""
    from ..config import AVAILABLE_VOICES
    return AVAILABLE_VOICES

