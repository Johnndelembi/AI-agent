import os
import logging
import subprocess
import sys

from PIL.TiffImagePlugin import TRANSFERFUNCTION

# Configure logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure PyTorch to reduce warnings
import warnings
import os

# Set PyTorch environment variables to reduce warnings BEFORE importing torch
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['PYTORCH_DISABLE_WARNINGS'] = '1'
os.environ['TORCH_WARN_ONCE'] = '0'
os.environ['PYTORCH_WARN_ONCE'] = '0'

# Suppress all warnings at the system level
warnings.filterwarnings("ignore")

# Try to import TTS dependencies with proper error handling
try:
    # Import torch with warnings suppressed
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import torch
        torch.set_warn_always(False)
    
    # Import kokoro with warnings suppressed
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from kokoro import KPipeline
        import soundfile as sf
    
    TTS_AVAILABLE = True
    TTS_ENGINE = "kokoro"
    logger.info("Kokoro TTS libraries loaded successfully (high-quality engine)")
except ImportError as e:
    TTS_AVAILABLE = False
    logger.warning(f"Kokoro TTS not available: {e}")
    logger.warning("No TTS libraries available. Audio generation will be disabled.")
except Exception as e:
    TTS_AVAILABLE = False
    logger.warning(f"Error loading Kokoro TTS: {e}. Audio generation will be disabled.")

# Now import other dependencies
from typing import Annotated
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
import json
from langgraph.types import Command, interrupt
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
import requests
from bs4 import BeautifulSoup
import feedparser
import re
from datetime import datetime

# Load environment variables from .env file
load_dotenv()








