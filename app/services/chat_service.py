"""Chat service for handling conversational AI logic."""
import asyncio
import re
from typing import AsyncIterator, List, Dict, Any, Optional

from app.services.agent_service import ConversationalAgent
from app.models.database import Conversation
from app.config import logger
from app.services.file_service import file_service


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
    
    async def send_message(
        self,
        message: str,
        thread_id: str = "default",
        user_id: Optional[str] = None,
        attachment_ids: Optional[List[str]] = None,
    ) -> tuple[str, str, Dict[str, Any]]:
        """
        Send a message to the chatbot and get a response.
        
        Args:
            message: The user's message
            thread_id: Thread ID for conversation context
            user_id: Required user identifier for security
            
        Returns:
            Tuple of (chatbot's response, message_id, message metadata)
        """
        if not user_id:
            raise ValueError("user_id is required for security")
        
        try:
            # Get or create conversation in MongoDB
            conversation = await asyncio.to_thread(
                Conversation.get_or_create,
                thread_id=thread_id,
                user_id=user_id
            )
            
            attachment_payloads = []
            if attachment_ids:
                attachment_payloads = await asyncio.to_thread(
                    file_service.build_attachment_payloads,
                    user_id,
                    attachment_ids,
                )

            # Store user message in MongoDB
            _, user_msg_id = await asyncio.to_thread(
                conversation.add_message,
                role='user',
                content=message,
                metadata={"attachments": attachment_payloads} if attachment_payloads else {},
            )
            
            # Get AI response
            agent = await self._ensure_agent()
            agent_result = await agent.stream_conversation(
                message,
                thread_id=thread_id,
                user_id=user_id,
                attachments=attachment_payloads,
            )
            response = agent_result["response"]
            response_metadata = agent_result.get("metadata", {})
            
            # Store assistant response in MongoDB and get its message_id
            _, assistant_msg_id = await asyncio.to_thread(
                conversation.add_message,
                role='assistant',
                content=response,
                metadata=response_metadata,
            )
            
            return response, assistant_msg_id, response_metadata
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            # If MongoDB fails, still try to get response from agent
            from uuid import uuid4
            agent = await self._ensure_agent()
            agent_result = await agent.stream_conversation(
                message,
                thread_id=thread_id,
                user_id=user_id,
                attachments=[],
            )
            return agent_result["response"], str(uuid4()), agent_result.get("metadata", {})

    async def stream_message(
        self,
        message: str,
        thread_id: str = "default",
        user_id: Optional[str] = None,
        attachment_ids: Optional[List[str]] = None,
    ) -> AsyncIterator[str]:
        """Generate a streamed text response for AI SDK text transport."""
        if not user_id:
            raise ValueError("user_id is required for security")

        try:
            conversation = await asyncio.to_thread(
                Conversation.get_or_create,
                thread_id=thread_id,
                user_id=user_id,
            )

            attachment_payloads = []
            if attachment_ids:
                attachment_payloads = await asyncio.to_thread(
                    file_service.build_attachment_payloads,
                    user_id,
                    attachment_ids,
                )

            await asyncio.to_thread(
                conversation.add_message,
                role="user",
                content=message,
                metadata={"attachments": attachment_payloads} if attachment_payloads else {},
            )

            agent = await self._ensure_agent()
            agent_result = await agent.stream_conversation(
                message,
                thread_id=thread_id,
                user_id=user_id,
                attachments=attachment_payloads,
            )
            response = agent_result["response"]
            response_metadata = agent_result.get("metadata", {})

            await asyncio.to_thread(
                conversation.add_message,
                role="assistant",
                content=response,
                metadata=response_metadata,
            )
        except Exception as exc:
            logger.error(f"Error in stream_message: {exc}")
            response = f"Unable to complete the request: {exc}"

        async def _generator() -> AsyncIterator[str]:
            for chunk in self._chunk_text(response):
                yield chunk
                await asyncio.sleep(0)

        return _generator()

    def _chunk_text(self, text: str, target_size: int = 48) -> List[str]:
        """Split text into reasonably sized chunks for incremental delivery."""
        pieces = re.split(r"(\s+)", text)
        chunks: List[str] = []
        buffer = ""

        for piece in pieces:
            if not piece:
                continue
            if len(buffer) + len(piece) > target_size and buffer:
                chunks.append(buffer)
                buffer = piece
            else:
                buffer += piece

        if buffer:
            chunks.append(buffer)

        return chunks or [text]
    
    async def get_history(self, thread_id: str = "default", user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get chat history for a specific thread from MongoDB.
        
        Args:
            thread_id: Thread ID to retrieve history for
            user_id: Required user identifier for security
            
        Returns:
            List of messages in the conversation
        """
        if not user_id:
            raise ValueError("user_id is required for security")
        
        try:
            # Try to get from MongoDB first, filtered by user
            conversation = await asyncio.to_thread(
                lambda: Conversation.objects(thread_id=thread_id, user_id=user_id).first()
            )
            
            if conversation:
                return conversation.get_messages_dict()
            
            # If not in MongoDB, try LangGraph state (for backward compatibility)
            agent = await self._ensure_agent()
            config = {"configurable": {"thread_id": thread_id}}
            state = await agent.graph.aget_state(config)
            
            if state and hasattr(state, 'values') and 'messages' in state.values:
                messages = []
                for msg in state.values['messages']:
                    msg_dict = {
                        'type': msg.__class__.__name__,
                        'content': msg.content if hasattr(msg, 'content') else str(msg),
                        'timestamp': None
                    }
                    messages.append(msg_dict)
                return messages
            
            return []
        except Exception as e:
            logger.error(f"Error in get_history: {e}")
            return []
    
    async def clear_history(self, thread_id: str = "default", user_id: Optional[str] = None) -> None:
        """
        Delete conversation completely from MongoDB and clear LangGraph state.
        
        Args:
            thread_id: Thread ID to delete
            user_id: Required user identifier for security
        """
        if not user_id:
            raise ValueError("user_id is required for security")
        
        try:
            # Delete the entire conversation document from MongoDB, filtered by user
            deleted_count = await asyncio.to_thread(
                lambda: Conversation.objects(thread_id=thread_id, user_id=user_id).delete()
            )
            
            if deleted_count > 0:
                logger.info(f"Deleted conversation document for thread {thread_id}")
            else:
                logger.info(f"No conversation found for thread {thread_id}")
            
            # Also clear from LangGraph state (for backward compatibility)
            agent = await self._ensure_agent()
            config = {"configurable": {"thread_id": thread_id}}
            await agent.graph.aupdate_state(config, {"messages": []})
            
            logger.info(f"Cleared history and deleted conversation for thread {thread_id}")
        except Exception as e:
            logger.error(f"Error in clear_history: {e}")
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
    
    async def list_conversations(
        self, 
        limit: int = 50, 
        skip: int = 0, 
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List conversations with pagination and user filtering.
        
        Args:
            limit: Maximum number of conversations to return
            skip: Number of conversations to skip
            user_id: Required user identifier for security
            
        Returns:
            List of conversation summaries
        """
        if not user_id:
            raise ValueError("user_id is required for security")
        
        try:
            def get_conversations():
                # Always filter by user_id for security
                query = Conversation.objects(user_id=user_id)
                
                conversations = query.order_by('-updated_at').skip(skip).limit(limit)
                
                return [
                    {
                        'thread_id': conv.thread_id,
                        'user_id': conv.user_id,
                        'title': conv.title,
                        'message_count': conv.message_count,
                        'created_at': conv.created_at.isoformat() if conv.created_at else None,
                        'updated_at': conv.updated_at.isoformat() if conv.updated_at else None,
                        'last_message_at': conv.last_message_at.isoformat() if conv.last_message_at else None,
                        'is_active': conv.is_active,
                        'is_archived': conv.is_archived,
                        'tags': conv.tags
                    }
                    for conv in conversations
                ]
            
            return await asyncio.to_thread(get_conversations)
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []
    
    async def get_message(self, thread_id: str, message_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a specific message by thread_id and message_id.
        
        Args:
            thread_id: Thread ID
            message_id: Message ID
            user_id: Required user identifier for security
            
        Returns:
            Message dict or None if not found
        """
        if not user_id:
            raise ValueError("user_id is required for security")
        
        try:
            conversation = await asyncio.to_thread(
                lambda: Conversation.objects(thread_id=thread_id, user_id=user_id).first()
            )
            
            if not conversation:
                logger.warning(f"Conversation not found: {thread_id}")
                return None
            
            message = conversation.get_message_by_id(message_id)
            if not message:
                logger.warning(f"Message not found: {message_id} in thread {thread_id}")
            
            return message
        except Exception as e:
            logger.error(f"Error getting message: {e}")
            return None
    
    async def update_message_audio(self, thread_id: str, message_id: str, audio_url: str, user_id: Optional[str] = None) -> bool:
        """
        Update a message to mark that audio has been generated.
        
        Args:
            thread_id: Thread ID
            message_id: Message ID
            audio_url: URL/path to the generated audio
            user_id: Required user identifier for security
            
        Returns:
            True if updated, False otherwise
        """
        if not user_id:
            raise ValueError("user_id is required for security")
        
        try:
            conversation = await asyncio.to_thread(
                lambda: Conversation.objects(thread_id=thread_id, user_id=user_id).first()
            )
            
            if not conversation:
                logger.warning(f"Conversation not found: {thread_id}")
                return False
            
            updated = await asyncio.to_thread(
                conversation.update_message_audio,
                message_id,
                audio_url
            )
            
            return updated
        except Exception as e:
            logger.error(f"Error updating message audio: {e}")
            return False
    
    async def get_conversation_stats(self, thread_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for a specific conversation.
        
        Args:
            thread_id: Thread ID to get stats for
            user_id: Required user identifier for security
            
        Returns:
            Dictionary with conversation statistics
        """
        if not user_id:
            raise ValueError("user_id is required for security")
        
        try:
            conversation = await asyncio.to_thread(
                lambda: Conversation.objects(thread_id=thread_id, user_id=user_id).first()
            )
            
            if not conversation:
                return {
                    'thread_id': thread_id,
                    'exists': False,
                    'message': 'Conversation not found'
                }
            
            user_messages = sum(1 for msg in conversation.messages if msg.role in ['user', 'human'])
            assistant_messages = sum(1 for msg in conversation.messages if msg.role in ['assistant', 'ai'])
            
            total_user_chars = sum(len(msg.content) for msg in conversation.messages if msg.role in ['user', 'human'])
            total_assistant_chars = sum(len(msg.content) for msg in conversation.messages if msg.role in ['assistant', 'ai'])
            
            return {
                'thread_id': thread_id,
                'exists': True,
                'user_id': conversation.user_id,
                'title': conversation.title,
                'message_count': conversation.message_count,
                'user_messages': user_messages,
                'assistant_messages': assistant_messages,
                'total_user_characters': total_user_chars,
                'total_assistant_characters': total_assistant_chars,
                'created_at': conversation.created_at.isoformat() if conversation.created_at else None,
                'updated_at': conversation.updated_at.isoformat() if conversation.updated_at else None,
                'last_message_at': conversation.last_message_at.isoformat() if conversation.last_message_at else None,
                'is_active': conversation.is_active,
                'is_archived': conversation.is_archived,
                'tags': conversation.tags,
                'category': conversation.category
            }
        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {
                'thread_id': thread_id,
                'exists': False,
                'error': str(e)
            }
