"""Tests for data provenance, confidence metadata, validate() hooks, and wet-lab feedback."""

from __future__ import annotations

import pytest

from bioforge.modules.base import DataProvenance, ValidationResult

# ---------------------------------------------------------------------------
# DataProvenance model
# ---------------------------------------------------------------------------


class TestDataProvenance:
    def test_basic_construction(self):
        prov = DataProvenance(
            source="primer3-py 0.6.1",
            method="nearest-neighbor Tm calculation",
        )
        assert prov.source == "primer3-py 0.6.1"
        assert prov.confidence == 1.0
        assert prov.warnings == []

    def test_full_construction(self):
        prov = DataProvenance(
            source="Evo 2-7B",
            method="delta log-likelihood",
            confidence=0.6,
            confidence_notes="short context window (<50 bp)",
            reference="doi:10.1126/science.ado9336",
            reference_data="Evo 2 OpenGenome2",
            warnings=["short_context", "extreme_gc"],
        )
        assert prov.confidence == 0.6
        assert len(prov.warnings) == 2
        assert prov.reference_data == "Evo 2 OpenGenome2"

    def test_default_warnings_is_empty_list(self):
        p1 = DataProvenance(source="a", method="b")
        p2 = DataProvenance(source="c", method="d")
        p1.warnings.append("test")
        assert p2.warnings == []  # no shared mutable default


class TestValidationResult:
    def test_valid_result(self):
        vr = ValidationResult(valid=True, checks_performed=["check1"])
        assert vr.valid
        assert vr.errors == []

    def test_invalid_result(self):
        vr = ValidationResult(
            valid=False,
            checks_performed=["check1"],
            errors=["something broke"],
        )
        assert not vr.valid
        assert "something broke" in vr.errors


# ---------------------------------------------------------------------------
# Assembly provenance in schemas
# ---------------------------------------------------------------------------


class TestAssemblyProvenance:
    def test_assembly_result_has_provenance(self):
        from bioforge.modules.assembly.schemas import AssemblyResult

        result = AssemblyResult(
            feasible=True,
            num_fragments=3,
            fragments=[],
            overhangs=[],
            quality_scores={},
            restarts_used=0,
            total_time_s=0.1,
        )
        assert result.provenance is not None
        assert "primer3" in result.provenance.source.lower()
        assert result.provenance.reference != ""

    def test_assembly_provenance_serializes(self):
        from bioforge.modules.assembly.schemas import AssemblyResult

        result = AssemblyResult(
            feasible=True,
            num_fragments=1,
            fragments=[],
            overhangs=[],
            quality_scores={},
            restarts_used=0,
            total_time_s=0.0,
        )
        d = result.model_dump()
        assert "provenance" in d
        assert d["provenance"]["source"] != ""
        assert d["provenance"]["method"] != ""


# ---------------------------------------------------------------------------
# Evo2 confidence metadata
# ---------------------------------------------------------------------------


class TestEvo2Confidence:
    def test_variant_score_has_confidence_fields(self):
        from bioforge.modules.evo2.schemas import VariantScore

        vs = VariantScore(
            position=10,
            ref_base="A",
            alt_base="T",
            score=-0.3,
            interpretation="neutral",
            confidence=0.7,
            confidence_flags=["near_threshold"],
        )
        assert vs.confidence == 0.7
        assert "near_threshold" in vs.confidence_flags

    def test_variant_scan_result_has_provenance(self):
        from bioforge.modules.evo2.schemas import VariantScanResult

        vsr = VariantScanResult(
            sequence_length=100,
            region_start=0,
            region_end=50,
            num_variants_scored=0,
        )
        assert vsr.provenance is not None
        assert "Evo 2" in vsr.provenance.source

    def test_embed_result_has_provenance(self):
        from bioforge.modules.evo2.schemas import EmbedResult

        er = EmbedResult(embedding=[0.1] * 1536)
        assert er.provenance is not None
        assert "Evo 2" in er.provenance.source


