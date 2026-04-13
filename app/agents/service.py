import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import openai

from app.agents.models import Agent, Tool
from app.agents.registry import get_tool_function
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_tool_schema(tool: Tool) -> dict | None:
    fn = get_tool_function(tool.function_name)
    if fn is None:
        return None
    try:
        params = json.loads(tool.parameters_schema)
    except Exception:
        params = {}
    return {
        "type": "function",
        "function": {
            "name": tool.function_name,
            "description": tool.description,
            "parameters": params or {"type": "object", "properties": {}, "required": []},
        },
    }


def _execute_tool(function_name: str, arguments: str) -> str:
    fn = get_tool_function(function_name)
    if fn is None:
        return f"Error: función '{function_name}' no disponible"
    try:
        args = json.loads(arguments) if arguments else {}
        result = fn(**args)
        return json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
    except Exception as e:
        logger.exception(f"Error ejecutando tool '{function_name}'")
        return f"Error: {str(e)}"


async def run_agent(
    db: AsyncSession,
    agent_name: str,
    message: str,
    context: dict | None = None,
    previous_response_id: str | None = None,
) -> tuple[str, None]:
    result = await db.execute(
        select(Agent)
        .where(Agent.name == agent_name, Agent.is_active == True)
        .options(selectinload(Agent.tools))
    )
    agent_db = result.scalars().first()

    if not agent_db:
        logger.error(f"Agente '{agent_name}' no encontrado o inactivo")
        return "Lo siento, el agente no está disponible en este momento.", None

    tools_schema = [
        s for t in agent_db.tools
        if t.is_active
        for s in [_build_tool_schema(t)]
        if s is not None
    ]

    user_content = message
    if context:
        ctx_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        user_content = f"[Contexto]\n{ctx_str}\n\n[Mensaje]\n{message}"

    messages = [
        {"role": "system", "content": agent_db.instructions},
        {"role": "user", "content": user_content},
    ]

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        for _ in range(5):
            kwargs: dict = {"model": agent_db.model, "messages": messages}
            if tools_schema:
                kwargs["tools"] = tools_schema
                kwargs["tool_choice"] = "auto"

            response = await client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            if not msg.tool_calls:
                return msg.content or "", None

            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _execute_tool(tc.function.name, tc.function.arguments),
                })

        return "No pude completar la operación. Por favor intenta de nuevo.", None

    except Exception as e:
        logger.exception(f"Error en agente '{agent_name}': {e}")
        return "Ocurrió un error. Por favor intenta de nuevo.", None


async def seed_default_agent(db: AsyncSession):
    result = await db.execute(select(Agent).limit(1))
    if result.scalars().first():
        return
    agent = Agent(
        name="default",
        display_name="Agente Principal",
        instructions=(
            "Eres un asistente de servicio al cliente amable y profesional. "
            "Ayuda a los clientes con sus consultas de forma clara y concisa. "
            "Si no puedes resolver algo, ofrece escalar con un agente humano."
        ),
        model="gpt-4o-mini",
        role="default",
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    logger.info("Agente default creado")
