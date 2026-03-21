from typing import Any

from fastapi import APIRouter

from luml_agent.schemas import AgentOut
from luml_agent.services.agents import list_agents, list_available_agents

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def get_all_agents() -> list[dict[str, Any]]:
    return [
        AgentOut.from_def(a).model_dump()
        for a in list_agents()
    ]


@router.get("/available")
def get_available_agents() -> list[dict[str, Any]]:
    return [
        AgentOut.from_def(a).model_dump()
        for a in list_available_agents()
    ]
