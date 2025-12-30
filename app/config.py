"""
Global configuration for the AI Agent application.
Centralizes all configuration settings for environment, models, TTS, and database.
"""

import os
import warnings
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env", override=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Settings:
    """Application settings and configuration."""
    
    # ============================================================================
    # ENVIRONMENT CONFIGURATION
    # ============================================================================
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development').lower()
    IS_DEV: bool = ENVIRONMENT == 'development'
    
    # ============================================================================
    # DATABASE CONFIGURATION
    # ============================================================================
    MONGO_URI: str = os.getenv("MONGO_URI")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "test-db-retry")
    
    # ============================================================================
    # API KEYS
    # ============================================================================
    # Chatbot API configuration
    CHATBOT_MODEL: str = os.getenv("CHATBOT_MODEL", "openai:gpt-4")
    CHATBOT_API_KEY: str = os.getenv("CHATBOT_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
    # ============================================================================
    # OAUTH CONFIGURATION
    # ============================================================================
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    
    # ============================================================================
    # EMAIL CONFIGURATION (for Celery tasks)
    # ============================================================================
    SMTP_SERVER: str = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT: int = int(os.getenv('SMTP_PORT', '587'))
    SENDER_EMAIL: str = os.getenv('SENDER_EMAIL')
    SENDER_PASSWORD: str = os.getenv('SENDER_PASSWORD')
    
    # ============================================================================
    # TTS CONFIGURATION
    # ============================================================================
    TTS_VOICE: str = os.getenv("TTS_VOICE", "af_heart")
    TTS_LANG_CODE: str = os.getenv("TTS_LANG_CODE", "b")
    
    # ============================================================================
    # APPLICATION SETTINGS
    # ============================================================================
    APP_TITLE: str = "AI Agent API"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "FastAPI-based conversational AI assistant with TTS support"
    
    # CORS settings
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]


# Create settings instance
settings = Settings()

# Log environment
logger.info(f"Running in {settings.ENVIRONMENT} mode")

# Validate required API keys in production
if not settings.IS_DEV:
    if not settings.CHATBOT_API_KEY and not settings.OPENAI_API_KEY:
        logger.warning("CHATBOT_API_KEY or OPENAI_API_KEY environment variable is recommended in production")
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY environment variable is recommended in production")

# ============================================================================
# MODEL PROVIDER CONFIGURATION
# ============================================================================

def get_model_provider(model: str) -> str:
    """Determine the model provider from the model string."""
    if model.startswith("openai:"):
        return "openai"
    elif model.startswith("anthropic:"):
        return "anthropic"
    elif model.startswith("google:"):
        return "google_genai"
    else:
        logger.warning(f"Unknown model prefix for {model}, using OpenAI as default")
        return "openai"

MODEL_PROVIDER = get_model_provider(settings.CHATBOT_MODEL)

# Set environment variables for the selected model provider
if MODEL_PROVIDER == "openai":
    os.environ["OPENAI_API_KEY"] = settings.CHATBOT_API_KEY or settings.OPENAI_API_KEY or ""
elif MODEL_PROVIDER == "anthropic":
    os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY or settings.CHATBOT_API_KEY or ""
elif MODEL_PROVIDER == "google_genai":
    os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY or settings.CHATBOT_API_KEY or ""

# Set Tavily API key
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY or ""

logger.info(f"Using model: {settings.CHATBOT_MODEL} with provider: {MODEL_PROVIDER}")

# ============================================================================
# TTS (TEXT-TO-SPEECH) CONFIGURATION
# ============================================================================

# Suppress PyTorch warnings BEFORE importing torch
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['PYTORCH_DISABLE_WARNINGS'] = '1'
os.environ['TORCH_WARN_ONCE'] = '0'
os.environ['PYTORCH_WARN_ONCE'] = '0'
os.environ['KOKORO_REPO_ID'] = 'hexgrad/Kokoro-82M'

# Suppress all warnings at system level
warnings.filterwarnings("ignore")

# Check TTS availability
TTS_AVAILABLE = False
TTS_ENGINE = None

try:
    # Import torch with warnings suppressed
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import torch
        torch.set_warn_always(False)
    
    # Import kokoro
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from kokoro import KPipeline
        import soundfile as sf
    
    TTS_AVAILABLE = True
    TTS_ENGINE = "kokoro"
    logger.info("Kokoro TTS libraries loaded successfully")
except ImportError as e:
    logger.warning(f"Kokoro TTS not available: {e}")
    logger.warning("Audio generation will be disabled")
except Exception as e:
    logger.warning(f"Error loading Kokoro TTS: {e}. Audio generation will be disabled")

# Kokoro cache directory
HOME_DIR = Path.home()
KOKORO_CACHE_DIR = HOME_DIR / ".cache" / "kokoro"
KOKORO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Audio output directory
AUDIO_OUTPUT_DIR = Path("audio_output")
AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================================
# DATABASE CONFIGURATION (MONGODB)
# ============================================================================

# Data directory for file storage (not for database)
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

# MongoDB connection details (from settings)
DATABASE_URL = settings.MONGO_URI
DATABASE_NAME = settings.DATABASE_NAME

if DATABASE_URL:
    logger.info(f"Using MongoDB database: {DATABASE_NAME}")
else:
    logger.warning("MONGO_URI not set - database will not be available")