class TestVariantScorerConfidence:
    @pytest.fixture
    def predictor(self):
        from bioforge.modules.evo2.client import MockEvo2Client
        from bioforge.modules.evo2.variant_scorer import VariantEffectPredictor

        return VariantEffectPredictor(MockEvo2Client())

    @pytest.mark.asyncio
    async def test_score_mutation_returns_confidence(self, predictor):
        seq = "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"
        result = await predictor.score_mutation(seq, 30, "T")
        assert "confidence" in result
        assert "confidence_flags" in result
        assert 0 < result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_same_base_has_full_confidence(self, predictor):
        seq = "ATCGATCG"
        result = await predictor.score_mutation(seq, 0, "A")
        assert result["confidence"] == 1.0
        assert result["confidence_flags"] == []

    @pytest.mark.asyncio
    async def test_short_sequence_lowers_confidence(self, predictor):
        # 10 bp is very short context
        seq = "ATCGATCGAT"
        result = await predictor.score_mutation(seq, 5, "G")
        assert result["confidence"] < 1.0
        assert "short_context" in result["confidence_flags"]

    @pytest.mark.asyncio
    async def test_edge_position_lowers_confidence(self, predictor):
        seq = "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"
        result = await predictor.score_mutation(seq, 0, "G")
        assert "near_sequence_edge" in result["confidence_flags"]

    @pytest.mark.asyncio
    async def test_scan_variants_includes_confidence(self, predictor):
        seq = "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"
        results = await predictor.scan_variants(seq, 20, 22)
        assert len(results) > 0
        for r in results:
            assert "confidence" in r
            assert "confidence_flags" in r


class TestConfidenceHelpers:
    def test_gc_content_calculation(self):
        from bioforge.modules.evo2.variant_scorer import _compute_gc_content

        assert _compute_gc_content("GCGC") == 1.0
        assert _compute_gc_content("ATAT") == 0.0
        assert abs(_compute_gc_content("ATGC") - 0.5) < 1e-6
        assert _compute_gc_content("") == 0.0

    def test_assess_confidence_normal(self):
        from bioforge.modules.evo2.variant_scorer import _assess_confidence

        # Normal conditions: long sequence, middle position, moderate score, balanced GC
        conf, flags = _assess_confidence(
            score=-2.0,
            sequence="ATGC" * 50,  # 200 bp, 50% GC
            position=100,
        )
        assert conf == 1.0
        assert flags == []

    def test_assess_confidence_near_threshold(self):
        from bioforge.modules.evo2.variant_scorer import _assess_confidence

        conf, flags = _assess_confidence(
            score=-0.45,  # very close to -0.5 threshold
            sequence="A" * 200,
            position=100,
        )
        assert conf < 1.0
        assert "near_threshold" in flags

    def test_assess_confidence_multiple_flags(self):
        from bioforge.modules.evo2.variant_scorer import _assess_confidence

        # Short sequence + edge position
        conf, flags = _assess_confidence(
            score=-2.0,
            sequence="ATCG" * 5,  # 20 bp
            position=0,
        )
        assert conf < 0.7
        assert "short_context" in flags
        assert "near_sequence_edge" in flags


# ---------------------------------------------------------------------------
# validate() hooks across modules
# ---------------------------------------------------------------------------


class TestAssemblyValidate:
    @pytest.mark.asyncio
    async def test_valid_assembly(self):
        from bioforge.modules.assembly.module import AssemblyModule

        mod = AssemblyModule()
        result = {
            "feasible": True,
            "fragments": [
                {"index": 0, "start": 0, "end": 2500},
                {"index": 1, "start": 2500, "end": 5000},
            ],
            "overhangs": [
                {"index": 0, "tm": 60.0},
                {"index": 1, "tm": 58.5},
            ],
        }
        vr = await mod.validate("design_assembly", result)
        assert vr.valid
        assert len(vr.checks_performed) > 0

    @pytest.mark.asyncio
    async def test_gap_in_fragments_detected(self):
        from bioforge.modules.assembly.module import AssemblyModule

        mod = AssemblyModule()
        result = {
            "feasible": True,
            "fragments": [
                {"index": 0, "start": 0, "end": 2000},
                {"index": 1, "start": 2500, "end": 5000},  # gap!
            ],
            "overhangs": [],
        }
        vr = await mod.validate("design_assembly", result)
        assert not vr.valid
        assert any("Gap" in e for e in vr.errors)

    @pytest.mark.asyncio
    async def test_extreme_tm_warned(self):
        from bioforge.modules.assembly.module import AssemblyModule

        mod = AssemblyModule()
        result = {
            "feasible": True,
            "fragments": [{"index": 0, "start": 0, "end": 5000}],
            "overhangs": [{"index": 0, "tm": 95.0}],  # way too hot
        }
        vr = await mod.validate("design_assembly", result)
        assert any("extreme Tm" in w for w in vr.warnings)


