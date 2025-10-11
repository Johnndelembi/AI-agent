"""FastAPI dependencies for dependency injection."""
from fastapi import Request

from app.services.chat_service import ChatService
from app.services.audio_service import AudioService
from app.services.database_service import get_db, is_connected


def get_chat_service(request: Request) -> ChatService:
    """
    Get the ChatService instance from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        ChatService instance
    """
    return request.app.state.chat_service


def get_audio_service(request: Request) -> AudioService:
    """
    Get the AudioService instance from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        AudioService instance
    """
    return request.app.state.audio_service


def get_database():
    """
    Get database connection status for dependency injection.
    Note: With MongoEngine, connections are managed automatically.
    This dependency ensures the database is connected.
    
    Yields:
        None (MongoEngine handles connections automatically)
    """
    # Ensure database is connected
    with get_db():
        yield


def check_db_connection() -> bool:
    """
    Check if database is connected.
    
    Returns:
        True if connected, False otherwise
    """
    return is_connected()

