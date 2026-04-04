"""Tests for the agent: router, memory, session management, and BioForgeAgent."""

import asyncio
from uuid import uuid4

from bioforge.agent.router import RouterAgent
from bioforge.agent.memory import AgentMemory
from bioforge.agent.client import BioForgeAgent, Session
from bioforge.modules.registry import ModuleRegistry
from bioforge.modules.assembly import AssemblyModule
from bioforge.core.config import Settings


def _make_registry() -> ModuleRegistry:
    """Create a registry with the assembly module for testing."""
    registry = ModuleRegistry()
    registry.register(AssemblyModule())
    return registry


class TestRouterAgent:
    def test_classify_assembly(self):
        registry = _make_registry()
        router = RouterAgent(registry)

        assert router.classify_intent("design a Gibson Assembly") == "assembly"

    def test_classify_sequence(self):
        registry = _make_registry()
        router = RouterAgent(registry)

        assert router.classify_intent("BLAST this sequence") == "sequence"

    def test_classify_variant(self):
        registry = _make_registry()
        router = RouterAgent(registry)

        assert router.classify_intent("score this mutation") == "variant"

    def test_classify_structure(self):
        registry = _make_registry()
        router = RouterAgent(registry)

        assert router.classify_intent("predict the protein structure") == "structure"

    def test_classify_pipeline(self):
        registry = _make_registry()
        router = RouterAgent(registry)

        assert router.classify_intent("build a pipeline") == "pipeline"

    def test_classify_general(self):
        registry = _make_registry()
        router = RouterAgent(registry)

        result = router.classify_intent("hello")
        assert result == "general"


class TestAgentMemory:
    def test_remember_and_recall(self):
        memory = AgentMemory()
        session_id = uuid4()

        memory.remember(session_id, "The plasmid backbone is pUC19")
        results = memory.recall("plasmid pUC19", session_id=session_id)

        assert len(results) >= 1
        assert "pUC19" in results[0]

    def test_recall_empty(self):
        memory = AgentMemory()
        session_id = uuid4()

        results = memory.recall("anything", session_id=session_id)

        assert results == []

    def test_recall_relevance(self):
        memory = AgentMemory()
        session_id = uuid4()

        memory.remember(session_id, "The target gene is GFP")
        memory.remember(session_id, "The vector backbone is pET28a")

        results = memory.recall("GFP gene", session_id=session_id)
        assert len(results) >= 1
        assert "GFP" in results[0]


class TestBioForgeAgent:
    def test_start_session(self):
        registry = _make_registry()
        settings = Settings(anthropic_api_key="")
        agent = BioForgeAgent(registry, settings)

        workspace_id = uuid4()
        project_id = uuid4()
        session_id = asyncio.run(agent.start_session(workspace_id, project_id))

        # Session ID should be a valid UUID
        assert session_id is not None
        assert str(session_id) != ""

    def test_get_session(self):
        registry = _make_registry()
        settings = Settings(anthropic_api_key="")
        agent = BioForgeAgent(registry, settings)

        workspace_id = uuid4()
        project_id = uuid4()
        session_id = asyncio.run(agent.start_session(workspace_id, project_id))

        session = agent.get_session(session_id)
        assert session is not None
        assert session.id == session_id
        assert session.workspace_id == workspace_id
        assert session.project_id == project_id

    def test_get_nonexistent_session(self):
        registry = _make_registry()
        settings = Settings(anthropic_api_key="")
        agent = BioForgeAgent(registry, settings)

        result = agent.get_session(uuid4())

        assert result is None

    def test_build_tools(self):
        registry = _make_registry()
        settings = Settings(anthropic_api_key="")
        agent = BioForgeAgent(registry, settings)

        tools = agent._build_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0
        # Each tool should have name, description, and input_schema
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool


class TestSession:
    def test_session_has_expected_fields(self):
        session = Session(
            id=uuid4(),
            workspace_id=uuid4(),
            project_id=uuid4(),
        )

        assert session.messages == []
        assert session.total_turns == 0
        assert session.status == "active"
        assert session.created_at is not None