class TestEvo2Validate:
    @pytest.mark.asyncio
    async def test_low_confidence_variants_warned(self):
        from bioforge.modules.evo2.client import MockEvo2Client
        from bioforge.modules.evo2.module import Evo2Module

        mod = Evo2Module(client=MockEvo2Client())
        result = {
            "variants": [
                {"position": 0, "score": -0.3, "confidence": 0.3},
                {"position": 1, "score": -2.0, "confidence": 0.9},
            ],
        }
        vr = await mod.validate("score_variants", result)
        assert vr.valid
        assert any("confidence < 0.5" in w for w in vr.warnings)

    @pytest.mark.asyncio
    async def test_empty_embedding_is_error(self):
        from bioforge.modules.evo2.client import MockEvo2Client
        from bioforge.modules.evo2.module import Evo2Module

        mod = Evo2Module(client=MockEvo2Client())
        result = {"embedding": [], "dimension": 0}
        vr = await mod.validate("embed_sequence", result)
        assert not vr.valid


class TestStructureValidate:
    @pytest.mark.asyncio
    async def test_low_plddt_warned(self):
        from bioforge.modules.structure.module import StructureModule

        mod = StructureModule()
        result = {
            "pdb_string": "ATOM  1  CA  ALA",
            "plddt_scores": [30.0, 25.0, 35.0],
            "mean_plddt": 30.0,
            "num_residues": 3,
        }
        vr = await mod.validate("structure.predict", result)
        assert vr.valid  # low but not fatal
        assert any("pLDDT" in w for w in vr.warnings)

    @pytest.mark.asyncio
    async def test_very_low_plddt_is_error(self):
        from bioforge.modules.structure.module import StructureModule

        mod = StructureModule()
        result = {
            "pdb_string": "ATOM  1  CA  ALA",
            "plddt_scores": [10.0, 15.0],
            "mean_plddt": 12.5,
            "num_residues": 2,
        }
        vr = await mod.validate("structure.predict", result)
        assert not vr.valid


class TestAlignmentValidate:
    @pytest.mark.asyncio
    async def test_valid_alignment(self):
        from bioforge.modules.alignment.module import AlignmentModule

        mod = AlignmentModule()
        result = {
            "aligned_sequences": [
                {"name": "s1", "aligned_sequence": "ATCG-"},
                {"name": "s2", "aligned_sequence": "ATCGA"},
            ],
            "alignment_length": 5,
            "gap_count": 1,
        }
        vr = await mod.validate("pairwise_align", result)
        assert vr.valid

    @pytest.mark.asyncio
    async def test_zero_length_alignment_is_error(self):
        from bioforge.modules.alignment.module import AlignmentModule

        mod = AlignmentModule()
        result = {
            "aligned_sequences": [],
            "alignment_length": 0,
            "gap_count": 0,
        }
        vr = await mod.validate("pairwise_align", result)
        assert not vr.valid


class TestSBOLValidate:
    @pytest.mark.asyncio
    async def test_empty_export_is_error(self):
        from bioforge.modules.sbol.module import SBOLModule

        mod = SBOLModule()
        result = {"sbol3_document": ""}
        vr = await mod.validate("export_sbol", result)
        assert not vr.valid

    @pytest.mark.asyncio
    async def test_valid_export(self):
        from bioforge.modules.sbol.module import SBOLModule

        mod = SBOLModule()
        result = {"sbol3_document": '<rdf:RDF xmlns:rdf="...">...</rdf:RDF>'}
        vr = await mod.validate("export_sbol", result)
        assert vr.valid


