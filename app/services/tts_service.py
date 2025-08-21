import os
import time
import warnings
import logging
from typing import List, Optional
import numpy as np
import soundfile as sf
import re

from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Configure PyTorch to reduce warnings
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['PYTORCH_DISABLE_WARNINGS'] = '1'
os.environ['TORCH_WARN_ONCE'] = '0'
os.environ['PYTORCH_WARN_ONCE'] = '0'
warnings.filterwarnings("ignore")

# Global TTS pipeline cache (for Kokoro only)
_TTS_PIPELINE_CACHE = {}

class TTSService:
    """Text-to-Speech service using Kokoro engine"""
    
    def __init__(self):
        self.tts_available = self._check_tts_availability()
        self.tts_engine = "kokoro" if self.tts_available else None
        self.voice = settings.tts_voice
        self.lang_code = settings.tts_lang_code
        
        if self.tts_available:
            logger.info("Kokoro TTS libraries loaded successfully (high-quality engine)")
        else:
            logger.warning("No TTS libraries available. Audio generation will be disabled.")
    
    def _check_tts_availability(self) -> bool:
        """Check if TTS dependencies are available"""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import torch
                torch.set_warn_always(False)
                
                from kokoro import KPipeline
                import soundfile as sf
            
            return True
        except ImportError as e:
            logger.warning(f"Kokoro TTS not available: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error loading Kokoro TTS: {e}")
            return False
    
    def _strip_markdown_to_text(self, text: str) -> str:
        """Convert common Markdown to plain text for clean TTS"""
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
    
    def _split_text_for_tts(self, full_text: str, max_chars_per_chunk: int = 800) -> List[str]:
        """Split long text into sentence-aware chunks"""
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
    
    def get_tts_pipeline(self, lang_code: Optional[str] = None):
        """Get or create TTS pipeline with caching"""
        global _TTS_PIPELINE_CACHE
        
        if self.tts_engine != "kokoro":
            return None
        
        try:
            # Import and use the proper Kokoro configuration
            from kokoro_local_config import create_kokoro_pipeline
            
            lang_to_use = lang_code or self.lang_code
            cache_key = f"pipeline_{lang_to_use}"
            
            if cache_key not in _TTS_PIPELINE_CACHE:
                logger.info(f"🔧 Initializing Kokoro TTS pipeline for language code: {lang_to_use}")
                
                # Create pipeline with local-first approach
                try:
                    _TTS_PIPELINE_CACHE[cache_key] = create_kokoro_pipeline(lang_to_use, use_local_only=True)
                    if _TTS_PIPELINE_CACHE[cache_key]:
                        logger.info("✅ Kokoro TTS pipeline initialized successfully")
                    else:
                        logger.error("❌ Kokoro pipeline failed to initialize")
                        return None
                except Exception as e:
                    logger.error(f"Failed to initialize Kokoro pipeline: {e}")
                    return None
            
            return _TTS_PIPELINE_CACHE[cache_key]
        except ImportError:
            logger.warning("Kokoro configuration not available")
            return None
    
    def generate_audio(self, text: str, voice: Optional[str] = None, lang_code: Optional[str] = None) -> List[str]:
        """Generate TTS audio from text and return list of file paths"""
        if not self.tts_available:
            return []
        
        try:
            # Create output directory
            output_dir = os.path.join(os.getcwd(), settings.audio_output_dir)
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate unique filename with timestamp
            timestamp = int(time.time())
            filename = f'response_{timestamp}.wav'
            filepath = os.path.join(output_dir, filename)
            
            # Use Kokoro TTS only
            if self.tts_engine == "kokoro":
                result = self._generate_kokoro_audio(text, voice, lang_code, filepath)
                return result
            else:
                logger.error(f"Kokoro TTS not available. Engine: {self.tts_engine}")
                return []
                
        except Exception as e:
            logger.error(f"Error generating TTS audio: {e}")
            return []
    
    def _generate_kokoro_audio(self, text: str, voice: Optional[str], lang_code: Optional[str], filepath: str) -> List[str]:
        """Generate audio using Kokoro TTS with improved long-text handling"""
        try:
            # Use provided voice/lang_code or defaults
            voice_to_use = voice or self.voice
            lang_to_use = lang_code or self.lang_code
            
            # Get cached pipeline
            pipeline = self.get_tts_pipeline(lang_to_use)
            if not pipeline:
                logger.error("Kokoro pipeline not available")
                return []
            
            # Sanitize markdown so audio doesn't read asterisks/hashtags
            sanitized = self._strip_markdown_to_text(text)
            logger.info(f"🎵 Generating Kokoro TTS audio for {len(sanitized)} characters with voice '{voice_to_use}'...")
            
            import torch
            torch.set_warn_always(False)
            
            # Split text into chunks and synthesize sequentially
            chunks = self._split_text_for_tts(sanitized, max_chars_per_chunk=900)
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
            
            self._cleanup_old_audio_files()
            return [filepath]
            
        except Exception as e:
            logger.error(f"❌ Error generating Kokoro TTS audio: {e}")
            return []
    
    def _cleanup_old_audio_files(self):
        """Clean up old audio files (keep only last 5 for better performance)"""
        try:
            output_dir = os.path.join(os.getcwd(), settings.audio_output_dir)
            
            audio_files = [f for f in os.listdir(output_dir) if f.startswith('response_') and f.endswith('.wav')]
            audio_files.sort(key=lambda x: os.path.getctime(os.path.join(output_dir, x)), reverse=True)
            
            # Keep only the 5 most recent files
            for old_file in audio_files[5:]:
                old_filepath = os.path.join(output_dir, old_file)
                os.remove(old_filepath)
                logger.info(f"Cleaned up old audio file: {old_file}")
        except Exception as e:
            logger.warning(f"Could not clean up old audio files: {e}")

# Global TTS service instance
tts_service = TTSService() 