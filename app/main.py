import asyncio
import signal
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers.chat import router as chat_router
from app.controllers.audio import router as audio_router
from app.controllers.health import router as health_router
from app.controllers.whatsapp import router as whatsapp_router
from app.controllers.celery_monitor import router as celery_router
from app.services.chat_service import ChatService
from app.services.audio_service import AudioService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan - startup and shutdown."""
    # Initialize services
    app.state.chat_service = ChatService()
    app.state.audio_service = AudioService()

    # Graceful shutdown handler
    stop_event = asyncio.Event()

    def _handle_sig():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            pass

    yield

    # Cleanup services
    await app.state.chat_service.shutdown()
    await app.state.audio_service.shutdown()


from app.config import APP_TITLE, APP_VERSION, APP_DESCRIPTION, CORS_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_ALLOW_METHODS, CORS_ALLOW_HEADERS

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

# Include routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(audio_router)
app.include_router(whatsapp_router)
app.include_router(celery_router)
