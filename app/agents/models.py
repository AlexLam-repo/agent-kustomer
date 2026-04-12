from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import Text
import json


class AgentToolLink(SQLModel, table=True):
    __tablename__ = "agent_tool_links"
    agent_id: Optional[int] = Field(default=None, foreign_key="agents.id", primary_key=True)
    tool_id: Optional[int] = Field(default=None, foreign_key="tools.id", primary_key=True)


class Agent(SQLModel, table=True):
    __tablename__ = "agents"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, max_length=100)
    display_name: str = Field(max_length=200)
    instructions: str = Field(sa_column=Column(Text, nullable=False))
    model: str = Field(default="gpt-4o-mini", max_length=100)
    role: str = Field(default="default", max_length=50)
    is_active: bool = Field(default=True)
    handoff_agents: str = Field(default="[]", max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    tools: List["Tool"] = Relationship(back_populates="agents", link_model=AgentToolLink)


class Tool(SQLModel, table=True):
    __tablename__ = "tools"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, max_length=100)
    display_name: str = Field(max_length=200)
    description: str = Field(sa_column=Column(Text, nullable=False))
    function_name: str = Field(max_length=100)
    parameters_schema: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    agents: List[Agent] = Relationship(back_populates="tools", link_model=AgentToolLink)


# ── API schemas ──────────────────────────────────────────────────

class ToolRead(SQLModel):
    id: int
    name: str
    display_name: str
    description: str
    function_name: str
    parameters_schema: str
    is_active: bool


class AgentRead(SQLModel):
    id: int
    name: str
    display_name: str
    instructions: str
    model: str
    role: str
    is_active: bool
    handoff_agents: str
    created_at: datetime
    updated_at: datetime
    tools: List[ToolRead] = []


class AgentCreate(SQLModel):
    name: str
    display_name: str
    instructions: str
    model: str = "gpt-4o-mini"
    role: str = "default"
    handoff_agents: str = "[]"
    tool_ids: List[int] = []


class AgentUpdate(SQLModel):
    display_name: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    tool_ids: Optional[List[int]] = None


class ToolCreate(SQLModel):
    name: str
    display_name: str
    description: str
    function_name: str
    parameters_schema: str = "{}"


class ToolUpdate(SQLModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    parameters_schema: Optional[str] = None


AgentRead.model_rebuild()