# === CONFIGURATION ===
MODEL = os.getenv("CHATBOT_MODEL", "openai:gpt-4")
API_KEY = os.getenv("CHATBOT_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

def init_chat_model(model_name: str, model_provider: str = "openai"):
    """Initialize chat model based on provider"""
    if model_provider == "openai":
        return ChatOpenAI(model=model_name.replace("openai:", ""))
    elif model_provider == "anthropic":
        return ChatAnthropic(model=model_name.replace("anthropic:", ""))
    elif model_provider == "google_genai":
        return ChatGoogleGenerativeAI(model=model_name.replace("google:", ""))
    else:
        # Default to OpenAI
        return ChatOpenAI(model=model_name.replace("openai:", ""))

# TTS Configuration
TTS_VOICE = os.getenv("TTS_VOICE", "af_heart")  # Default voice
TTS_LANG_CODE = os.getenv("TTS_LANG_CODE", "b")  # Default language code

# Validate required environment variables
IS_DEV = os.getenv("ENV", "production").lower() == "dev"
if not API_KEY:
    if IS_DEV:
        logger.warning("CHATBOT_API_KEY environment variable is missing (dev mode)")
    else:
        raise ValueError("CHATBOT_API_KEY environment variable is required")
if not TAVILY_API_KEY:
    if IS_DEV:
        logger.warning("TAVILY_API_KEY environment variable is missing (dev mode)")
    else:
        raise ValueError("TAVILY_API_KEY environment variable is required")

# Set the correct environment variable for the selected model
if MODEL.startswith("openai:"):
    os.environ["OPENAI_API_KEY"] = API_KEY
    model_provider = "openai"
elif MODEL.startswith("anthropic:"):
    os.environ["ANTHROPIC_API_KEY"] = API_KEY
    model_provider = "anthropic"
elif MODEL.startswith("google:"):
    os.environ["GOOGLE_API_KEY"] = API_KEY
    model_provider = "google_genai"
else:
    # Default fallback to OpenAI - ensure API key is set
    os.environ["OPENAI_API_KEY"] = API_KEY
    model_provider = "openai"
    logger.warning(f"Unknown model prefix for {MODEL}, using OpenAI as default provider")

# Set Tavily API key
os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

logger.info(f"Using model: {MODEL}")
logger.info(f"TTS Available: {TTS_AVAILABLE}")
# === END CONFIGURATION ===













# === START TTS UTILITIES ===
# Global TTS pipeline cache (for Kokoro only)
_TTS_PIPELINE_CACHE = {}

def _strip_markdown_to_text(text: str) -> str:
    """Convert common Markdown to plain text for clean TTS.
    Removes emphasis markers, headings, code markers, links/ images markup, list bullets, blockquotes, and extra whitespace.
    """
    import re
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

def _split_text_for_tts(full_text: str, max_chars_per_chunk: int = 800) -> list:
    """Split long text into sentence-aware chunks not exceeding max_chars_per_chunk.
    Keeps punctuation boundaries where possible to avoid mid-sentence cuts.
    """
    import re
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
    """Get or create TTS pipeline with caching for better performance (Kokoro only)"""
    global _TTS_PIPELINE_CACHE, TTS_ENGINE
    
    if TTS_ENGINE != "kokoro":
        return None
    
    try:
        # Import and use the proper Kokoro configuration
        from kokoro_local_config import create_kokoro_pipeline
        
        lang_to_use = lang_code or TTS_LANG_CODE
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

def generate_tts_audio(text: str, voice: str = None, lang_code: str = None) -> list:
    """Generate TTS audio from text and return list of file paths"""
    if not TTS_AVAILABLE:
        return []
    
    try:
        # Create output directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, 'audio_output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate full text without truncation (user requested full-length audio)
        
        # Generate unique filename with timestamp
        import time
        timestamp = int(time.time())
        filename = f'response_{timestamp}.wav'
        filepath = os.path.join(output_dir, filename)
        
        # Use Kokoro TTS only
        if TTS_ENGINE == "kokoro":
            result = _generate_kokoro_audio(text, voice, lang_code, filepath)
            return result
        else:
            logger.error(f"Kokoro TTS not available. Engine: {TTS_ENGINE}")
            return []
            
    except Exception as e:
        logger.error(f"Error generating TTS audio: {e}")
        return []

def _generate_kokoro_audio(text: str, voice: str, lang_code: str, filepath: str) -> list:
    """Generate audio using Kokoro TTS with improved long-text handling.
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
    """Clean up old audio files (keep only last 5 for better performance)"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, 'audio_output')
        
        audio_files = [f for f in os.listdir(output_dir) if f.startswith('response_') and f.endswith('.wav')]
        audio_files.sort(key=lambda x: os.path.getctime(os.path.join(output_dir, x)), reverse=True)
        
        # Keep only the 5 most recent files (reduced from 10)
        for old_file in audio_files[5:]:
            old_filepath = os.path.join(output_dir, old_file)
            os.remove(old_filepath)
            logger.info(f"Cleaned up old audio file: {old_file}")
    except Exception as e:
        logger.warning(f"Could not clean up old audio files: {e}")

# === END TTS UTILITIES ===


# === STATE ===

class State(TypedDict):
    messages: Annotated[list, add_messages]





# === TOOLS ===
@tool
def human_assistance(query: str) -> str:
    """Request assistance from a human when the AI needs help with complex or sensitive queries."""
    # This will raise a Command exception that gets caught by the stream handler
    return interrupt({"query": query})

@tool
def generate_literature_review(topic: str) -> str:
    """Generate a comprehensive literature review on any topic"""
    prompt = f"""
    Create a comprehensive literature review on {topic}.
    Include:
    1. Background and context
    2. Key theories and frameworks
    3. Recent findings and developments
    4. Current gaps and opportunities
    5. Methodological approaches
    6. Future directions and trends
    
    Structure this as a thorough review with proper citations and clear explanations.
    """
    llm = init_chat_model(MODEL, model_provider=model_provider)
    response = llm.invoke(prompt)
    return response.content

@tool
def generate_research_methodology(topic: str) -> str:
    """Suggest appropriate research methodologies for a given topic"""
    prompt = f"""
    Suggest comprehensive research methodologies for studying {topic}.
    Include:
    1. Quantitative approaches (surveys, experiments, statistical analysis)
    2. Qualitative approaches (interviews, case studies, content analysis)
    3. Mixed methods approaches
    4. Data collection strategies
    5. Sampling techniques
    6. Ethical considerations
    7. Validity and reliability measures
    
    Provide detailed explanations for each methodology and when to use them.
    """
    llm = init_chat_model(MODEL, model_provider=model_provider)
    response = llm.invoke(prompt)
    return response.content

@tool
def generate_study_plan(subject: str) -> str:
    """Create a comprehensive study plan for any subject"""
    prompt = f"""
    Create a detailed study plan for {subject}.
    Include:
    1. Learning objectives and outcomes
    2. Weekly study schedule
    3. Key topics and subtopics
    4. Study strategies and techniques
    5. Practice exercises and assessments
    6. Recommended resources and readings
    7. Progress tracking methods
    8. Time management tips
    
    Make this practical and actionable for effective learning.
    """
    llm = init_chat_model(MODEL, model_provider=model_provider)
    response = llm.invoke(prompt)
    return response.content

@tool
def generate_audio_response(request: str) -> str:
    """Generate audio from text using TTS (Text-to-Speech)
    
    Args:
        request: Audio request in format "text|voice|lang_code" (e.g., "Hello world|af_heart|b")
    """
    if not TTS_AVAILABLE:
        return "TTS is not available. Please install kokoro and soundfile libraries."
    
    # Parse the request
    parts = request.split('|')
    text = parts[0] if len(parts) > 0 else ""
    voice = parts[1] if len(parts) > 1 else None
    lang_code = parts[2] if len(parts) > 2 else None
    
    audio_files = generate_tts_audio(text, voice, lang_code)
    
    if audio_files:
        # Prefer returning a relative path Streamlit can render
        try:
            import os
            rel_paths = []
            for p in audio_files:
                base = os.path.basename(p)
                rel_paths.append(f"audio_output/{base}")
            primary = rel_paths[0]
            return f"Audio generated successfully! File: {primary}"
        except Exception:
            return f"Audio generated successfully! Files saved: {', '.join(audio_files)}"
    else:
        return "No audio was generated from the text."

@tool
def browse_web_page(url: str) -> str:
    """Browses a web page or social media post and returns its content.

    Args:
        url: The URL of the web page or social media post to browse.

    Returns:
        The text content of the page/post, or an error message if fetching fails.
    """
    if not url or not url.startswith(('http://', 'https://')):
        return "Invalid URL. Please provide a full and valid URL starting with http:// or https://."

    try:
        # Detect platform and handle accordingly
        platform = _detect_platform(url)
        
        if platform == "instagram":
            return _browse_instagram_post(url)
        elif platform == "linkedin":
            return _browse_linkedin_post(url)
        elif platform == "twitter" or platform == "x":
            return _browse_twitter_post(url)
        else:
            return _browse_regular_webpage(url)
            
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def _detect_platform(url: str) -> str:
    """Detect the platform from the URL"""
    url_lower = url.lower()
    
    if 'instagram.com' in url_lower:
        return "instagram"
    elif 'linkedin.com' in url_lower:
        return "linkedin"
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return "twitter"
    else:
        return "webpage"

def _browse_instagram_post(url: str) -> str:
    """Browse Instagram post content"""
    try:
        # Instagram requires special handling due to dynamic content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract Instagram post content
        content = []
        
        # Try to find post description
        description_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            'div[data-testid="post-caption"]',
            'article div[dir="auto"]',
            '.caption',
            '[data-testid="post-caption"]'
        ]
        
        for selector in description_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 10:
                    content.append(f"📝 Post Description: {text}")
                    break
        
        # Try to find username
        username_selectors = [
            'meta[property="og:title"]',
            'a[href*="/p/"]',
            'header a',
            '.username'
        ]
        
        for selector in username_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and '@' in text:
                    content.append(f"👤 Username: {text}")
                    break
        
        # Try to find engagement metrics
        engagement_selectors = [
            '[data-testid="like-count"]',
            '[data-testid="comment-count"]',
            '.likes',
            '.comments'
        ]
        
        for selector in engagement_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and any(word in text.lower() for word in ['like', 'comment', 'view']):
                    content.append(f"📊 Engagement: {text}")
                    break
        
        if content:
            result = f"📱 Instagram Post Analysis:\n\n"
            result += "\n".join(content)
            result += f"\n\n🔗 Source: {url}"
            return result
        else:
            return f"Could not extract Instagram post content. The post might be private or require authentication.\n\n🔗 URL: {url}"
            
    except Exception as e:
        return f"Error browsing Instagram post: {e}"

