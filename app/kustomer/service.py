import hashlib
import hmac
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.sessions.models import ConversationSession
from app.agents.service import run_agent
from app.utils.kustomer_client import kustomer_client

logger = logging.getLogger(__name__)
settings = get_settings()


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    if not settings.kustomer_webhook_secret:
        return True
    expected = hmac.new(
        settings.kustomer_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    sig_value = signature.replace("sha256=", "").strip()
    return hmac.compare_digest(expected, sig_value)


async def get_or_create_session(
    db: AsyncSession,
    customer_id: str,
    agent_name: str = "default",
) -> ConversationSession:
    result = await db.execute(
        select(ConversationSession).where(
            ConversationSession.customer_id == customer_id,
            ConversationSession.provider == "kustomer",
        )
    )
    session = result.scalars().first()
    if session:
        return session

    session = ConversationSession(
        customer_id=customer_id,
        provider="kustomer",
        agent_name=agent_name,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def process_message(
    db: AsyncSession,
    customer_id: str,
    conversation_id: str,
    message: str,
    agent_name: str = "default",
    context: dict | None = None,
) -> None:
    session = await get_or_create_session(db, customer_id, agent_name)
    response_text, _ = await run_agent(
        db=db,
        agent_name=session.agent_name,
        message=message,
        context=context,
        previous_response_id=session.openai_response_id,
    )
    try:
        await kustomer_client.send_message(conversation_id, response_text)
    except Exception as e:
        logger.exception(f"Error enviando mensaje a Kustomer: {e}")

    session.updated_at = datetime.utcnow()
    db.add(session)
    await db.commit()


async def reset_session(db: AsyncSession, customer_id: str) -> bool:
    result = await db.execute(
        select(ConversationSession).where(
            ConversationSession.customer_id == customer_id,
            ConversationSession.provider == "kustomer",
        )
    )
    session = result.scalars().first()
    if not session:
        return False
    session.openai_response_id = None
    session.updated_at = datetime.utcnow()
    db.add(session)
    await db.commit()
    return True
