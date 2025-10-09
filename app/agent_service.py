import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from basic_chatbot import ConversationalAgent


class AgentService:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent")
        self._agent: Optional[ConversationalAgent] = None
        self._lock = asyncio.Lock()

    async def _ensure_agent(self) -> ConversationalAgent:
        if self._agent is None:
            async with self._lock:
                if self._agent is None:
                    # Initialize in thread to avoid blocking event loop
                    loop = asyncio.get_running_loop()
                    self._agent = await loop.run_in_executor(self._executor, ConversationalAgent)
        return self._agent  # type: ignore[return-value]

    async def ask(self, message: str, thread_id: str = "api-thread") -> str:
        agent = await self._ensure_agent()
        loop = asyncio.get_running_loop()
        # Run the potentially blocking stream in the thread pool
        def _invoke() -> str:
            return agent.stream_conversation(message, thread_id=thread_id)
        return await loop.run_in_executor(self._executor, _invoke)

    async def shutdown(self) -> None:
        async with self._lock:
            self._agent = None
        self._executor.shutdown(wait=False, cancel_futures=True)
