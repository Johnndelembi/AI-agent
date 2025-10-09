import asyncio
from typing import Optional, Any

try:
    import aioredis  # type: ignore
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore


class AsyncCache:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self._redis = None
        self._memory: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.redis_url and aioredis:
            try:
                self._redis = await aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
            except Exception:
                self._redis = None

    async def get(self, key: str) -> Optional[str]:
        if self._redis:
            try:
                return await self._redis.get(key)
            except Exception:
                pass
        async with self._lock:
            return self._memory.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        if self._redis:
            try:
                await self._redis.set(key, value, ex=ttl_seconds)
                return
            except Exception:
                pass
        async with self._lock:
            self._memory[key] = value

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
