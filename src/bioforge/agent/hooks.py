"""Agent hooks for audit logging, safety, and cost tracking."""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


async def audit_hook(tool_name: str, tool_input: dict, **kwargs: Any) -> dict:
    """Log every tool call for reproducibility."""
    logger.info("Agent tool call: %s", tool_name)
    return {}


async def safety_hook(tool_name: str, tool_input: dict, **kwargs: Any) -> dict:
    """Block dangerous operations."""
    blocked_tools = {"Bash", "shell", "exec"}
    if tool_name in blocked_tools:
        logger.warning("Blocked unsafe tool call: %s", tool_name)
        return {"blocked": True, "reason": "Direct shell access not permitted"}
    return {}


async def cost_tracking_hook(
    tool_name: str, duration_ms: int = 0, **kwargs: Any
) -> dict:
    """Track API costs per session."""
    logger.debug("Tool %s completed in %dms", tool_name, duration_ms)
    return {}
