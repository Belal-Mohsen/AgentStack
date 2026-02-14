from __future__ import annotations

from typing import List, Union, Optional, Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    trim_messages as _trim_messages,
)
from langchain_core.messages.utils import count_tokens_approximately

from app.core.config import settings
from app.core.config.logging import get_logger
from app.schemas import Message

logger = get_logger(__name__)


# ==================================================
# Types
# ==================================================

InputMsg = Union[Message, Dict[str, Any], BaseMessage]

def dump_messages(messages: list[Message]) -> list[dict]:
    """
    Backwards-compatible helper: converts your Pydantic Message list to OpenAI-style dicts.
    """
    return [m.model_dump() for m in messages]

# ==================================================
# Content & Role Helpers
# ==================================================

def _coerce_content_to_str(content: Any) -> str:
    """Ensure content is a string to avoid trimmer/token-counter failures."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    # Covers structured blocks / lists / dicts
    return str(content)


def _extract_role_and_content(m: InputMsg) -> tuple[str, str]:
    """
    Extract role/content from either:
    - Pydantic Message (role/content)
    - dict (OpenAI-ish: role/content; tool_call_id optional)
    - BaseMessage (m.type and m.content)
    """
    if isinstance(m, BaseMessage):
        # LangChain message types: "human", "ai", "system", "tool", ...
        role_map = {
            "human": "user",
            "user": "user",
            "ai": "assistant",
            "assistant": "assistant",
            "system": "system",
            "tool": "tool",
        }
        role = role_map.get(getattr(m, "type", "user"), "user")
        content = _coerce_content_to_str(getattr(m, "content", ""))
        return role, content

    # Pydantic-ish
    if hasattr(m, "role") and hasattr(m, "content"):
        role = getattr(m, "role", "user") or "user"
        content = _coerce_content_to_str(getattr(m, "content", ""))
        return role, content

    # Dict-ish
    if isinstance(m, dict):
        role = (m.get("role") or "user")
        content = _coerce_content_to_str(m.get("content", ""))
        return role, content

    # Fallback
    return "user", _coerce_content_to_str(m)


def _extract_tool_call_id(m: InputMsg) -> str:
    """
    Try to get a tool_call_id for ToolMessage correlation.
    Supports:
    - pydantic attribute tool_call_id
    - dict key tool_call_id / id
    - BaseMessage attribute tool_call_id (if present)
    """
    if isinstance(m, BaseMessage):
        tcid = getattr(m, "tool_call_id", None)
        return str(tcid) if tcid else "unknown"

    if hasattr(m, "tool_call_id"):
        tcid = getattr(m, "tool_call_id", None)
        return str(tcid) if tcid else "unknown"

    if isinstance(m, dict):
        tcid = m.get("tool_call_id") or m.get("id")
        return str(tcid) if tcid else "unknown"

    return "unknown"


# ==================================================
# Normalization Helpers
# ==================================================

def _to_langchain_message(m: InputMsg) -> BaseMessage:
    """Convert any supported message shape into a LangChain BaseMessage."""
    if isinstance(m, BaseMessage):
        # Hardening: ensure content is string-ish
        m.content = _coerce_content_to_str(getattr(m, "content", ""))
        return m

    role, content = _extract_role_and_content(m)

    # Map internal/openai roles to LangChain message types
    if role == "user":
        return HumanMessage(content=content)
    if role == "assistant":
        return AIMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    if role == "tool":
        tool_call_id = _extract_tool_call_id(m)
        return ToolMessage(content=content, tool_call_id=tool_call_id)

    # Safe fallback
    return HumanMessage(content=content)


def _from_langchain_message(m: BaseMessage) -> Optional[Message]:
    """
    Convert LangChain BaseMessage back into your Pydantic Message schema.
    Returns None for empty/unsupported messages.
    """
    role_map = {
        "human": "user",
        "user": "user",
        "ai": "assistant",
        "assistant": "assistant",
        "system": "system",
        "tool": "tool",
    }
    role = role_map.get(getattr(m, "type", "user"), "user")
    content = _coerce_content_to_str(getattr(m, "content", ""))

    # Drop empty messages (optional behavior)
    if not content:
        return None

    # If your Pydantic Message supports tool_call_id, preserve it
    if role == "tool" and hasattr(Message, "model_fields") and "tool_call_id" in Message.model_fields:
        tcid = getattr(m, "tool_call_id", None)
        return Message(role=role, content=content, tool_call_id=str(tcid) if tcid else None)

    return Message(role=role, content=content)


# ==================================================
# Core LLM Utilities
# ==================================================

def prepare_messages(
    messages: List[InputMsg],
    llm: BaseChatModel,
    system_prompt: str,
    *,
    max_fallback_messages: Optional[int] = None,
) -> List[Message]:
    """
    Prepares chat history for the LLM by trimming it to fit the context window.

    Logic:
    1. Normalize all messages to LangChain BaseMessage objects.
    2. Attempt precision trimming using the model token counter (token_counter=llm).
    3. If that fails (e.g., unrecognized content blocks), fall back to approximate counting.
    4. If the approximate fallback also fails, fall back to a hard-cap by message count.
    5. Always return a clean List[Message] starting with the system prompt.

    Notes:
    - We exclude system messages during trimming and prepend our canonical system prompt.
    - start_on="human" is correct because we normalize user messages to HumanMessage.
    """
    if max_fallback_messages is None:
        # Sensible default: keep the last N messages if all trimming fails
        max_fallback_messages = getattr(settings, "MAX_FALLBACK_MSGS", 30)

    # 1) Normalize inputs
    lc_messages = [_to_langchain_message(m) for m in messages]

    # 2) Trim (precision)
    try:
        trimmed_lc = _trim_messages(
            lc_messages,
            strategy="last",
            token_counter=llm,
            max_tokens=settings.MAX_TOKENS,
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
    except (ValueError, TypeError) as e:
        logger.warning(
            "precision_trimming_failed_using_approximate",
            error=str(e),
            message_count=len(lc_messages),
        )
        # 3) Trim (approximate)
        try:
            trimmed_lc = _trim_messages(
                lc_messages,
                strategy="last",
                token_counter=count_tokens_approximately,
                max_tokens=settings.MAX_TOKENS,
                start_on="human",
                include_system=False,
                allow_partial=False,
            )
        except Exception as e2:
            logger.error(
                "approximate_trimming_failed_using_hard_cap",
                error=str(e2),
                message_count=len(lc_messages),
                hard_cap=max_fallback_messages,
            )
            # 4) Last resort hard-cap (never send full history)
            trimmed_lc = lc_messages[-max_fallback_messages:]

    # 5) Convert back to your schema (consistent return type)
    final_history: List[Message] = [Message(role="system", content=system_prompt)]

    for m in trimmed_lc:
        pm = _from_langchain_message(m)
        if pm is not None:
            final_history.append(pm)

    return final_history


def process_llm_response(response: BaseMessage) -> BaseMessage:
    """
    Normalize responses from advanced models (e.g., GPT-5 preview / o1-style / Claude)
    that may return structured content blocks.

    - Extracts text blocks into a flat string.
    - Logs reasoning blocks for observability.
    - Mutates response.content in place.
    """
    content = getattr(response, "content", None)

    if isinstance(content, list):
        text_parts: List[str] = []

        for block in content:
            # Allow plain strings in list
            if isinstance(block, str):
                text_parts.append(block)
                continue

            # Dict block format: {"type": "...", ...}
            if isinstance(block, dict):
                block_type = block.get("type")

                if block_type == "text":
                    text_parts.append(_coerce_content_to_str(block.get("text", "")))

                elif block_type == "reasoning":
                    logger.debug(
                        "reasoning_block_received",
                        reasoning_id=block.get("id"),
                        has_summary=bool(block.get("summary")),
                    )

                else:
                    # Unknown dict block: keep it out of UI, but make it diagnosable
                    logger.debug(
                        "unknown_content_block_received",
                        block_type=block_type,
                        keys=list(block.keys()),
                    )
                continue

            # Unknown block type: stringify to avoid losing user-visible content
            text_parts.append(_coerce_content_to_str(block))

        response.content = "".join(text_parts)

    else:
        # Ensure it's a string (some providers may return non-str scalars)
        response.content = _coerce_content_to_str(content)

    return response
