"""Chat controller for handling chat-related endpoints."""
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.models.chat import ChatRequest, ChatResponse, ChatHistoryRequest, ChatHistoryResponse
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service
from app.utils.error_handler import handle_http_errors, success_response

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse, summary="Send a chat message")
@handle_http_errors("Error processing message")
async def send_message(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    """
    Send a message to the chatbot and receive a response.
    
    - **message**: The user's message
    - **thread_id**: Optional conversation thread ID for context (auto-generated if not provided)
    - **user_id**: Optional user identifier for tracking
    """
    response, message_id = await chat_service.send_message(
        message=request.message,
        thread_id=request.thread_id,
        user_id=request.user_id
    )
    return ChatResponse(response=response, thread_id=request.thread_id, message_id=message_id)


@router.post("/history", response_model=ChatHistoryResponse, summary="Get chat history")
@handle_http_errors("Error retrieving history")
async def get_history(
    request: ChatHistoryRequest,
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatHistoryResponse:
    """
    Retrieve chat history for a specific thread.
    
    - **thread_id**: The conversation thread ID
    """
    messages = await chat_service.get_history(thread_id=request.thread_id)
    return ChatHistoryResponse(thread_id=request.thread_id, messages=messages)


@router.delete("/history/{thread_id}", summary="Delete conversation")
@handle_http_errors("Error deleting conversation")
async def clear_history(
    thread_id: str,
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    Delete a conversation completely (including all messages and metadata).
    
    This permanently removes the conversation document from MongoDB and clears
    the LangGraph state. The conversation cannot be recovered after deletion.
    
    - **thread_id**: The conversation thread ID to delete
    """
    await chat_service.clear_history(thread_id=thread_id)
    return success_response(f"Conversation {thread_id} deleted successfully")


@router.get("/conversations", summary="List all conversations")
@handle_http_errors("Error listing conversations")
async def list_conversations(
    limit: int = Query(default=50, le=100, description="Maximum number of conversations to return"),
    skip: int = Query(default=0, ge=0, description="Number of conversations to skip"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    List all conversations with pagination and optional user filtering.
    
    - **limit**: Maximum number of conversations to return (max 100)
    - **skip**: Number of conversations to skip (for pagination)
    - **user_id**: Optional filter by user ID
    """
    conversations = await chat_service.list_conversations(limit=limit, skip=skip, user_id=user_id)
    return {
        "conversations": conversations,
        "count": len(conversations),
        "limit": limit,
        "skip": skip
    }


@router.get("/conversations/{thread_id}/stats", summary="Get conversation statistics")
@handle_http_errors("Error getting conversation stats")
async def get_conversation_stats(
    thread_id: str,
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    Get statistics for a specific conversation.
    
    - **thread_id**: The conversation thread ID
    """
    stats = await chat_service.get_conversation_stats(thread_id=thread_id)
    return stats

