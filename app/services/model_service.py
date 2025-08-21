from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings, MODEL_PROVIDER
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class ModelService:
    """Service for managing different LLM providers"""
    
    def __init__(self):
        self.model_name = settings.chatbot_model
        self.provider = MODEL_PROVIDER
        self._model_cache = {}
    
    def get_model(self, model_name: Optional[str] = None, provider: Optional[str] = None) -> ChatOpenAI | ChatAnthropic | ChatGoogleGenerativeAI:
        """Get or create a chat model instance"""
        model_to_use = model_name or self.model_name
        provider_to_use = provider or self.provider
        
        cache_key = f"{provider_to_use}:{model_to_use}"
        
        if cache_key not in self._model_cache:
            logger.info(f"Initializing {provider_to_use} model: {model_to_use}")
            self._model_cache[cache_key] = self._create_model(model_to_use, provider_to_use)
        
        return self._model_cache[cache_key]
    
    def _create_model(self, model_name: str, provider: str):
        """Create a new model instance based on provider"""
        try:
            if provider == "openai":
                model_clean = model_name.replace("openai:", "")
                return ChatOpenAI(model=model_clean)
            elif provider == "anthropic":
                model_clean = model_name.replace("anthropic:", "")
                return ChatAnthropic(model=model_clean)
            elif provider == "google_genai":
                model_clean = model_name.replace("google:", "")
                return ChatGoogleGenerativeAI(model=model_clean)
            else:
                # Default to OpenAI
                model_clean = model_name.replace("openai:", "")
                logger.warning(f"Unknown provider {provider}, using OpenAI as default")
                return ChatOpenAI(model=model_clean)
        except Exception as e:
            logger.error(f"Error creating model {model_name} with provider {provider}: {e}")
            raise
    
    def get_default_model(self):
        """Get the default configured model"""
        return self.get_model()

# Global model service instance
model_service = ModelService() 