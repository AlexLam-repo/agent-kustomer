import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import get_session, AsyncSessionLocal
from app.kustomer.service import verify_webhook_signature, process_message, reset_session
from app.kustomer.message_batcher import add_message, MessageBatch

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kustomer", tags=["kustomer"])


class DirectMessage(BaseModel):
    customer_id: str
    conversation_id: str
    message: str
    agent_name: str = "default"
    context: Optional[dict] = None


class TriggerPayload(BaseModel):
    customer_id: str
    conversation_id: str
    agent_name: str = "default"
    initial_message: Optional[str] = None
    context: Optional[dict] = None


def make_batch_processor():
    async def on_batch_ready(batch: MessageBatch):
        async with AsyncSessionLocal() as db:
            await process_message(
                db=db,
                customer_id=batch.customer_id,
                conversation_id=batch.conversation_id,
                message=batch.messages[0],
                agent_name=batch.agent_name,
                context=batch.context,
            )
    return on_batch_ready


@router.post("/webhook")
async def kustomer_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_kustomer_signature: Optional[str] = Header(None),
):
    """Endpoint principal — configura esta URL en Kustomer → Settings → Webhooks."""
    body = await request.body()

    if x_kustomer_signature:
        if not verify_webhook_signature(body, x_kustomer_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("type", "")
    data = payload.get("data", {})

    logger.info(f"Kustomer webhook: type={event_type}")

    if event_type in ("kustomer.conversation.message.send", "message.send"):
        attrs = data.get("attributes", {})
        if attrs.get("direction") == "in":
            customer_id = (
                data.get("relationships", {})
                .get("customer", {}).get("data", {}).get("id", "")
            )
            conversation_id = (
                data.get("relationships", {})
                .get("conversation", {}).get("data", {}).get("id", "")
            )
            message_body = attrs.get("body", "").strip()

            if not customer_id or not message_body:
                return {"status": "skipped"}

            background_tasks.add_task(
                add_message,
                customer_id=customer_id,
                message=message_body,
                conversation_id=conversation_id,
                agent_name="default",
                context={"conversation_id": conversation_id},
                on_batch_ready=make_batch_processor(),
            )
            return {"status": "queued"}

    return {"status": "ignored", "type": event_type}


@router.post("/trigger")
async def trigger_conversation(
    payload: TriggerPayload,
    db: AsyncSession = Depends(get_session),
):
    """Inicia una conversación desde un Kustomer Workflow."""
    msg = payload.initial_message or "Hola, ¿en qué puedo ayudarte?"
    await process_message(
        db=db,
        customer_id=payload.customer_id,
        conversation_id=payload.conversation_id,
        message=msg,
        agent_name=payload.agent_name,
        context=payload.context,
    )
    return {"status": "ok"}


@router.post("/message")
async def send_direct_message(
    payload: DirectMessage,
    background_tasks: BackgroundTasks,
):
    """Envía un mensaje directo al agente — útil para pruebas."""
    background_tasks.add_task(
        add_message,
        customer_id=payload.customer_id,
        message=payload.message,
        conversation_id=payload.conversation_id,
        agent_name=payload.agent_name,
        context=payload.context or {},
        on_batch_ready=make_batch_processor(),
    )
    return {"status": "queued"}


@router.post("/reset/{customer_id}")
async def reset_customer_session(
    customer_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Resetea la sesión de un cliente para iniciar conversación nueva."""
    success = await reset_session(db, customer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "reset"}
