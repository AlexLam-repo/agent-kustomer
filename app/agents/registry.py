"""
Tool Registry — registra aquí las funciones Python que el agente puede llamar.
Para agregar una tool nueva: añade una función con @register("nombre_tool")
"""
from typing import Callable, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
_REGISTRY: Dict[str, Callable] = {}


def register(name: str):
    def decorator(fn: Callable):
        _REGISTRY[name] = fn
        return fn
    return decorator


def get_tool_function(name: str) -> Callable | None:
    return _REGISTRY.get(name)


def list_registered() -> list[str]:
    return list(_REGISTRY.keys())


# ── Tools disponibles ────────────────────────────────────────────

@register("get_current_datetime")
def get_current_datetime() -> str:
    """Retorna la fecha y hora actual."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@register("get_customer_info")
def get_customer_info(customer_id: str) -> dict:
    """Obtiene información de un cliente por su ID."""
    # TODO: reemplazar con llamada real a tu API o BD
    return {
        "customer_id": customer_id,
        "name": "Cliente Demo",
        "email": "demo@example.com",
        "status": "active",
    }


@register("create_ticket")
def create_ticket(customer_id: str, subject: str, description: str) -> dict:
    """Crea un ticket de soporte para un cliente."""
    # TODO: reemplazar con tu sistema de tickets
    import random
    ticket_id = f"TKT-{random.randint(10000, 99999)}"
    logger.info(f"Ticket creado: {ticket_id}")
    return {"ticket_id": ticket_id, "status": "created", "subject": subject}


@register("check_order_status")
def check_order_status(order_id: str) -> dict:
    """Consulta el estado de un pedido u orden."""
    # TODO: reemplazar con tu sistema de órdenes
    return {"order_id": order_id, "status": "en proceso", "estimated_date": "2025-04-20"}
