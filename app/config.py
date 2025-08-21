import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings and configuration"""
    
    # API Configuration
    app_name: str = "AI Agent API"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Model Configuration
    chatbot_model: str = os.getenv("CHATBOT_MODEL", "openai:gpt-4")
    chatbot_api_key: str = os.getenv("CHATBOT_API_KEY", "")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    
    # TTS Configuration
    tts_voice: str = os.getenv("TTS_VOICE", "af_heart")
    tts_lang_code: str = os.getenv("TTS_LANG_CODE", "b")
    
    # Email Configuration
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    sender_email: Optional[str] = os.getenv("SENDER_EMAIL")
    sender_password: Optional[str] = os.getenv("SENDER_PASSWORD")
    
    # Environment
    environment: str = os.getenv("ENV", "production")
    
    # File paths
    audio_output_dir: str = "audio_output"
    data_dir: str = "data"
    logs_dir: str = "logs"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()

# Validate required settings
def validate_settings():
    """Validate that required settings are present"""
    if not settings.chatbot_api_key and settings.environment != "dev":
        raise ValueError("CHATBOT_API_KEY environment variable is required")
    
    if not settings.tavily_api_key and settings.environment != "dev":
        raise ValueError("TAVILY_API_KEY environment variable is required")

# Set environment variables for different model providers
def setup_model_environment():
    """Setup environment variables for the selected model provider"""
    if settings.chatbot_model.startswith("openai:"):
        os.environ["OPENAI_API_KEY"] = settings.chatbot_api_key
        return "openai"
    elif settings.chatbot_model.startswith("anthropic:"):
        os.environ["ANTHROPIC_API_KEY"] = settings.chatbot_api_key
        return "anthropic"
    elif settings.chatbot_model.startswith("google:"):
        os.environ["GOOGLE_API_KEY"] = settings.chatbot_api_key
        return "google_genai"
    else:
        # Default fallback to OpenAI
        os.environ["OPENAI_API_KEY"] = settings.chatbot_api_key
        return "openai"

# Set Tavily API key
os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

# Initialize settings
validate_settings()
MODEL_PROVIDER = setup_model_environment() 