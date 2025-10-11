"""WhatsApp webhook controller."""
from fastapi import APIRouter, Request, Query, Depends
from typing import Optional
import logging

from app.services.chat_service import ChatService
from app.dependencies import get_chat_service
from app.utils.error_handler import create_400_error, create_403_error, error_response, success_response

router = APIRouter(prefix="/v1/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)


@router.get("/webhook", summary="WhatsApp webhook verification")
async def verify_webhook(
    request: Request,
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """
    Verify WhatsApp webhook endpoint.
    
    Facebook/Meta sends a verification request to this endpoint
    when you set up a webhook in the WhatsApp Business API.
    """
    logger.info(f"Webhook verification request: mode={mode}, token={token}")
    
    # Get verification token from environment or config
    # For now, accept any token (you should validate this in production)
    VERIFY_TOKEN = "your_verify_token_here"  # TODO: Move to environment variable
    
    if mode == "subscribe" and token:
        # Verify token matches
        if token == VERIFY_TOKEN or True:  # TODO: Remove "or True" in production
            logger.info("Webhook verified successfully")
            return int(challenge) if challenge else success_response("Webhook verified")
        else:
            logger.warning("Invalid verification token")
            raise create_403_error("Verification token mismatch")
    
    logger.warning("Invalid verification request")
    raise create_400_error("Invalid verification request")


@router.post("/message/{message_id}", summary="Receive WhatsApp message")
async def receive_message(
    message_id: str,
    request: Request,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Receive incoming WhatsApp webhook messages.
    
    This endpoint receives webhook notifications from WhatsApp Business API.
    """
    try:
        # Get the raw payload
        payload = await request.json()
        logger.info(f"Received WhatsApp webhook for message {message_id}: {payload}")
        
        # Parse WhatsApp webhook structure
        # Typical structure: { "object": "whatsapp_business_account", "entry": [...] }
        
        if not isinstance(payload, dict):
            logger.warning(f"Invalid payload format: {payload}")
            return error_response("Invalid payload")
        
        # Extract message data
        entries = payload.get("entry", [])
        if not entries:
            logger.info("No entries in webhook, likely a status update")
            return success_response("Webhook received")
        
        # Process each entry
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message in messages:
                    from_number = message.get("from", "unknown")
                    msg_text = message.get("text", {}).get("body", "")
                    msg_id = message.get("id", message_id)
                    
                    if msg_text:
                        logger.info(f"Processing message from {from_number}: {msg_text}")
                        
                        # Process the message through chat service
                        # Use phone number as thread_id to maintain conversation context
                        thread_id = f"whatsapp_{from_number}"
                        
                        try:
                            response = await chat_service.send_message(
                                message=msg_text,
                                thread_id=thread_id
                            )
                            
                            logger.info(f"Generated response for {from_number}: {response[:100]}...")
                            
                            # TODO: Send response back to WhatsApp using their API
                            # For now, just log it
                            return success_response(
                                "Message processed",
                                message_id=msg_id,
                                response=response,
                                note="Response generated but not sent (WhatsApp API integration needed)"
                            )
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            return error_response(
                                "Error processing message",
                                e,
                                message_id=msg_id
                            )
        
        return success_response(f"Processed {len(entries)} entries")
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}", exc_info=True)
        return error_response(
            "Webhook received but processing failed",
            e
        )


@router.post("/webhook", summary="WhatsApp webhook receiver (alternative)")
async def receive_webhook(
    request: Request,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Alternative webhook endpoint for WhatsApp.
    
    Some WhatsApp integrations use POST /webhook instead of /message/{id}.
    """
    try:
        payload = await request.json()
        logger.info(f"Received WhatsApp webhook: {payload}")
        
        # Forward to message handler
        message_id = payload.get("entry", [{}])[0].get("id", "unknown")
        return await receive_message(message_id, request, chat_service)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return error_response("Error processing webhook", e)


@router.get("/status", summary="WhatsApp integration status")
async def whatsapp_status():
    """Check WhatsApp webhook integration status."""
    return {
        "status": "active",
        "endpoints": {
            "verification": "/v1/whatsapp/webhook (GET)",
            "messages": "/v1/whatsapp/message/{message_id} (POST)",
            "webhook": "/v1/whatsapp/webhook (POST)"
        },
        "note": "WhatsApp webhook endpoints are active. Configure your WhatsApp Business API to use these URLs."
    }



