import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.config import get_settings
from app.agents.models import (
    Agent, Tool, AgentToolLink,
    AgentCreate, AgentUpdate, AgentRead,
    ToolCreate, ToolUpdate, ToolRead,
)
from app.sessions.models import ConversationSession
from app.agents.registry import list_registered

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden")


# ── Agents ───────────────────────────────────────────────────────

@router.get("/agents", response_model=List[AgentRead])
async def list_agents(db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(
        select(Agent).options(selectinload(Agent.tools)).order_by(Agent.created_at.desc())
    )
    return result.all()


@router.get("/agents/{agent_id}", response_model=AgentRead)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(
        select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.tools))
    )
    agent = result.first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/agents", response_model=AgentRead, status_code=201)
async def create_agent(payload: AgentCreate, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    existing = await db.exec(select(Agent).where(Agent.name == payload.name))
    if existing.first():
        raise HTTPException(status_code=409, detail="Agent name already exists")

    agent = Agent(
        name=payload.name,
        display_name=payload.display_name,
        instructions=payload.instructions,
        model=payload.model,
        role=payload.role,
        handoff_agents=payload.handoff_agents,
    )
    db.add(agent)
    await db.flush()

    for tool_id in payload.tool_ids:
        tool_result = await db.exec(select(Tool).where(Tool.id == tool_id))
        if tool_result.first():
            db.add(AgentToolLink(agent_id=agent.id, tool_id=tool_id))

    await db.commit()
    result = await db.exec(
        select(Agent).where(Agent.id == agent.id).options(selectinload(Agent.tools))
    )
    return result.first()


@router.patch("/agents/{agent_id}", response_model=AgentRead)
async def update_agent(agent_id: int, payload: AgentUpdate, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(select(Agent).where(Agent.id == agent_id))
    agent = result.first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    for k, v in payload.model_dump(exclude_unset=True, exclude={"tool_ids"}).items():
        setattr(agent, k, v)
    agent.updated_at = datetime.utcnow()

    if payload.tool_ids is not None:
        existing_links = await db.exec(
            select(AgentToolLink).where(AgentToolLink.agent_id == agent_id)
        )
        for link in existing_links.all():
            await db.delete(link)
        for tool_id in payload.tool_ids:
            db.add(AgentToolLink(agent_id=agent_id, tool_id=tool_id))

    db.add(agent)
    await db.commit()
    result = await db.exec(
        select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.tools))
    )
    return result.first()


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(select(Agent).where(Agent.id == agent_id))
    agent = result.first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()


# ── Tools ────────────────────────────────────────────────────────

@router.get("/tools", response_model=List[ToolRead])
async def list_tools(db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(select(Tool).order_by(Tool.created_at.desc()))
    return result.all()


@router.post("/tools", response_model=ToolRead, status_code=201)
async def create_tool(payload: ToolCreate, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    existing = await db.exec(select(Tool).where(Tool.name == payload.name))
    if existing.first():
        raise HTTPException(status_code=409, detail="Tool name already exists")
    tool = Tool(**payload.model_dump())
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.patch("/tools/{tool_id}", response_model=ToolRead)
async def update_tool(tool_id: int, payload: ToolUpdate, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(select(Tool).where(Tool.id == tool_id))
    tool = result.first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tool, k, v)
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(tool_id: int, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(select(Tool).where(Tool.id == tool_id))
    tool = result.first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    await db.delete(tool)
    await db.commit()


# ── Registry & Sessions ──────────────────────────────────────────

@router.get("/registry")
async def get_registry(_=Depends(require_admin)):
    return {"registered_functions": list_registered()}


@router.get("/sessions")
async def list_sessions(limit: int = 50, db: AsyncSession = Depends(get_session), _=Depends(require_admin)):
    result = await db.exec(
        select(ConversationSession).order_by(ConversationSession.updated_at.desc()).limit(limit)
    )
    return [
        {
            "id": s.id,
            "customer_id": s.customer_id,
            "agent_name": s.agent_name,
            "has_thread": bool(s.openai_response_id),
            "metadata": s.get_metadata(),
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in result.all()
    ]
