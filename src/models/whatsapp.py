"""WhatsApp webhook models."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class WhatsAppMessage(BaseModel):
    """WhatsApp incoming message model."""
    from_number: str = Field(..., alias="from")
    to: str
    message_id: str = Field(..., alias="id")
    timestamp: str
    text: Optional[Dict[str, str]] = None
    type: str


class WhatsAppWebhook(BaseModel):
    """WhatsApp webhook payload."""
    object: str
    entry: List[Dict[str, Any]]


class WhatsAppResponse(BaseModel):
    """Response model for WhatsApp webhook."""
    status: str
    message_id: Optional[str] = None
    response: Optional[str] = None


class WhatsAppVerification(BaseModel):
    """WhatsApp webhook verification model."""
    mode: str = Field(..., alias="hub.mode")
    token: str = Field(..., alias="hub.verify_token")
    challenge: str = Field(..., alias="hub.challenge")



