import re
from typing import List, Literal
from pydantic import BaseModel, Field, field_validator

# ==================================================
# Chat Schemas
# ==================================================
class Message(BaseModel):
    """
    Represents a single message in the conversation history.
    """
    role: Literal["user", "assistant", "system"] = Field(..., description="Who sent the message")
    content: str = Field(..., description="The message content", min_length=1, max_length=3000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """
        Sanitization: Prevent basic XSS or injection attacks.
        """
        # Check for potentially harmful content
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")

        # Check for null bytes
        if "\0" in v:
            raise ValueError("Content contains null bytes")
        return v

class ChatRequest(BaseModel):
    """
    Payload sent to the /chat endpoint.
    """
    messages: List[Message] = Field(..., min_length=1)

class ChatResponse(BaseModel):
    """
    Standard response from the /chat endpoint.
    """
    messages: List[Message]

class StreamResponse(BaseModel):
    """
    Chunk format for Server-Sent Events (SSE) streaming.
    """
    content: str = Field(default="")
    done: bool = Field(default=False)