# Backward compatibility - expose settings as module-level variables
APP_TITLE = settings.APP_TITLE
APP_VERSION = settings.APP_VERSION
APP_DESCRIPTION = settings.APP_DESCRIPTION
CORS_ORIGINS = settings.CORS_ORIGINS
CORS_ALLOW_CREDENTIALS = settings.CORS_ALLOW_CREDENTIALS
CORS_ALLOW_METHODS = settings.CORS_ALLOW_METHODS
CORS_ALLOW_HEADERS = settings.CORS_ALLOW_HEADERS
TTS_VOICE = settings.TTS_VOICE
TTS_LANG_CODE = settings.TTS_LANG_CODE
CHATBOT_MODEL = settings.CHATBOT_MODEL
CHATBOT_API_KEY = settings.CHATBOT_API_KEY
TAVILY_API_KEY = settings.TAVILY_API_KEY
GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI = settings.GOOGLE_REDIRECT_URI
SMTP_SERVER = settings.SMTP_SERVER
SMTP_PORT = settings.SMTP_PORT
SENDER_EMAIL = settings.SENDER_EMAIL
SENDER_PASSWORD = settings.SENDER_PASSWORD
ENVIRONMENT = settings.ENVIRONMENT
IS_DEV = settings.IS_DEV

# ============================================================================
# KOKORO TTS CONFIGURATION
# ============================================================================

def configure_kokoro_environment():
    """Configure environment for Kokoro TTS to reduce warnings."""
    if not TTS_AVAILABLE:
        return
    
    try:
        import torch
        torch.set_warn_always(False)
        
        # Suppress specific warnings
        warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.modules.rnn")
        warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.utils.weight_norm")
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="torch")
        warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
        warnings.filterwarnings("ignore", message=".*weight_norm is deprecated.*")
        
        # Configure PyTorch backends
        if hasattr(torch.backends, 'cudnn'):
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except Exception as e:
        logger.warning(f"Error configuring Kokoro environment: {e}")

# Configure Kokoro environment on import
configure_kokoro_environment()

# ============================================================================
# AVAILABLE VOICES
# ============================================================================

# Available Kokoro TTS voices from HuggingFace
# American English (lang_code='a'): af_* (female), am_* (male)
# British English (lang_code='b'): bf_* (female), bm_* (male)
AVAILABLE_VOICES = [
    # American English - Female
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", 
    "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    # American English - Male
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", 
    "am_michael", "am_onyx", "am_puck", "am_santa",
    # British English - Female
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    # British English - Male
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
]

# Voice descriptions for user-friendly display
VOICE_DESCRIPTIONS = {
    # American English - Female
    "af_heart": "American Female - Heart (❤️) - Grade A",
    "af_alloy": "American Female - Alloy - Grade C",
    "af_aoede": "American Female - Aoede - Grade C+",
    "af_bella": "American Female - Bella (🔥) - Grade A-",
    "af_jessica": "American Female - Jessica - Grade D",
    "af_kore": "American Female - Kore - Grade C+",
    "af_nicole": "American Female - Nicole (🎧) - Grade B-",
    "af_nova": "American Female - Nova - Grade C",
    "af_river": "American Female - River - Grade D",
    "af_sarah": "American Female - Sarah - Grade C+",
    "af_sky": "American Female - Sky - Grade C-",
    # American English - Male
    "am_adam": "American Male - Adam - Grade F+",
    "am_echo": "American Male - Echo - Grade D",
    "am_eric": "American Male - Eric - Grade D",
    "am_fenrir": "American Male - Fenrir - Grade C+",
    "am_liam": "American Male - Liam - Grade D",
    "am_michael": "American Male - Michael - Grade C+",
    "am_onyx": "American Male - Onyx - Grade D",
    "am_puck": "American Male - Puck - Grade C+",
    "am_santa": "American Male - Santa - Grade D-",
    # British English - Female
    "bf_alice": "British Female - Alice - Grade D",
    "bf_emma": "British Female - Emma - Grade B-",
    "bf_isabella": "British Female - Isabella - Grade C",
    "bf_lily": "British Female - Lily - Grade D",
    # British English - Male
    "bm_daniel": "British Male - Daniel - Grade D",
    "bm_fable": "British Male - Fable - Grade C",
    "bm_george": "British Male - George - Grade C",
    "bm_lewis": "British Male - Lewis - Grade D+",
}

# ============================================================================
# EXPORT ALL SETTINGS
# ============================================================================

__all__ = [
    # Settings class and instance
    'Settings',
    'settings',
    
    # Environment
    'ENVIRONMENT',
    'IS_DEV',
    'logger',
    
    # API Keys
    'CHATBOT_MODEL',
    'CHATBOT_API_KEY',
    'TAVILY_API_KEY',
    'MODEL_PROVIDER',
    
    # OAuth
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET',
    'GOOGLE_REDIRECT_URI',
    
    # Email
    'SMTP_SERVER',
    'SMTP_PORT',
    'SENDER_EMAIL',
    'SENDER_PASSWORD',
    
    # TTS
    'TTS_AVAILABLE',
    'TTS_ENGINE',
    'TTS_VOICE',
    'TTS_LANG_CODE',
    'KOKORO_CACHE_DIR',
    'AUDIO_OUTPUT_DIR',
    'AVAILABLE_VOICES',
    'VOICE_DESCRIPTIONS',
    'configure_kokoro_environment',
    
    # Database
    'DATA_DIR',
    'DATABASE_URL',
    'DATABASE_NAME',
    
    # Application
    'APP_TITLE',
    'APP_VERSION',
    'APP_DESCRIPTION',
    'CORS_ORIGINS',
    'CORS_ALLOW_CREDENTIALS',
    'CORS_ALLOW_METHODS',
    'CORS_ALLOW_HEADERS',
]

