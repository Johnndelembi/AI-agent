"""Chat controller for handling chat-related endpoints."""
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from src.models.chat import ChatRequest, ChatResponse, ChatHistoryRequest, ChatHistoryResponse
from src.models.auth import User
from src.services.chat_service import ChatService
from src.dependencies import get_chat_service
from src.utils.auth_utils import get_current_active_user
from src.utils.error_handler import handle_http_errors, success_response

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse, summary="Send a chat message")
@handle_http_errors("Error processing message")
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    """
    Send a message to the chatbot and receive a response.
    
    Requires: Valid JWT token in Authorization header.
    
    - **message**: The user's message
    - **thread_id**: Optional conversation thread ID for context (auto-generated if not provided)
    - **user_id**: Ignored - will use authenticated user's ID for security
    """
    # Force user_id to be the authenticated user's ID for security
    response, message_id = await chat_service.send_message(
        message=request.message,
        thread_id=request.thread_id,
        user_id=str(current_user.id)  # Use authenticated user's ID
    )
    return ChatResponse(response=response, thread_id=request.thread_id, message_id=message_id)


@router.post("/history", response_model=ChatHistoryResponse, summary="Get chat history")
@handle_http_errors("Error retrieving history")
async def get_history(
    request: ChatHistoryRequest,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatHistoryResponse:
    """
    Retrieve chat history for a specific thread.
    
    Requires: Valid JWT token in Authorization header.
    Users can only access their own conversations.
    
    - **thread_id**: The conversation thread ID
    """
    messages = await chat_service.get_history(
        thread_id=request.thread_id,
        user_id=str(current_user.id)  # Filter by authenticated user
    )
    return ChatHistoryResponse(thread_id=request.thread_id, messages=messages)


@router.delete("/history/{thread_id}", summary="Delete conversation")
@handle_http_errors("Error deleting conversation")
async def clear_history(
    thread_id: str,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    Delete a conversation completely (including all messages and metadata).
    
    Requires: Valid JWT token in Authorization header.
    Users can only delete their own conversations.
    
    This permanently removes the conversation document from MongoDB and clears
    the LangGraph state. The conversation cannot be recovered after deletion.
    
    - **thread_id**: The conversation thread ID to delete
    """
    await chat_service.clear_history(
        thread_id=thread_id,
        user_id=str(current_user.id)  # Only allow deletion of user's own conversations
    )
    return success_response(f"Conversation {thread_id} deleted successfully")


@router.get("/conversations", summary="List user's conversations")
@handle_http_errors("Error listing conversations")
async def list_conversations(
    limit: int = Query(default=50, le=100, description="Maximum number of conversations to return"),
    skip: int = Query(default=0, ge=0, description="Number of conversations to skip"),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    List conversations for the authenticated user with pagination.
    
    Requires: Valid JWT token in Authorization header.
    Users can only see their own conversations.
    
    - **limit**: Maximum number of conversations to return (max 100)
    - **skip**: Number of conversations to skip (for pagination)
    """
    conversations = await chat_service.list_conversations(
        limit=limit, 
        skip=skip, 
        user_id=str(current_user.id)  # Only show user's own conversations
    )
    return {
        "conversations": conversations,
        "count": len(conversations),
        "limit": limit,
        "skip": skip,
        "user_id": str(current_user.id)
    }


@router.get("/conversations/{thread_id}/stats", summary="Get conversation statistics")
@handle_http_errors("Error getting conversation stats")
async def get_conversation_stats(
    thread_id: str,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    Get statistics for a specific conversation.
    
    Requires: Valid JWT token in Authorization header.
    Users can only access statistics for their own conversations.
    
    - **thread_id**: The conversation thread ID
    """
    stats = await chat_service.get_conversation_stats(
        thread_id=thread_id,
        user_id=str(current_user.id)  # Only allow access to user's own conversations
    )
    return stats

