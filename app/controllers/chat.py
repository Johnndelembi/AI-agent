"""Chat controller for handling chat-related endpoints."""
from fastapi import APIRouter, Depends
from typing import List

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
    - **thread_id**: Optional conversation thread ID for context
    """
    response = await chat_service.send_message(
        message=request.message,
        thread_id=request.thread_id
    )
    return ChatResponse(response=response, thread_id=request.thread_id)


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


@router.delete("/history/{thread_id}", summary="Clear chat history")
@handle_http_errors("Error clearing history")
async def clear_history(
    thread_id: str,
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    Clear chat history for a specific thread.
    
    - **thread_id**: The conversation thread ID to clear
    """
    await chat_service.clear_history(thread_id=thread_id)
    return success_response(f"History cleared for thread {thread_id}")

