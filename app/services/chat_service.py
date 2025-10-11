"""Chat service for handling conversational AI logic."""
import asyncio
from typing import List, Dict, Any, Optional

from app.services.agent_service import ConversationalAgent


class ChatService:
    """Service for managing chat conversations with the AI agent."""
    
    def __init__(self):
        """Initialize the chat service."""
        self._agent: Optional[ConversationalAgent] = None
        self._lock = asyncio.Lock()
    
    async def _ensure_agent(self) -> ConversationalAgent:
        """Ensure the agent is initialized (lazy, thread-safe)."""
        if self._agent is None:
            async with self._lock:
                if self._agent is None:
                    # Initialize agent (no executor needed - it's not CPU-bound)
                    self._agent = ConversationalAgent()
        return self._agent
    
    async def send_message(self, message: str, thread_id: str = "default") -> str:
        """
        Send a message to the chatbot and get a response.
        
        Args:
            message: The user's message
            thread_id: Thread ID for conversation context
            
        Returns:
            The chatbot's response
        """
        agent = await self._ensure_agent()
        # Now using native async method!
        return await agent.stream_conversation(message, thread_id=thread_id)
    
    async def get_history(self, thread_id: str = "default") -> List[Dict[str, Any]]:
        """
        Get chat history for a specific thread.
        
        Args:
            thread_id: Thread ID to retrieve history for
            
        Returns:
            List of messages in the conversation
        """
        agent = await self._ensure_agent()
        
        try:
            # Use async get_state if available, otherwise sync is fast enough
            config = {"configurable": {"thread_id": thread_id}}
            state = await agent.graph.aget_state(config)
            
            if state and hasattr(state, 'values') and 'messages' in state.values:
                messages = []
                for msg in state.values['messages']:
                    msg_dict = {
                        'type': msg.__class__.__name__,
                        'content': msg.content if hasattr(msg, 'content') else str(msg)
                    }
                    messages.append(msg_dict)
                return messages
            return []
        except Exception:
            return []
    
    async def clear_history(self, thread_id: str = "default") -> None:
        """
        Clear chat history for a specific thread.
        
        Args:
            thread_id: Thread ID to clear history for
        """
        agent = await self._ensure_agent()
        
        try:
            config = {"configurable": {"thread_id": thread_id}}
            # Use async update_state
            await agent.graph.aupdate_state(config, {"messages": []})
        except Exception as e:
            # If the thread doesn't exist yet, that's fine
            pass
    
    async def is_healthy(self) -> bool:
        """Check if the chat service is healthy."""
        try:
            agent = await self._ensure_agent()
            return agent is not None
        except Exception:
            return False
    
    async def shutdown(self) -> None:
        """Shutdown the chat service and cleanup resources."""
        async with self._lock:
            self._agent = None

