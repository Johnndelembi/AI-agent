import asyncio
import signal
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .api import router as api_router
from .agent_service import AgentService
from .cache import AsyncCache


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialize shared services
    app.state.agent_service = AgentService()
    app.state.cache = AsyncCache()
    await app.state.cache.connect()

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _handle_sig():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            pass

    yield

    await app.state.agent_service.shutdown()
    await app.state.cache.close()


app = FastAPI(
    title="AI Agent API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Mount API (single endpoint exposed by router)
app.include_router(api_router)
