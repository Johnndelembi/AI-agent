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
    # RECOMMENDATION SERVICE CONFIGURATION
    # ============================================================================
    MIPANGO_DATABASE: str = os.getenv("MIPANGO_DATABASE", "postgresql://postgres:[YOUR_PASSWORD]@db.rpliwcovzmxtliybkkva.supabase.co:5432/postgres")
    
    # ============================================================================
    # API KEYS
    # ============================================================================
    # Chatbot API configuration
    CHATBOT_MODEL: str = os.getenv("CHATBOT_MODEL", "openai:gpt-4")
    CHATBOT_API_KEY: str = os.getenv("CHATBOT_API_KEY", "")
    # OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
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
SMTP_SERVER = settings.SMTP_SERVER
SMTP_PORT = settings.SMTP_PORT
SENDER_EMAIL = settings.SENDER_EMAIL
SENDER_PASSWORD = settings.SENDER_PASSWORD
ENVIRONMENT = settings.ENVIRONMENT
IS_DEV = settings.IS_DEV
MIPANGO_DATABASE = settings.MIPANGO_DATABASE



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
    'configure_kokoro_environment',
    
    # Database
    'DATA_DIR',
    'DATABASE_URL',
    'DATABASE_NAME',
    'MIPANGO_DATABASE',
    
    # Application
    'APP_TITLE',
    'APP_VERSION',
    'APP_DESCRIPTION',
    'CORS_ORIGINS',
    'CORS_ALLOW_CREDENTIALS',
    'CORS_ALLOW_METHODS',
    'CORS_ALLOW_HEADERS',
]

