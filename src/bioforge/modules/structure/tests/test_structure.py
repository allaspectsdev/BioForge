"""Tests for the structure prediction module using MockStructureClient."""

from __future__ import annotations

import pytest

from bioforge.modules.structure.client import MockStructureClient, PDBResult
from bioforge.modules.structure.module import StructureModule

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MockStructureClient:
    return MockStructureClient()


@pytest.fixture
def structure_module(mock_client: MockStructureClient) -> StructureModule:
    return StructureModule(client=mock_client)


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class TestMockStructureClient:
    """Verify MockStructureClient behaviour."""

    @pytest.mark.asyncio
    async def test_predict_structure_returns_pdb(self, mock_client: MockStructureClient):
        result = await mock_client.predict_structure("MKFLILLFNILCLFPVLAADNH")
        assert isinstance(result, PDBResult)
        assert "ATOM" in result.pdb_string
        assert "END" in result.pdb_string

    @pytest.mark.asyncio
    async def test_plddt_scores_count(self, mock_client: MockStructureClient):
        seq = "MKFLILLFNILCLFPVLAADNH"
        result = await mock_client.predict_structure(seq)
        assert len(result.plddt_scores) == len(seq)

    @pytest.mark.asyncio
    async def test_mean_plddt_in_range(self, mock_client: MockStructureClient):
        result = await mock_client.predict_structure("MKFLILLFNILCLFPVLAADNH")
        assert 0.0 <= result.mean_plddt <= 100.0

    @pytest.mark.asyncio
    async def test_num_residues_matches_sequence(self, mock_client: MockStructureClient):
        seq = "ACDEFGHIKLMNPQRSTVWY"
        result = await mock_client.predict_structure(seq)
        assert result.num_residues == len(seq)

    @pytest.mark.asyncio
    async def test_predict_structure_deterministic(self, mock_client: MockStructureClient):
        seq = "MKFLIL"
        r1 = await mock_client.predict_structure(seq)
        r2 = await mock_client.predict_structure(seq)
        assert r1.pdb_string == r2.pdb_string
        assert r1.plddt_scores == r2.plddt_scores

    @pytest.mark.asyncio
    async def test_predict_complex(self, mock_client: MockStructureClient):
        seqs = ["MKFLI", "ACDEF"]
        result = await mock_client.predict_complex(seqs)
        assert isinstance(result, PDBResult)
        assert result.num_residues == 10
        # Should contain TER records between chains
        assert "TER" in result.pdb_string

    @pytest.mark.asyncio
    async def test_predict_complex_plddt_count(self, mock_client: MockStructureClient):
        seqs = ["MKFLI", "ACDEF", "GHI"]
        result = await mock_client.predict_complex(seqs)
        assert len(result.plddt_scores) == sum(len(s) for s in seqs)


# ---------------------------------------------------------------------------
# Module integration tests
# ---------------------------------------------------------------------------


class TestStructureModule:
    """Verify StructureModule integrates correctly."""

    def test_module_info(self, structure_module: StructureModule):
        info = structure_module.info()
        assert info.name == "structure"
        assert info.version == "0.2.0"

    def test_module_has_two_capabilities(self, structure_module: StructureModule):
        caps = structure_module.capabilities()
        assert len(caps) == 2
        names = {c.name for c in caps}
        assert names == {"structure.predict", "structure.predict_complex"}

    def test_module_has_one_pipeline_step(self, structure_module: StructureModule):
        steps = structure_module.pipeline_steps()
        assert len(steps) == 1
        assert steps[0].step_type == "structure.fold"

    def test_module_has_two_mcp_tools(self, structure_module: StructureModule):
        tools = structure_module.mcp_tools()
        assert len(tools) == 2

    def test_registry_integration(self, structure_module: StructureModule):
        from bioforge.modules.registry import ModuleRegistry

        registry = ModuleRegistry()
        registry.register(structure_module)

        assert registry.get_module("structure") is structure_module
        assert len(registry.all_capabilities()) == 2
        assert "structure.fold" in registry.all_pipeline_steps()
        assert len(registry.all_mcp_tools()) == 2

    @pytest.mark.asyncio
    async def test_handle_predict(self, structure_module: StructureModule):
        result = await structure_module._handle_predict({"sequence": "MKFLIL"})
        assert "pdb_string" in result
        assert "plddt_scores" in result
        assert "mean_plddt" in result
        assert result["num_residues"] == 6

    @pytest.mark.asyncio
    async def test_handle_predict_complex(self, structure_module: StructureModule):
        result = await structure_module._handle_predict_complex(
            {"sequences": ["MKFLI", "ACDEF"]}
        )
        assert "pdb_string" in result
        assert result["num_residues"] == 10

    @pytest.mark.asyncio
    async def test_pipeline_fold(self, structure_module: StructureModule):
        result = await structure_module._pipeline_fold(
            {"sequence": "MKFLIL"}, {}
        )
        assert "pdb_string" in result
        assert "mean_plddt" in result

    @pytest.mark.asyncio
    async def test_mcp_predict_structure(self, structure_module: StructureModule):
        result = await structure_module._mcp_predict_structure({"sequence": "MKFLIL"})
        assert "pdb_string" in result
        assert result["num_residues"] == 6

    @pytest.mark.asyncio
    async def test_mcp_predict_complex(self, structure_module: StructureModule):
        result = await structure_module._mcp_predict_complex(
            {"sequences": ["MKFLI", "ACDEF"]}
        )
        assert result["num_residues"] == 10

    @pytest.mark.asyncio
    async def test_mcp_predict_complex_empty(self, structure_module: StructureModule):
        result = await structure_module._mcp_predict_complex({"sequences": []})
        assert "error" in result
