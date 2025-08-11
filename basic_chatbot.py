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

# Install compatible versions of dependencies first
try:
    # Try normal install first
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'numpy<2.0', 'scipy<2.0'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'kokoro==0.7.16', 'soundfile'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception as e:
    logger.warning(f"Failed to install dependencies normally: {e}")
    try:
        # Try with --break-system-packages if needed
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--break-system-packages', 'numpy<2.0', 'scipy<2.0'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--break-system-packages', 'kokoro==0.7.16', 'soundfile'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e2:
        logger.warning(f"Failed to install dependencies with --break-system-packages: {e2}")

# Install espeak-ng (Linux only, will fail silently on non-Linux)
try:
    subprocess.run(['apt-get', '-qq', '-y', 'install', 'espeak-ng'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception:
    pass  # Ignore errors on non-Linux systems

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
from langchain_community.chat_models import init_chat_model
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

# Load environment variables from .env file
load_dotenv()

# === CONFIGURATION ===
MODEL = os.getenv("CHATBOT_MODEL", "openai:gpt-4")
API_KEY = os.getenv("CHATBOT_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

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

# === TTS UTILITIES ===

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

# def _generate_coqui_audio(text: str, filepath: str, voice: str = None, lang_code: str = None) -> list:
#     """Generate audio using Coqui TTS (high-quality, reliable engine)"""
#     try:
#         from coqui_tts_config import create_coqui_tts, generate_coqui_audio
        
#         logger.info(f"🎵 Generating Coqui TTS audio for {len(text)} characters...")
        
#         # Create TTS instance
#         tts = create_coqui_tts()
#         if not tts:
#             logger.error("❌ Failed to create Coqui TTS instance")
#             return []
        
#         # Use provided voice or default
#         voice_to_use = voice or TTS_VOICE
#         lang_to_use = lang_code or TTS_LANG_CODE
        
#         # Generate audio
#         result = generate_coqui_audio(tts, text, filepath, voice_to_use, lang_to_use)
        
#         if result:
#             logger.info(f"✅ Coqui TTS audio saved: {filepath}")
#             _cleanup_old_audio_files()
#             return [filepath]
#         else:
#             logger.error("❌ Coqui TTS audio generation failed")
#             return []
        
#     except Exception as e:
#         logger.error(f"❌ Error generating Coqui TTS audio: {e}")
#         return []

# def _generate_pyttsx3_audio(text: str, filepath: str) -> list:
#     """Generate audio using PyTTSx3 with female voice and optimized settings"""
#     try:
#         import pyttsx3
        
#         logger.info(f"🎵 Generating PyTTSx3 audio for {len(text)} characters...")
        
#         # Initialize the TTS engine
#         engine = pyttsx3.init()
        
#         # Get available voices
#         voices = engine.getProperty('voices')
        
#         # Find and set a female voice (prefer high-quality female voices like Kokoro)
#         female_voice = None
#         preferred_female_voices = ['samantha', 'victoria', 'karen', 'alice', 'fiona']
        
#         for voice in voices:
#             voice_name = voice.name.lower()
#             voice_id = voice.id.lower()
            
#             # Look for preferred female voices first
#             for preferred in preferred_female_voices:
#                 if preferred in voice_name or preferred in voice_id:
#                     female_voice = voice
#                     break
            
#             if female_voice:
#                 break
            
#             # Fallback to any female voice
#             if any(indicator in voice_name or indicator in voice_id for indicator in 
#                    ['female', 'woman', 'girl']):
#                 female_voice = voice
#                 break
        
#         # Set voice (female if found, otherwise first available)
#         if female_voice:
#             engine.setProperty('voice', female_voice.id)
#             logger.info(f"🎭 Using female voice: {female_voice.name}")
#         elif voices:
#             engine.setProperty('voice', voices[0].id)
#             logger.info(f"🎭 Using voice: {voices[0].name}")
        
#         # Optimize settings for better quality and speed
#         engine.setProperty('rate', 180)      # Faster speech (was 150)
#         engine.setProperty('volume', 0.95)   # Higher volume for clarity
#         engine.setProperty('pitch', 1.1)     # Slightly higher pitch for female-like sound
        
#         # Save to file
#         engine.save_to_file(text, filepath)
#         engine.runAndWait()
        
#         logger.info(f"✅ PyTTSx3 audio saved: {filepath}")
#         _cleanup_old_audio_files()
#         return [filepath]
        
#     except Exception as e:
#         logger.error(f"❌ Error generating PyTTSx3 audio: {e}")
#         return []

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
def generate_linkedin_post(topic: str, style: str = "academic") -> str:
    """Generate an academic LinkedIn post for professional networking and scholarly discussion"""
    prompt = f"""
    Create an academic LinkedIn post about {topic} in a {style} style.
    Structure: Research insight → Key findings → Academic implications → Call for collaboration
    Focus on scholarly discussion, research implications, and academic networking.
    Keep it under 300 words, use relevant academic hashtags.
    """
    llm = init_chat_model(MODEL, model_provider=model_provider)
    response = llm.invoke(prompt)
    return response.content

@tool
def generate_twitter_thread(topic: str, num_tweets: int = 5) -> str:
    """Generate an educational Twitter thread for academic discussion and knowledge sharing"""
    prompt = f"""
    Create a {num_tweets}-tweet educational thread about {topic}.
    Structure: Research question → Key concepts → Evidence/examples → Implications → Further reading
    Focus on educational value, academic rigor, and knowledge sharing.
    Each tweet max 280 chars. Number them 1/{num_tweets}, 2/{num_tweets}, etc.
    Include relevant academic hashtags and citations where appropriate.
    """
    llm = init_chat_model(MODEL, model_provider=model_provider)
    response = llm.invoke(prompt)
    return response.content

@tool
def post_to_linkedin(content: str) -> str:
    """Stub: Post content to LinkedIn via API (not implemented)."""
    try:
        LINKEDIN_CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID')
        LINKEDIN_CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET')
        if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
            return "LinkedIn API credentials not configured. Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in your .env file."
        # NOTE: Actual LinkedIn API posting is not implemented in this MVP.
        return f"Successfully posted to LinkedIn:\n{content}"
    except Exception as e:
        return f"Error posting to LinkedIn: {str(e)}"

@tool
def schedule_content(content: str, platform: str, datetime: str) -> str:
    """Schedule academic content for later posting"""
    return f"Academic content scheduled for {platform} at {datetime}:\n{content}"

@tool
def generate_literature_review(topic: str) -> str:
    """Generate a comprehensive literature review on a research topic"""
    prompt = f"""
    Create a comprehensive literature review on {topic}.
    Include:
    1. Background and context
    2. Key theories and frameworks
    3. Recent research findings
    4. Research gaps and opportunities
    5. Methodological approaches
    6. Future research directions
    
    Structure this as an academic literature review with proper citations and scholarly tone.
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
    """Create a comprehensive study plan for academic subjects"""
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
def generate_audio_response(text: str, voice: str = None, lang_code: str = None) -> str:
    """Generate audio from text using TTS (Text-to-Speech)"""
    if not TTS_AVAILABLE:
        return "TTS is not available. Please install kokoro and soundfile libraries."
    
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
    """Browses a web page and returns its text content.

    Args:
        url: The URL of the web page to browse.

    Returns:
        The text content of the web page, or an error message if fetching fails.
    """
    if not url or not url.startswith(('http://', 'https://')):
        return "Invalid URL. Please provide a full and valid URL starting with http:// or https://."

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
            generate_linkedin_post,
            generate_twitter_thread,
            post_to_linkedin,
            schedule_content,
            generate_literature_review,
            generate_research_methodology,
            generate_study_plan,
            generate_audio_response
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
            "You are an expert academic research and study assistant specializing in scholarly work, literature reviews, and educational support. You have access to:\n"
            "1. 'tavily_search' - find academic papers, research studies, and scholarly information\n"
            "2. 'browse_web_page' - read and analyze academic articles, research papers, and educational content\n"
            "3. 'generate_linkedin_post' - create professional academic networking posts\n"
            "4. 'generate_twitter_thread' - create educational content threads\n"
            "5. 'post_to_linkedin' - publish academic content\n"
            "6. 'schedule_content' - schedule academic content\n"
            "7. 'generate_literature_review' - create comprehensive literature reviews\n"
            "8. 'generate_research_methodology' - suggest research methodologies\n"
            "9. 'generate_study_plan' - create detailed study plans\n"
            "10. 'generate_audio_response' - convert text responses to audio using TTS\n"
            "11. 'human_assistance' - request human help\n\n"
            "For academic research: Always prioritize peer-reviewed sources, academic databases, and scholarly content.\n"
            "For study assistance: Provide comprehensive explanations, examples, and learning strategies.\n\n"
            "- If the user provides a URL to an academic paper or research article, use the 'browse_web_page' tool to analyze it.\n"
            "- If the user asks you to browse a page without providing a URL, you MUST ask for one.\n"
            "- For research questions, use the 'tavily_search' tool to find recent studies and academic sources.\n"
            "- For literature reviews, use the 'generate_literature_review' tool for comprehensive academic analysis.\n"
            "- For research methodology questions, use the 'generate_research_methodology' tool.\n"
            "- For study planning, use the 'generate_study_plan' tool for structured learning approaches.\n"
            "- For study help, provide detailed explanations with examples and practice problems.\n"
            "- Always cite sources when possible and suggest additional reading materials.\n"
            "- Focus on academic rigor, critical thinking, and evidence-based responses.\n"
            "- When users ask for audio versions of responses or say 'speak this', 'read aloud', or 'audio', use the 'generate_audio_response' tool.\n"
            "- If the user asks for 'expert guidance', 'human help', or explicitly asks you to 'request assistance', "
            "you MUST use the 'human_assistance' tool. Do not try to answer these queries yourself."
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