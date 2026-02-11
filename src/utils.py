"""Utility functions for async handling and timeouts."""

import asyncio
from typing import TypeVar, Coroutine, Any

from .logging_config import get_logger

logger = get_logger("ai_workflow.utils")

T = TypeVar("T")

# Default timeout for LLM calls (seconds)
DEFAULT_TIMEOUT = 60


class PipelineTimeout(Exception):
    """Raised when a pipeline stage times out."""

    pass


def run_with_timeout(
    coro: Coroutine[Any, Any, T], timeout: float = DEFAULT_TIMEOUT, stage_name: str = "operation"
) -> T:
    """
    Run an async coroutine with a timeout.

    This creates a new event loop each time, which is necessary for Streamlit
    since it doesn't have a running event loop in the main thread.

    Args:
        coro: The coroutine to run
        timeout: Timeout in seconds (default 60)
        stage_name: Name of the stage for logging

    Returns:
        The result of the coroutine

    Raises:
        PipelineTimeout: If the operation times out
        Exception: Any other exception from the coroutine
    """
    logger.info(f"Starting {stage_name} (timeout: {timeout}s)")

    async def run_with_timeout_async():
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"{stage_name} timed out after {timeout}s")
            raise PipelineTimeout(f"{stage_name} timed out after {timeout} seconds")

    # Create new event loop for this operation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(run_with_timeout_async())
        logger.info(f"Completed {stage_name}")
        return result
    except PipelineTimeout:
        raise
    except Exception as e:
        logger.exception(f"Error in {stage_name}: {e}")
        raise
    finally:
        # Clean up the loop
        try:
            loop.close()
        except Exception:
            pass


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
