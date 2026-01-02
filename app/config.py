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
    APP_NAME: str = os.getenv('APP_NAME', 'Artemis - AI Assistant')
    FRONTEND_URL: str = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
    
    # ============================================================================
    # APPLICATION SETTINGS
    # ============================================================================
    APP_TITLE: str = "AI Agent API"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "FastAPI-based conversational AI assistant with email service"
    
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
# EMAIL CONFIGURATION
# ============================================================================
# Email configuration is handled in Settings class above
# Google SMTP settings are configured via environment variables

# ============================================================================
# AUDIO OUTPUT DIRECTORY (for cleanup tasks)
# ============================================================================
# Audio output directory (used for temporary file cleanup)
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
APP_NAME = settings.APP_NAME
FRONTEND_URL = settings.FRONTEND_URL
ENVIRONMENT = settings.ENVIRONMENT
IS_DEV = settings.IS_DEV


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
    'APP_NAME',
    'FRONTEND_URL',
    
    # Audio (for cleanup tasks)
    'AUDIO_OUTPUT_DIR',
    
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

