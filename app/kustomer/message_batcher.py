import asyncio
import logging
from typing import Dict, List, Callable, Awaitable
from dataclasses import dataclass, field
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class MessageBatch:
    customer_id: str
    messages: List[str] = field(default_factory=list)
    conversation_id: str = ""
    agent_name: str = "default"
    context: dict = field(default_factory=dict)
    _task: asyncio.Task | None = None


_batches: Dict[str, MessageBatch] = {}
_lock = asyncio.Lock()


async def add_message(
    customer_id: str,
    message: str,
    conversation_id: str,
    agent_name: str,
    context: dict,
    on_batch_ready: Callable[[MessageBatch], Awaitable[None]],
) -> None:
    async with _lock:
        if customer_id in _batches:
            batch = _batches[customer_id]
            batch.messages.append(message)
            if batch._task and not batch._task.done():
                batch._task.cancel()
            if len(batch.messages) >= settings.message_batch_max_size:
                del _batches[customer_id]
                asyncio.create_task(_flush(batch, on_batch_ready))
                return
        else:
            batch = MessageBatch(
                customer_id=customer_id,
                messages=[message],
                conversation_id=conversation_id,
                agent_name=agent_name,
                context=context,
            )
            _batches[customer_id] = batch

        batch._task = asyncio.create_task(
            _schedule_flush(customer_id, batch, on_batch_ready)
        )


async def _schedule_flush(customer_id, batch, on_batch_ready):
    try:
        await asyncio.sleep(settings.message_batch_window_seconds)
        async with _lock:
            if customer_id in _batches and _batches[customer_id] is batch:
                del _batches[customer_id]
                await _flush(batch, on_batch_ready)
    except asyncio.CancelledError:
        pass


async def _flush(batch, on_batch_ready):
    combined = " ".join(batch.messages)
    batch.messages = [combined]
    try:
        await on_batch_ready(batch)
    except Exception:
        logger.exception(f"Error procesando batch para {batch.customer_id}")