def _browse_linkedin_post(url: str) -> str:
    """Browse LinkedIn post content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract LinkedIn post content
        content = []
        
        # Try to find post content
        content_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            '.feed-shared-text',
            '.feed-shared-update-v2__description',
            '.share-text',
            '[data-testid="post-content"]'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 20:
                    content.append(f"📝 Post Content: {text}")
                    break
        
        # Try to find author name
        author_selectors = [
            'meta[property="og:title"]',
            '.feed-shared-actor__name',
            '.post-meta__headline',
            '.author-name'
        ]
        
        for selector in author_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 2:
                    content.append(f"👤 Author: {text}")
                    break
        
        # Try to find engagement metrics
        engagement_selectors = [
            '.social-details-social-counts',
            '.feed-shared-social-counts',
            '.reactions-count',
            '.comments-count'
        ]
        
        for selector in engagement_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and any(word in text.lower() for word in ['like', 'comment', 'share', 'reaction']):
                    content.append(f"📊 Engagement: {text}")
                    break
        
        if content:
            result = f"💼 LinkedIn Post Analysis:\n\n"
            result += "\n".join(content)
            result += f"\n\n🔗 Source: {url}"
            return result
        else:
            return f"Could not extract LinkedIn post content. The post might be private or require authentication.\n\n🔗 URL: {url}"
            
    except Exception as e:
        return f"Error browsing LinkedIn post: {e}"

def _browse_twitter_post(url: str) -> str:
    """Browse Twitter/X post content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract Twitter/X post content
        content = []
        
        # Try to find tweet content
        content_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            '[data-testid="tweetText"]',
            '.tweet-text',
            '.js-tweet-text',
            'article div[lang]'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 10:
                    content.append(f"🐦 Tweet Content: {text}")
                    break
        
        # Try to find username
        username_selectors = [
            'meta[property="og:title"]',
            '[data-testid="User-Name"]',
            '.username',
            '.screen-name'
        ]
        
        for selector in username_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and '@' in text:
                    content.append(f"👤 Username: {text}")
                    break
        
        # Try to find engagement metrics
        engagement_selectors = [
            '[data-testid="like"]',
            '[data-testid="retweet"]',
            '[data-testid="reply"]',
            '.tweet-stats'
        ]
        
        engagement_metrics = []
        for selector in engagement_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and any(word in text.lower() for word in ['like', 'retweet', 'reply', 'view']):
                    engagement_metrics.append(text)
        
        if engagement_metrics:
            content.append(f"📊 Engagement: {', '.join(engagement_metrics)}")
        
        if content:
            result = f"🐦 Twitter/X Post Analysis:\n\n"
            result += "\n".join(content)
            result += f"\n\n🔗 Source: {url}"
            return result
        else:
            return f"Could not extract Twitter/X post content. The post might be private or require authentication.\n\n🔗 URL: {url}"
            
    except Exception as e:
        return f"Error browsing Twitter/X post: {e}"

