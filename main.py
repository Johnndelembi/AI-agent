import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.config import settings
from app.api.endpoints import router
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 Starting AI Agent API...")
    
    # Create necessary directories
    os.makedirs(settings.audio_output_dir, exist_ok=True)
    os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(settings.logs_dir, exist_ok=True)
    
    logger.info("✅ AI Agent API started successfully")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down AI Agent API...")

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A comprehensive AI agent API with chat, news, email, and TTS capabilities",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for audio
app.mount("/audio", StaticFiles(directory=settings.audio_output_dir), name="audio")

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["AI Agent"])

@app.get("/api/v1")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to AI Agent API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/info")
async def info():
    """API information endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "model": settings.chatbot_model,
        "tts_available": True,  # Will be checked dynamically
        "features": [
            "Chat with AI agent",
            "News search and analysis",
            "Email functionality",
            "Text-to-speech",
            "Web browsing",
            "Research tools"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    ) 