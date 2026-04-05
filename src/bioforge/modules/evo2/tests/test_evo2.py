"""Tests for the Evo 2 module using MockEvo2Client."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pytest

from bioforge.modules.evo2.client import EMBEDDING_DIM, MockEvo2Client
from bioforge.modules.evo2.embeddings import EmbeddingService
from bioforge.modules.evo2.module import Evo2Module
from bioforge.modules.evo2.variant_scorer import VariantEffectPredictor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MockEvo2Client:
    return MockEvo2Client()


@pytest.fixture
def evo2_module(mock_client: MockEvo2Client) -> Evo2Module:
    return Evo2Module(client=mock_client)


@pytest.fixture
def variant_predictor(mock_client: MockEvo2Client) -> VariantEffectPredictor:
    return VariantEffectPredictor(mock_client)


@pytest.fixture
def embedding_service(mock_client: MockEvo2Client) -> EmbeddingService:
    return EmbeddingService(mock_client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmbedReturnsVector:
    """Verify that MockEvo2Client.embed returns a correct embedding vector."""

    @pytest.mark.asyncio
    async def test_embed_returns_correct_dimension(self, mock_client: MockEvo2Client):
        vec = await mock_client.embed("ATCGATCGATCG")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (EMBEDDING_DIM,)

    @pytest.mark.asyncio
    async def test_embed_is_deterministic(self, mock_client: MockEvo2Client):
        v1 = await mock_client.embed("ATCGATCG")
        v2 = await mock_client.embed("ATCGATCG")
        np.testing.assert_array_equal(v1, v2)

    @pytest.mark.asyncio
    async def test_embed_different_sequences_differ(self, mock_client: MockEvo2Client):
        v1 = await mock_client.embed("AAAA")
        v2 = await mock_client.embed("TTTT")
        assert not np.allclose(v1, v2)

    @pytest.mark.asyncio
    async def test_embed_is_normalized(self, mock_client: MockEvo2Client):
        vec = await mock_client.embed("GCGCGCGC")
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-5


class TestVariantScoringReturnsScores:
    """Verify variant scoring via MockEvo2Client."""

    @pytest.mark.asyncio
    async def test_score_variants_returns_list(self, mock_client: MockEvo2Client):
        seq = "ATCGATCG"
        mutations = [(0, "A", "T"), (3, "G", "C")]
        scores = await mock_client.score_variants(seq, mutations)
        assert isinstance(scores, list)
        assert len(scores) == 2
        assert all(isinstance(s, float) for s in scores)

    @pytest.mark.asyncio
    async def test_score_variants_deterministic(self, mock_client: MockEvo2Client):
        seq = "ATCGATCG"
        mutations = [(0, "A", "T")]
        s1 = await mock_client.score_variants(seq, mutations)
        s2 = await mock_client.score_variants(seq, mutations)
        assert s1 == s2

    @pytest.mark.asyncio
    async def test_variant_predictor_scan(self, variant_predictor: VariantEffectPredictor):
        seq = "ATCG"
        results = await variant_predictor.scan_variants(seq, 0, 2)
        # 2 positions x 3 alternate bases each = 6 variants
        assert len(results) == 6
        # Results are sorted by score ascending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores)

    @pytest.mark.asyncio
    async def test_variant_predictor_single_mutation(
        self, variant_predictor: VariantEffectPredictor
    ):
        seq = "ATCGATCG"
        result = await variant_predictor.score_mutation(seq, 0, "T")
        assert "position" in result
        assert "ref_base" in result
        assert "alt_base" in result
        assert "score" in result
        assert result["interpretation"] in ("deleterious", "neutral", "beneficial")

    @pytest.mark.asyncio
    async def test_same_base_mutation_is_neutral(
        self, variant_predictor: VariantEffectPredictor
    ):
        seq = "ATCGATCG"
        result = await variant_predictor.score_mutation(seq, 0, "A")
        assert result["score"] == 0.0
        assert result["interpretation"] == "neutral"


class TestSimilaritySearch:
    """Test similarity search with a mocked database session."""

    @pytest.mark.asyncio
    async def test_similarity_search_calls_db(
        self, embedding_service: EmbeddingService, mock_client: MockEvo2Client
    ):
        query_vec = await mock_client.embed("ATCGATCG")
        project_id = uuid4()

        # Mock the async session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "seq_alpha", 0.15),
            (uuid4(), "seq_beta", 0.42),
        ]
        mock_session.execute.return_value = mock_result

        hits = await embedding_service.similarity_search(
            query_vec, project_id, top_k=5, session=mock_session
        )

        assert len(hits) == 2
        assert hits[0]["name"] == "seq_alpha"
        assert hits[0]["distance"] == 0.15
        assert abs(hits[0]["score"] - 0.85) < 1e-6
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_embed_and_store(
        self, embedding_service: EmbeddingService
    ):
        sid = uuid4()
        mock_session = AsyncMock()

        vec = await embedding_service.embed_and_store(sid, "ATCGATCG", mock_session)

        assert isinstance(vec, np.ndarray)
        assert vec.shape == (EMBEDDING_DIM,)
        # Verify UPDATE was executed
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()


class TestModuleRegistration:
    """Verify the Evo2Module integrates with the ModuleRegistry."""

    def test_module_info(self, evo2_module: Evo2Module):
        info = evo2_module.info()
        assert info.name == "evo2"
        assert info.version == "0.2.0"

    def test_module_has_four_capabilities(self, evo2_module: Evo2Module):
        caps = evo2_module.capabilities()
        assert len(caps) == 4
        names = {c.name for c in caps}
        assert names == {"embed_sequence", "find_similar", "score_variants", "generate_sequence"}

    def test_module_has_two_pipeline_steps(self, evo2_module: Evo2Module):
        steps = evo2_module.pipeline_steps()
        assert len(steps) == 2
        step_types = {s.step_type for s in steps}
        assert step_types == {"evo2.embed", "evo2.variant_scan"}

    def test_module_has_four_mcp_tools(self, evo2_module: Evo2Module):
        tools = evo2_module.mcp_tools()
        assert len(tools) == 4

    def test_registry_integration(self, evo2_module: Evo2Module):
        from bioforge.modules.registry import ModuleRegistry

        registry = ModuleRegistry()
        registry.register(evo2_module)

        assert registry.get_module("evo2") is evo2_module
        assert len(registry.all_capabilities()) == 4
        assert "evo2.embed" in registry.all_pipeline_steps()
        assert "evo2.variant_scan" in registry.all_pipeline_steps()
        assert len(registry.all_mcp_tools()) == 4


class TestGeneration:
    """Test sequence generation via mock client."""

    @pytest.mark.asyncio
    async def test_generate_returns_bases(self, mock_client: MockEvo2Client):
        result = await mock_client.generate("ATCG", max_length=50)
        assert len(result) == 50
        assert all(b in "ATCG" for b in result)

    @pytest.mark.asyncio
    async def test_generate_deterministic(self, mock_client: MockEvo2Client):
        r1 = await mock_client.generate("ATCG", max_length=20)
        r2 = await mock_client.generate("ATCG", max_length=20)
        assert r1 == r2

    @pytest.mark.asyncio
    async def test_module_generate_handler(self, evo2_module: Evo2Module):
        result = await evo2_module._handle_generate(
            {"prompt_sequence": "ATCG", "max_length": 30}
        )
        assert result["prompt_length"] == 4
        assert result["generated_length"] == 30
        assert result["full_sequence"].startswith("ATCG")
