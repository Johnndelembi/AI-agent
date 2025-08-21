from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
import os
from typing import Optional

from app.models.chat import (
    ChatRequest, ChatResponse, NewsRequest, EmailRequest, 
    AudioRequest, AudioResponse, HealthResponse
)
from app.core.agent import agent
from app.services.tts_service import tts_service
from app.services.news_service import news_service
from app.services.email_service import email_service
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        services = {
            "agent": "healthy",
            "tts": "healthy" if tts_service.tts_available else "unavailable",
            "news": "healthy",
            "email": "healthy" if settings.sender_email else "unconfigured"
        }
        
        return HealthResponse(
            status="healthy",
            version=settings.app_version,
            services=services
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Service unhealthy")

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint"""
    try:
        logger.info(f"Chat request received for thread: {request.thread_id}")
        
        # Get response from agent
        response_text = agent.stream_conversation(request.message, request.thread_id)
        
        # Generate audio if requested
        # audio_file = None
        # if request.generate_audio:
        #     try:
        #         audio_files = tts_service.generate_audio(
        #             response_text, 
        #             request.voice, 
        #             request.lang_code
        #         )
        #         if audio_files:
        #             audio_file = os.path.basename(audio_files[0])
        #     except Exception as e:
        #         logger.error(f"Audio generation failed: {e}")
        
        return ChatResponse(
            response=response_text,
            thread_id=request.thread_id,
            # audio_file=audio_file
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @router.post("/news", response_model=str)
# async def search_news_endpoint(request: NewsRequest):
#     """News search endpoint"""
#     try:
#         logger.info(f"News search request: {request.topic} in {request.location}")
        
#         result = news_service.search_news(
#             topic=request.topic,
#             location=request.location,
#             age_group=request.age_group,
#             max_results=request.max_results,
#             time_period=request.time_period
#         )
        
#         return result
        
#     except Exception as e:
#         logger.error(f"News search error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/email/send", response_model=str)
# async def send_email_endpoint(request: EmailRequest):
#     """Send email endpoint"""
#     try:
#         logger.info(f"Email request for: {request.recipient_email}")
        
#         result = email_service.send_daily_news_email(
#             recipient_email=request.recipient_email,
#             news_topics=request.news_topics,
#             custom_content=request.custom_content
#         )
        
#         return result
        
#     except Exception as e:
#         logger.error(f"Email error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/email/schedule", response_model=str)
# async def schedule_email_endpoint(request: EmailRequest):
#     """Schedule email endpoint"""
#     try:
#         logger.info(f"Email schedule request for: {request.recipient_email}")
        
#         result = email_service.setup_daily_news_schedule(
#             recipient_email=request.recipient_email,
#             time=request.time,
#             include_tanzania=request.include_tanzania,
#             include_tech=request.include_tech
#         )
        
#         return result
        
#     except Exception as e:
#         logger.error(f"Email schedule error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/audio", response_model=AudioResponse)
# async def generate_audio_endpoint(request: AudioRequest):
#     """Audio generation endpoint"""
#     try:
#         logger.info(f"Audio generation request for {len(request.text)} characters")
        
#         audio_files = tts_service.generate_audio(
#             request.text,
#             request.voice,
#             request.lang_code
#         )
        
#         if not audio_files:
#             raise HTTPException(status_code=500, detail="Failed to generate audio")
        
#         audio_file = os.path.basename(audio_files[0])
#         voice_used = request.voice or tts_service.voice
        
#         return AudioResponse(
#             audio_file=audio_file,
#             text_length=len(request.text),
#             voice_used=voice_used
#         )
        
#     except Exception as e:
#         logger.error(f"Audio generation error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/audio/{filename}")
# async def get_audio_file(filename: str):
#     """Serve audio files"""
#     try:
#         audio_path = os.path.join(settings.audio_output_dir, filename)
        
#         if not os.path.exists(audio_path):
#             raise HTTPException(status_code=404, detail="Audio file not found")
        
#         return FileResponse(audio_path, media_type="audio/wav")
        
#     except Exception as e:
#         logger.error(f"Audio file serve error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/state/{thread_id}")
# async def get_conversation_state(thread_id: str):
#     """Get conversation state for debugging"""
#     try:
#         state = agent.get_state_snapshot(thread_id)
#         return state
        
#     except Exception as e:
#         logger.error(f"State retrieval error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/tools/literature-review")
# async def generate_literature_review_endpoint(topic: str):
#     """Generate literature review endpoint"""
#     try:
#         from app.tools.chat_tools import generate_literature_review
#         result = generate_literature_review.invoke({"topic": topic})
#         return {"result": result}
        
#     except Exception as e:
#         logger.error(f"Literature review error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/tools/research-methodology")
# async def generate_research_methodology_endpoint(topic: str):
#     """Generate research methodology endpoint"""
#     try:
#         from app.tools.chat_tools import generate_research_methodology
#         result = generate_research_methodology.invoke({"topic": topic})
#         return {"result": result}
        
#     except Exception as e:
#         logger.error(f"Research methodology error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/tools/study-plan")
# async def generate_study_plan_endpoint(subject: str):
#     """Generate study plan endpoint"""
#     try:
#         from app.tools.chat_tools import generate_study_plan
#         result = generate_study_plan.invoke({"subject": subject})
#         return {"result": result}
        
#     except Exception as e:
#         logger.error(f"Study plan error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/tools/browse-web")
# async def browse_web_endpoint(url: str):
#     """Browse web page endpoint"""
#     try:
#         from app.tools.chat_tools import browse_web_page
#         result = browse_web_page.invoke({"url": url})
#         return {"result": result}
        
#     except Exception as e:
#         logger.error(f"Web browse error: {e}")
#         raise HTTPException(status_code=500, detail=str(e)) 