class TestVariantsValidate:
    @pytest.mark.asyncio
    async def test_low_confidence_predictions_warned(self):
        from bioforge.modules.variants.module import VariantModule

        mod = VariantModule()
        result = {
            "effects": [
                {"confidence": 0.2, "prediction": "uncertain"},
                {"confidence": 0.8, "prediction": "benign"},
            ],
        }
        vr = await mod.validate("predict_effects", result)
        assert vr.valid
        assert any("confidence < 0.4" in w for w in vr.warnings)


class TestBaseDefaultValidate:
    @pytest.mark.asyncio
    async def test_base_validate_returns_valid(self):
        """BioForgeModule.validate() has a safe default."""
        from bioforge.modules.sbol.module import SBOLModule

        mod = SBOLModule()
        # Call with an unrecognized capability — should hit default path
        vr = await mod.validate("unknown_capability", {})
        assert vr.valid


# ---------------------------------------------------------------------------
# Wet-lab feedback loop
# ---------------------------------------------------------------------------


class TestWetLabFeedback:
    @pytest.fixture
    def experiment_module(self):
        from bioforge.modules.experiments.module import ExperimentModule
        return ExperimentModule()

    @pytest.mark.asyncio
    async def test_record_outcome(self, experiment_module):
        result = await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": True,
            "colony_count": 12,
            "sequence_verified": True,
            "notes": "Clean colonies, correct insert size on gel",
        })
        assert "outcome_id" in result
        assert "recorded_at" in result

    @pytest.mark.asyncio
    async def test_record_failure(self, experiment_module):
        result = await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": False,
            "failure_mode": "no_colonies",
            "notes": "No growth on selective plates",
        })
        assert "outcome_id" in result

    @pytest.mark.asyncio
    async def test_get_outcomes_returns_all(self, experiment_module):
        await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": True,
        })
        await experiment_module._record_outcome({
            "design_type": "golden_gate",
            "success": False,
        })

        result = await experiment_module._get_outcomes({})
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_outcomes_filter_by_type(self, experiment_module):
        await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": True,
        })
        await experiment_module._record_outcome({
            "design_type": "golden_gate",
            "success": True,
        })

        result = await experiment_module._get_outcomes({"design_type": "gibson_assembly"})
        assert result["count"] == 1
        assert result["outcomes"][0]["design_type"] == "gibson_assembly"

    @pytest.mark.asyncio
    async def test_get_outcomes_success_only(self, experiment_module):
        await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": True,
        })
        await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": False,
        })

        result = await experiment_module._get_outcomes({"success_only": True})
        assert result["count"] == 1
        assert result["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, experiment_module):
        await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": True,
        })
        await experiment_module._record_outcome({
            "design_type": "gibson_assembly",
            "success": False,
        })

        result = await experiment_module._get_outcomes({})
        assert result["success_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_outcome_links_to_experiment(self, experiment_module):
        # Create an experiment first
        exp = await experiment_module._create_experiment({
            "name": "Test Gibson",
            "protocol_id": "gibson_assembly_neb_hifi",
        })
        exp_id = exp["experiment_id"]

        # Record outcome linked to it
        await experiment_module._record_outcome({
            "experiment_id": exp_id,
            "design_type": "gibson_assembly",
            "success": True,
        })

        # Experiment should be updated
        stored = experiment_module._experiments[exp_id]
        assert stored["status"] == "completed"
        assert len(stored.get("outcomes", [])) == 1

    @pytest.mark.asyncio
    async def test_failed_outcome_sets_experiment_failed(self, experiment_module):
        exp = await experiment_module._create_experiment({
            "name": "Test Gibson Fail",
            "protocol_id": "gibson_assembly_neb_hifi",
        })
        exp_id = exp["experiment_id"]

        await experiment_module._record_outcome({
            "experiment_id": exp_id,
            "design_type": "gibson_assembly",
            "success": False,
            "failure_mode": "no_colonies",
        })

        assert experiment_module._experiments[exp_id]["status"] == "failed"

    def test_module_has_5_capabilities(self, experiment_module):
        caps = experiment_module.capabilities()
        assert len(caps) == 5
        names = {c.name for c in caps}
        assert "record_outcome" in names
        assert "get_outcomes" in names

    def test_module_has_5_mcp_tools(self, experiment_module):
        tools = experiment_module.mcp_tools()
        assert len(tools) == 5
