"""
Database service for managing MongoDB connections and operations.
Handles MongoEngine connection setup and context management.
"""

import logging
from mongoengine import connect, disconnect
from typing import Optional
from contextlib import contextmanager

from app.config import settings, logger

# Connection tracking
_connection = None
_is_connected = False


def connect_db():
    """
    Connect to MongoDB using MongoEngine.
    
    Returns:
        Connection object or None on error
    """
    global _connection, _is_connected
    
    if _is_connected:
        logger.info("MongoDB already connected")
        return _connection
    
    try:
        if not settings.MONGO_URI:
            logger.error("MONGO_URI not set in environment variables")
            return None
        
        # Connect to MongoDB
        # Increase timeouts to handle DNS resolution issues
        _connection = connect(
            db=settings.DATABASE_NAME,
            host=settings.MONGO_URI,
            alias='default',
            serverSelectionTimeoutMS=30000,  # 30 second timeout (increased for DNS issues)
            connectTimeoutMS=30000,  # 30 second connection timeout
            socketTimeoutMS=60000,  # 60 second socket timeout
            retryWrites=True,
            w='majority',  # Write concern
            # Additional connection options for better reliability
            maxPoolSize=10,
            minPoolSize=1,
            maxIdleTimeMS=45000,
            waitQueueTimeoutMS=10000
        )
        
        _is_connected = True
        logger.info(f"MongoDB connected successfully to database: {settings.DATABASE_NAME}")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        
        return _connection
        
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        _is_connected = False
        return None


def disconnect_db():
    """
    Disconnect from MongoDB.
    """
    global _connection, _is_connected
    
    try:
        disconnect(alias='default')
        _connection = None
        _is_connected = False
        logger.info("MongoDB disconnected successfully")
    except Exception as e:
        logger.error(f"Error disconnecting from MongoDB: {e}")


def is_connected() -> bool:
    """
    Check if MongoDB is connected.
    
    Returns:
        True if connected, False otherwise
    """
    global _is_connected
    
    if not _is_connected:
        return False
    
    # Verify connection is actually working by checking if we can access the database
    try:
        from mongoengine.connection import get_connection
        conn = get_connection(alias='default')
        # Try to ping the database to verify connection (without requiring models)
        # Use the database's command method directly to avoid model registration issues
        db = conn[conn.name]
        db.command('ping')
        return True
    except Exception:
        # Connection exists but is not working, reset flag
        _is_connected = False
        return False


def ensure_connection():
    """
    Ensure MongoDB connection is established.
    This is useful for Celery workers that may not have inherited the connection.
    
    Returns:
        True if connected, False otherwise
    """
    if is_connected():
        return True
    
    return connect_db() is not None


@contextmanager
def get_db():
    """
    Context manager for MongoDB operations (for FastAPI dependency injection).
    Note: With MongoEngine, we don't need to manage sessions like SQLAlchemy.
    This is kept for API compatibility.
    
    Yields:
        None (MongoEngine handles connection pooling automatically)
    """
    if not _is_connected:
        connect_db()
    
    try:
        yield None  # MongoEngine handles connections automatically
    except Exception as e:
        logger.error(f"Error in database operation: {e}")
        raise


def get_db_connection():
    """
    Get MongoDB connection (for FastAPI dependencies).
    Ensures connection is established.
    
    Returns:
        Connection status (bool)
    """
    if not _is_connected:
        connect_db()
    return _is_connected


def setup_database():
    """
    Setup MongoDB connection and ensure indexes are created.
    This function is called on module import.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        connection = connect_db()
        
        if connection:
            # Import models to ensure indexes are created
            from ..models.database import (
                Employee, MealSelection, MealReminder, MealOptions, 
                Conversation
            )
            from ..models.auth import (
                User, OTPVerification, PasswordResetToken
            )
            
            # Ensure indexes are created for all models
            logger.info("Ensuring MongoDB indexes...")
            try:
                # Drop conflicting legacy indexes if they exist
                from mongoengine.connection import get_db
                db = get_db(alias='default')
                try:
                    db['users'].drop_index('email_1')
                except Exception:
                    pass
                try:
                    db['otp_verifications'].drop_index('email_1')
                except Exception:
                    pass
                try:
                    db['password_reset_tokens'].drop_index('token_1')
                except Exception:
                    pass

                # Now ensure indexes
                MealSelection.ensure_indexes()
                MealReminder.ensure_indexes()
                MealOptions.ensure_indexes()
                Conversation.ensure_indexes()
                User.ensure_indexes()
                OTPVerification.ensure_indexes()
                PasswordResetToken.ensure_indexes()
                logger.info("MongoDB indexes ensured successfully")
            except Exception as index_error:
                logger.warning(f"Some indexes could not be created: {index_error}")
                # Don't fail the entire setup for index issues
            
            return True
        else:
            logger.warning("MongoDB connection not established during setup")
            return False
            
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False


# Initialize database on module import
setup_database()

