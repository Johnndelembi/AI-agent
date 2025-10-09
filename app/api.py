from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .agent_service import AgentService
from .cache import AsyncCache

router = APIRouter()


class MessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    response: str


class MessageController:
    def __init__(self, agent: AgentService, cache: AsyncCache):
        self.agent = agent
        self.cache = cache

    async def post_message(self, payload: MessageRequest) -> MessageResponse:
        cache_key = f"msg:{hash(payload.message)}"
        cached = await self.cache.get(cache_key)
        if cached:
            return MessageResponse(response=cached)

        reply = await self.agent.ask(payload.message)
        await self.cache.set(cache_key, reply, ttl_seconds=300)
        return MessageResponse(response=reply)


# Dependency providers
_agent_service: AgentService | None = None
_cache: AsyncCache | None = None


async def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


async def get_cache() -> AsyncCache:
    global _cache
    if _cache is None:
        from os import getenv
        redis_url = getenv("REDIS_URL")
        _cache = AsyncCache(redis_url=redis_url)
        await _cache.connect()
    return _cache


@router.post("/message", response_model=MessageResponse, tags=["message"], summary="Send a message and receive a response")
async def post_message(payload: MessageRequest, agent: AgentService = Depends(get_agent_service), cache: AsyncCache = Depends(get_cache)) -> MessageResponse:
    controller = MessageController(agent=agent, cache=cache)
    return await controller.post_message(payload)
