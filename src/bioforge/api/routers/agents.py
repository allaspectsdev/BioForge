from fastapi import APIRouter, Depends, HTTPException

from bioforge.api.deps import get_settings
from bioforge.core.config import Settings
from bioforge.modules.assembly.module import AssemblyModule
from bioforge.modules.registry import ModuleRegistry
from bioforge.schemas.agent import AgentQuery, AgentResponse

router = APIRouter()


def _get_agent(settings: Settings = Depends(get_settings)):
    from bioforge.agent.client import BioForgeAgent

    registry = ModuleRegistry()
    registry.register(AssemblyModule())
    return BioForgeAgent(registry, settings)


@router.post("/query", response_model=AgentResponse)
async def agent_query(body: AgentQuery, agent=Depends(_get_agent)):
    """Send a natural language query to the BioForge AI agent."""
    if not agent.settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured. Set BIOFORGE_ANTHROPIC_API_KEY.",
        )
    result = await agent.query(
        prompt=body.prompt,
        workspace_id=str(body.workspace_id),
        project_id=str(body.project_id),
    )
    return AgentResponse(result=result)