def _browse_regular_webpage(url: str) -> str:
    """Browse regular web page content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
            
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:5000] # Return the first 5000 characters to avoid being too long
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

@tool
def search_news(query: str) -> str:
    """Search for news, headlines, and current events using Tavily search. Use this tool for ANY news-related queries including AI trends, technology news, business news, world news, etc.
    
    Args:
        topic: News topic to search for (e.g., "AI trends", "technology news", "latest news", "business news")
        location: Geographic location for news (default: "global")
        age_group: Target age group ("general", "youth", "senior", "professional")
        max_results: Maximum number of news items to return (default: 5)
        time_period: Time period for news ("recent", "today", "week", "month")
    
    Args:
        query: News query to search for (e.g., "AI trends", "technology news", "latest news", "business news")
    """
    try:
        from datetime import datetime, timedelta
        
        # Parse the query to extract topic and location if possible
        topic = query
        location = "global"
        age_group = "general"
        max_results = 5
        time_period = "recent"
        
        # Create optimized search query based on parameters
        search_query = _build_news_search_query(topic, location, age_group, time_period)
        
        # Use Tavily search to get news
        tavily_search = TavilySearch(max_results=max_results * 2)  # Get more results to account for filtering
        search_results = tavily_search.invoke(search_query)
        
        if not search_results or not hasattr(search_results, 'content'):
            return f"No news found for '{topic}' in {location}."
        
        # Extract URLs and headlines from search results
        news_items = _extract_news_from_search_results(search_results.content, max_results)
        
        if not news_items:
            return f"No relevant news found for '{topic}' in {location}."
        
        # Fetch and summarize each article
        summarized_news = _fetch_and_summarize_articles(news_items, topic, location, age_group)
        
        return summarized_news
        
    except Exception as e:
        logger.error(f"Error in search_news: {e}")
        return f"Error searching for news: {e}"

def _build_news_search_query(topic: str, location: str, age_group: str, time_period: str) -> str:
    """Build an optimized search query for news based on parameters"""
    
    # Base query
    query_parts = [topic]
    
    # Add location context
    if location.lower() != "global":
        query_parts.append(f"in {location}")
    
    # Add time period context
    time_contexts = {
        "recent": "latest breaking news",
        "today": "today's news",
        "week": "this week's news",
        "month": "this month's news"
    }
    if time_period in time_contexts:
        query_parts.append(time_contexts[time_period])
    
    # Add age-appropriate context
    age_contexts = {
        "youth": "trending viral news",
        "senior": "important developments",
        "professional": "business and industry news",
        "general": "mainstream news"
    }
    if age_group in age_contexts:
        query_parts.append(age_contexts[age_group])
    
    # Add news-specific terms
    query_parts.extend(["news", "headlines", "latest updates"])
    
    return " ".join(query_parts)

def _extract_news_from_search_results(search_content: str, max_results: int) -> list:
    """Extract news URLs and headlines from Tavily search results"""
    try:
        news_items = []
        lines = search_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 20:
                # Look for lines that might contain URLs
                if 'http' in line and any(domain in line.lower() for domain in ['news', 'bbc', 'cnn', 'reuters', 'ap', 'guardian', 'nytimes', 'washingtonpost', 'techcrunch', 'theverge', 'arstechnica', 'wired', 'mit', 'citizen', 'dailynews', 'ippmedia', 'mwananchi']):
                    # Extract URL and title
                    url_match = re.search(r'https?://[^\s]+', line)
                    if url_match:
                        url = url_match.group(0)
                        # Clean up the title (remove URL and extra formatting)
                        title = line.replace(url, '').replace('•', '').replace('-', '').strip()
                        if title and len(title) > 10:
                            news_items.append({
                                'url': url,
                                'title': title,
                                'source': _extract_source_from_url(url)
                            })
        
        return news_items[:max_results]
        
    except Exception as e:
        logger.error(f"Error extracting news from search results: {e}")
        return []

def _extract_source_from_url(url: str) -> str:
    """Extract source name from URL"""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        # Remove www. and common TLDs
        source = domain.replace('www.', '').split('.')[0]
        return source.title()
    except:
        return "Unknown Source"

def _fetch_and_summarize_articles(news_items: list, topic: str, location: str, age_group: str) -> str:
    """Fetch full articles and generate summaries"""
    try:
        llm = init_chat_model(MODEL, model_provider=model_provider)
        summarized_articles = []
        
        for i, item in enumerate(news_items, 1):
            try:
                logger.info(f"Fetching article {i}/{len(news_items)}: {item['title'][:50]}...")
                
                # Fetch the full article content
                article_content = browse_web_page.invoke({'url': item['url']})
                
                if article_content and not article_content.startswith("Error") and len(article_content) > 100:
                    # Generate summary using LLM
                    summary = _generate_article_summary(llm, article_content, item['title'], age_group)
                    
                    summarized_articles.append({
                        'title': item['title'],
                        'summary': summary,
                        'url': item['url'],
                        'source': item['source']
                    })
                else:
                    # If we can't fetch the article, just include the headline
                    summarized_articles.append({
                        'title': item['title'],
                        'summary': "Article content could not be fetched. Please visit the source for full details.",
                        'url': item['url'],
                        'source': item['source']
                    })
                
            except Exception as e:
                logger.error(f"Error processing article {i}: {e}")
                continue
        
        # Format the results
        return _format_summarized_news(summarized_articles, topic, location, age_group)
        
    except Exception as e:
        logger.error(f"Error fetching and summarizing articles: {e}")
        return f"Error processing news articles: {e}"

def _generate_article_summary(llm, article_content: str, title: str, age_group: str) -> str:
    """Generate a concise summary of the article content"""
    try:
        # Truncate content if too long to avoid token limits
        max_content_length = 3000
        if len(article_content) > max_content_length:
            article_content = article_content[:max_content_length] + "..."
        
        # Create age-appropriate summary prompt
        age_context = {
            "youth": "Write a concise, engaging summary suitable for young adults",
            "senior": "Write a clear, detailed summary with important context",
            "professional": "Write a professional summary focusing on key facts and implications",
            "general": "Write a clear, balanced summary for general audience"
        }
        
        prompt = f"""
        {age_context.get(age_group, age_context['general'])} for this news article:
        
        Title: {title}
        
        Article Content:
        {article_content}
        
        Provide a 2-3 sentence summary that captures the main points and key details.
        Focus on the most important information and maintain accuracy.
        """
        
        response = llm.invoke(prompt)
        return response.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return "Summary could not be generated."

def _format_summarized_news(summarized_articles: list, topic: str, location: str, age_group: str) -> str:
    """Format the summarized news articles with proper structure"""
    try:
        location_emoji = _get_location_emoji(location)
        topic_emoji = _get_topic_emoji(topic)
        
        result = f"{location_emoji} {topic_emoji} News Summary for {location.title()}:\n\n"
        
        for i, article in enumerate(summarized_articles, 1):
            result += f"📰 **{i}. {article['title']}**\n"
            result += f"📝 {article['summary']}\n"
            result += f"🔗 Source: [{article['source']}]({article['url']})\n"
            result += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            result += "─" * 50 + "\n\n"
        
        result += f"🎯 Optimized for: {age_group.title()} audience\n"
        result += f"📊 Total articles: {len(summarized_articles)}"
        
        return result
        
    except Exception as e:
        logger.error(f"Error formatting summarized news: {e}")
        return f"Error formatting news results: {e}"

def _get_location_emoji(location: str) -> str:
    """Get appropriate emoji for location"""
    location_lower = location.lower()
    if 'tanzania' in location_lower or 'dar' in location_lower:
        return "🇹🇿"
    elif 'kenya' in location_lower:
        return "🇰🇪"
    elif 'uganda' in location_lower:
        return "🇺🇬"
    elif 'africa' in location_lower:
        return "🌍"
    elif 'usa' in location_lower or 'america' in location_lower:
        return "🇺🇸"
    elif 'uk' in location_lower or 'britain' in location_lower:
        return "🇬🇧"
    elif 'europe' in location_lower:
        return "🇪🇺"
    elif 'asia' in location_lower:
        return "🌏"
    else:
        return "🌍"

def _get_topic_emoji(topic: str) -> str:
    """Get appropriate emoji for topic"""
    topic_lower = topic.lower()
    if any(word in topic_lower for word in ['tech', 'technology', 'ai', 'artificial intelligence']):
        return "💻"
    elif any(word in topic_lower for word in ['business', 'economy', 'finance']):
        return "💰"
    elif any(word in topic_lower for word in ['sports', 'football', 'basketball']):
        return "⚽"
    elif any(word in topic_lower for word in ['politics', 'government']):
        return "🏛️"
    elif any(word in topic_lower for word in ['health', 'medical', 'covid']):
        return "🏥"
    elif any(word in topic_lower for word in ['entertainment', 'movie', 'music']):
        return "🎬"
    elif any(word in topic_lower for word in ['science', 'research']):
        return "🔬"
    else:
        return "📰"

@tool
def send_daily_news_email(request: str) -> str:
    """Send daily news digest email with flexible content from AI
    
    Args:
        request: Email request in format "recipient_email|topics|content" (e.g., "user@example.com|Technology,AI|Custom content")
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime
        import re
        
        # Parse the request
        parts = request.split('|')
        recipient_email = parts[0] if len(parts) > 0 else "williamjohnie61@gmail.com"
        news_topics = parts[1].split(',') if len(parts) > 1 and parts[1] else None
        custom_content = parts[2] if len(parts) > 2 else None
        
        # Check email configuration
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        
        if not all([sender_email, sender_password, recipient_email]):
            return "Email configuration incomplete. Please set SENDER_EMAIL, SENDER_PASSWORD, and provide recipient_email in .env file"
        
        # Helper function to convert markdown-style content to HTML
        def convert_content_to_html(content: str) -> str:
            """Convert markdown-style content to HTML for email"""
            if not content:
                return ""
            
            # Convert **bold** to <strong>
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            
            # Convert markdown links [text](url) to HTML links
            content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #3498db; text-decoration: none;">\1</a>', content)
            
            # Convert line breaks to <br> tags
            content = content.replace('\n', '<br>')
            
            # Convert separator lines
            content = re.sub(r'─{10,}', '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">', content)
            
            return content
        
        # Helper function to get emoji for topic
        def get_topic_emoji(topic: str) -> str:
            topic_lower = topic.lower()
            if any(word in topic_lower for word in ['tech', 'technology', 'ai', 'artificial intelligence']):
                return "💻"
            elif any(word in topic_lower for word in ['business', 'economy', 'finance']):
                return "💰"
            elif any(word in topic_lower for word in ['sports', 'football', 'basketball']):
                return "⚽"
            elif any(word in topic_lower for word in ['politics', 'government']):
                return "🏛️"
            elif any(word in topic_lower for word in ['health', 'medical', 'covid']):
                return "🏥"
            elif any(word in topic_lower for word in ['entertainment', 'movie', 'music']):
                return "🎬"
            elif any(word in topic_lower for word in ['science', 'research']):
                return "🔬"
            elif any(word in topic_lower for word in ['tanzania', 'africa']):
                return "🇹🇿"
            else:
                return "📰"
        
        # Start building email content
        email_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; }}
                .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .section {{ margin: 20px 0; padding: 20px; border-left: 4px solid #3498db; background-color: #f8f9fa; border-radius: 5px; }}
                .news-item {{ margin: 15px 0; padding: 15px; background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .news-title {{ font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 10px; }}
                .news-summary {{ color: #555; margin-bottom: 10px; line-height: 1.5; }}
                .news-source {{ color: #7f8c8d; font-size: 0.9em; margin-top: 10px; }}
                .news-source a {{ color: #3498db; text-decoration: none; }}
                .news-source a:hover {{ text-decoration: underline; }}
                .footer {{ text-align: center; margin-top: 30px; padding: 20px; background-color: #ecf0f1; border-radius: 5px; }}
                .emoji {{ font-size: 1.2em; }}
                hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
                strong {{ color: #2c3e50; }}
                .custom-content {{ background-color: #e8f4fd; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1><span class="emoji">📰</span> Daily News Digest</h1>
                <p>{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
        """
        
        # Add custom content if provided
        if custom_content:
            custom_html = convert_content_to_html(custom_content)
            email_content += f"""
            <div class="custom-content">
                <h2><span class="emoji">🤖</span> AI Generated Content</h2>
                <div class="news-content">
                    {custom_html}
                </div>
            </div>
            """
        
        # Add news topics if provided
        if news_topics:
            for topic in news_topics:
                try:
                    # Get news for this topic
                    topic_news = search_news.invoke({"query": topic})
                    
                    # Convert the content to HTML
                    topic_html = convert_content_to_html(topic_news)
                    topic_emoji = get_topic_emoji(topic)
                    
                    email_content += f"""
                    <div class="section">
                        <h2><span class="emoji">{topic_emoji}</span> {topic} News</h2>
                        <div class="news-content">
                            {topic_html}
                        </div>
                    </div>
                    """
                    
                except Exception as e:
                    logger.error(f"Error getting news for topic {topic}: {e}")
                    email_content += f"""
                    <div class="section">
                        <h2><span class="emoji">❌</span> {topic} News</h2>
                        <p>Unable to fetch news for this topic at the moment.</p>
                    </div>
                    """
        
        # If no custom content or topics provided, get some default news
        if not custom_content and not news_topics:
            try:
                # Get some general news
                general_news = search_news.invoke({"query": "latest news"})
                
                general_html = convert_content_to_html(general_news)
                
                email_content += f"""
                <div class="section">
                    <h2><span class="emoji">🌍</span> Latest News</h2>
                    <div class="news-content">
                        {general_html}
                    </div>
                </div>
                """
                
            except Exception as e:
                logger.error(f"Error getting default news: {e}")
                email_content += f"""
                <div class="section">
                    <h2><span class="emoji">❌</span> News</h2>
                    <p>Unable to fetch news at the moment. Please try again later.</p>
                </div>
                """
        
        email_content += f"""
            <div class="footer">
                <p><span class="emoji">🤖</span> Generated by Artemis AI News Assistant</p>
                <p style="font-size: 0.9em; color: #7f8c8d;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </body>
        </html>
        """
        
        # Send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"📰 Daily News Digest - {datetime.now().strftime('%B %d, %Y')}"
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        html_part = MIMEText(email_content, 'html')
        msg.attach(html_part)
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return f"✅ Daily news digest email sent successfully to {recipient_email}"
        
    except Exception as e:
        logger.error(f"Error sending daily news email: {e}")
        return f"Error sending email: {e}"

@tool
def setup_daily_news_schedule(request: str) -> str:
    """Setup daily news email schedule (requires running the scheduler script separately)
    
    Args:
        request: Schedule request in format "recipient_email|time|include_tanzania|include_tech" (e.g., "user@example.com|08:00|true|true")
    """
    try:
        import json
        from datetime import datetime
        
        # Parse the request
        parts = request.split('|')
        recipient_email = parts[0] if len(parts) > 0 else "williamjohnie61@gmail.com"
        time = parts[1] if len(parts) > 1 else "08:00"
        include_tanzania = parts[2].lower() == 'true' if len(parts) > 2 else True
        include_tech = parts[3].lower() == 'true' if len(parts) > 3 else True
        
        # Create schedule configuration
        schedule_config = {
            'recipient_email': recipient_email,
            'time': time,
            'include_tanzania': include_tanzania,
            'include_tech': include_tech,
            'created_at': datetime.now().isoformat(),
            'active': True
        }
        
        # Save configuration
        config_dir = 'data'
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, 'news_schedule.json')
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(schedule_config, f, indent=2)
        
        return f"✅ Daily news schedule configured successfully!\n\n" \
               f"📧 Recipient: {recipient_email}\n" \
               f"⏰ Time: {time}\n" \
               f"🇹🇿 Tanzania News: {'Yes' if include_tanzania else 'No'}\n" \
               f"🌍 Tech News: {'Yes' if include_tech else 'No'}\n\n" \
               f"To start the scheduler, run: python news_scheduler.py"
        
    except Exception as e:
        logger.error(f"Error setting up news schedule: {e}")
        return f"Error setting up schedule: {e}"
# === END TOOLS ===













# === MAIN CLASS ===
class ConversationalAgent:
    """Main chatbot class with improved error handling and state management"""

    def __init__(self):
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        logger.info("Conversational agent initialized successfully")

    def _build_graph(self):
        """Build the conversation graph with tools and a system prompt"""
        graph_builder = StateGraph(State)

        # Set up tools
        tavily_search = TavilySearch(max_results=2)
        tools = [
            tavily_search, 
            human_assistance, 
            browse_web_page,
            generate_literature_review,
            generate_research_methodology,
            generate_study_plan,
            generate_audio_response,
            search_news,
            send_daily_news_email,
            setup_daily_news_schedule
        ]

        # Initialize LLM with tools
        try:
            llm = init_chat_model(MODEL, model_provider=model_provider)
            llm_with_tools = llm.bind_tools(tools)
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

        # Create a system prompt to guide the LLM's tool usage
        system_prompt = (
            "You are a super intelligent AI assistant with access to multiple tools and capabilities. You can help with a wide range of tasks including research, analysis, content creation, and information gathering. You have access to:\n"
            "1. 'tavily_search' - search the web for current information, research, and data\n"
            "2. 'browse_web_page' - read and analyze web pages, articles, social media posts (Instagram, LinkedIn, Twitter/X), and online content\n"
            "3. 'generate_literature_review' - create comprehensive literature reviews on any topic\n"
            "4. 'generate_research_methodology' - suggest research methodologies for various topics\n"
            "5. 'generate_study_plan' - create detailed study plans for any subject\n"
            "6. 'generate_audio_response' - convert text responses to audio using TTS\n"
            "7. 'search_news' - search for news headlines and updates across locations and topics\n" # Updated tool description
            "8. 'send_daily_news_email' - send flexible daily news digest email with custom topics or content\n"
            "9. 'setup_daily_news_schedule' - setup daily news email schedule\n"
            "10. 'human_assistance' - request human help when needed\n\n"
            "You are capable of handling diverse topics and providing intelligent, well-researched responses.\n\n"
            "- If the user provides a URL to any webpage or social media post (Instagram, LinkedIn, Twitter/X), use the 'browse_web_page' tool to analyze it.\n"
            "- If the user asks you to browse a page without providing a URL, you MUST ask for one.\n"
            "- For research questions and information gathering, use the 'tavily_search' tool to find current information and sources.\n"
            "- For comprehensive topic analysis, use the 'generate_literature_review' tool for detailed reviews.\n"
            "- For research methodology questions, use the 'generate_research_methodology' tool.\n"
            "- For learning and study planning, use the 'generate_study_plan' tool for structured approaches.\n"
            "- Provide detailed explanations with examples and practical applications.\n"
            "- Always cite sources when possible and suggest additional resources.\n"
            "- Focus on accuracy, critical thinking, and evidence-based responses.\n"
            "- When users ask for audio versions of responses or say 'speak this', 'read aloud', or 'audio', use the 'generate_audio_response' tool.\n"
            "- When users ask for news, headlines, current events, or any news-related queries, ALWAYS use the 'search_news' tool.\n"
            "- For general news requests, use 'search_news' with the query 'latest news'.\n"
            "- For specific topic news (like AI, technology, business, etc.), use 'search_news' with the topic as the query.\n"
            "- For AI trends, AI news, or technology trends, use 'search_news' with queries like 'AI trends' or 'technology trends'.\n"
            "- For location-specific news, include the location in the query like 'news in Tanzania' or 'technology news in Africa'.\n"
            "- When users ask to send news via email, use the 'send_daily_news_email' tool with custom topics or content.\n"
            "- For email scheduling, use the 'setup_daily_news_schedule' tool.\n"
            "- If the user asks for 'expert guidance', 'human help', or explicitly asks you to 'request assistance', "
            "you MUST use the 'human_assistance' tool. Do not try to answer these queries yourself.\n"
            "- IMPORTANT: When users ask for news, trends, or current events, ALWAYS use the 'search_news' tool instead of providing manual summaries or responses."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                ("placeholder", "{messages}"),
            ]
        )

        # Create a chain that combines the prompt and the LLM
        agent_chain = prompt | llm_with_tools

        # Define chatbot node
        def chatbot_node(state: State):
            try:
                filtered_messages = self._filter_messages(state["messages"])
                if not filtered_messages:
                    logger.warning("No valid messages found in state")
                    return {"messages": []}
                message = agent_chain.invoke({"messages": filtered_messages})
                if hasattr(message, "tool_calls") and len(message.tool_calls) > 1:
                    logger.warning(f"Multiple tool calls detected: {len(message.tool_calls)}")
                return {"messages": [message]}
            except Exception as e:
                logger.error(f"Error in chatbot node: {e}")
                error_msg = {"role": "assistant", "content": "I encountered an error processing your request. Please try again."}
                return {"messages": [error_msg]}

        # Build graph
        graph_builder.add_node("chatbot", chatbot_node)
        
        tool_node = ToolNode(tools=tools)
        graph_builder.add_node("tools", tool_node)
        
        # Add edges
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")
        graph_builder.add_edge(START, "chatbot")
        
        return graph_builder.compile(checkpointer=self.memory)

    def _filter_messages(self, messages):
        """Filter messages to keep only valid ones with improved logic"""
        filtered_messages = []
        
        for msg in messages:
            # Handle different message types
            if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls", None):
                # Keep tool call messages
                filtered_messages.append(msg)
            # CORRECTED: Added a check to ensure msg.content is not None
            elif hasattr(msg, "content") and msg.content is not None:
                # Handle LCEL message objects
                content = str(msg.content).strip()
                if content:
                    filtered_messages.append(msg)
            elif isinstance(msg, dict):
                # Handle dict-style messages
                content = str(msg.get("content", "")).strip()
                if content:
                    filtered_messages.append(msg)
            else:
                # This will now correctly skip messages where content is None
                logger.debug(f"Skipping message of unknown type or with None content: {type(msg)}")
        
        return filtered_messages

    def _is_json(self, text):
        """Check if text is valid JSON"""
        try:
            json.loads(text)
            return True
        except (ValueError, TypeError):
            return False

    def _handle_interrupt(self, command_exception, streamlit_output=None):
        """Handle human-in-the-loop interrupts. If streamlit_output is provided, use it for output."""
        try:
            query = command_exception.data.get('query', 'Assistance needed')
            response = f"\n[🤝 Human Assistance Needed] {query}\nPlease provide your response:"
            if streamlit_output:
                streamlit_output.write(response)
                # In Streamlit, we can't resume, so just display
            else:
                print(f"\n[🤝 Human Assistance Needed] {query}")
                human_input = input("Your response: ").strip()
                if not human_input:
                    human_input = "No response provided"
                command_exception.resume({"data": human_input})
                logger.info("Human assistance provided, resuming conversation")
        except Exception as e:
            logger.error(f"Error handling interrupt: {e}")
            try:
                error_msg = "Unable to get human assistance"
                if streamlit_output:
                    streamlit_output.write(error_msg)
                else:
                    print(error_msg)
                command_exception.resume({"data": error_msg})
            except:
                pass  # If resume fails, the conversation will end

    def _process_event_value(self, value):
        """Process event values and extract assistant responses"""
        if isinstance(value, tuple) and len(value) == 2:
            value = value[1]
        
        if isinstance(value, dict) and "messages" in value and value["messages"]:
            last_msg = value["messages"][-1]
            
            content = getattr(last_msg, "content", None)
            if content is None and isinstance(last_msg, dict):
                content = last_msg.get("content", "")
            
            if content and not self._is_json(str(content)):
                return content  # Return the assistant's message content
        return None

    def stream_conversation(self, user_input: str, thread_id: str = "default-thread", streamlit_output=None):
        """Stream conversation updates with improved error handling. If streamlit_output is provided, output to Streamlit."""
        config = {"configurable": {"thread_id": thread_id}}
        response = ""
        try:
            for event in self.graph.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config
            ):
                for value in event.values():
                    content = self._process_event_value(value)
                    if content and not self._is_json(str(content)):
                        if streamlit_output:
                            response += content + "\n"
                            streamlit_output.write(response)
                        else:
                            response = content  # Set response to the latest assistant content
            return response
        except Command as cmd:
            self._handle_interrupt(cmd, streamlit_output=streamlit_output)
        except Exception as e:
            logger.error(f"Error in stream_conversation: {e}")
            if streamlit_output:
                streamlit_output.write(f"❌ Error: {e}")
            else:
                print(f"❌ Error: {e}")

    def print_state_snapshot(self, thread_id: str = "default-thread"):
        """Print detailed state information for debugging"""
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            snapshot = self.graph.get_state(config)
            print(f"\n--- 📊 State Snapshot (Thread: {thread_id}) ---")
            print(f"Values: {snapshot.values}")
            print(f"Next: {snapshot.next}")
            print(f"Created: {snapshot.created_at}")
            print(f"Tasks: {len(snapshot.tasks) if snapshot.tasks else 0}")
            print("--- End Snapshot ---\n")
            
        except Exception as e:
            logger.error(f"Error getting state snapshot: {e}")
            print(f"❌ Could not retrieve state: {e}")

    def run_interactive_session(self):
        """Run the interactive chat session"""
        thread_id = "default-thread"
        
        print("🚀 Conversational AI Agent Started!")
        print("Commands: 'quit'/'exit'/'q' to stop, 'state' to view current state")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == "state":
                    self.print_state_snapshot(thread_id=thread_id)
                    continue
                elif not user_input:
                    print("Please enter a message.")
                    continue
                
                self.stream_conversation(user_input, thread_id=thread_id)
                
            except KeyboardInterrupt:
                print("\n👋 Chat interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                print(f"❌ Unexpected error: {e}")
                print("Type 'quit' to exit or continue chatting...")

def main():
    """Main entry point"""
    try:
        agent = ConversationalAgent()
        agent.run_interactive_session()
    except Exception as e:
        logger.error(f"Failed to start agent: {e}")
        print(f"❌ Failed to start: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())