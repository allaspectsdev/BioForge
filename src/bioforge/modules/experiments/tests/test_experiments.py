"""Tests for the experiments module: protocols, primer ordering, and ExperimentModule."""

import asyncio

from bioforge.modules.experiments import ExperimentModule
from bioforge.modules.experiments.protocols import ProtocolLibrary
from bioforge.modules.experiments.ordering import PrimerOrderGenerator


class TestProtocols:
    def test_list_protocols(self):
        lib = ProtocolLibrary()
        protocols = lib.list_protocols()

        assert isinstance(protocols, list)
        assert len(protocols) >= 3  # gibson, golden_gate, colony_pcr

    def test_get_gibson_protocol(self):
        lib = ProtocolLibrary()
        protocol = lib.get_protocol("gibson_assembly_neb_hifi")

        assert protocol is not None
        assert len(protocol.steps) > 0

    def test_get_golden_gate_protocol(self):
        lib = ProtocolLibrary()
        protocol = lib.get_protocol("golden_gate_bsai")

        assert protocol is not None
        assert len(protocol.steps) > 0

    def test_unknown_protocol_error(self):
        lib = ProtocolLibrary()
        result = lib.get_protocol("nonexistent")

        assert result is None


class TestPrimerOrdering:
    def test_csv_format(self):
        generator = PrimerOrderGenerator()
        assembly_result = {
            "fragments": [
                {"index": 0, "start": 0, "end": 100},
                {"index": 1, "start": 100, "end": 200},
            ],
            "overhangs": [
                {"index": 0, "sequence": "ATCGATCGATCGATCGATCGATCGA"},
                {"index": 1, "sequence": "GCTAGCTAGCTAGCTAGCTAGCTAG"},
            ],
        }
        order = generator.generate(assembly_result)
        csv = order.to_csv()

        assert "Well Position" in csv
        assert "Name" in csv
        assert "Sequence" in csv

    def test_well_positions(self):
        generator = PrimerOrderGenerator()
        assembly_result = {
            "fragments": [
                {"index": 0, "start": 0, "end": 100},
                {"index": 1, "start": 100, "end": 200},
            ],
            "overhangs": [
                {"index": 0, "sequence": "ATCGATCGATCGATCGATCGATCGA"},
                {"index": 1, "sequence": "GCTAGCTAGCTAGCTAGCTAGCTAG"},
            ],
        }
        order = generator.generate(assembly_result)

        well_positions = [p.well_position for p in order.primers]
        # First two wells should be A01, A02
        if len(well_positions) >= 2:
            assert well_positions[0] == "A01"
            assert well_positions[1] == "A02"


class TestExperimentModule:
    def test_module_info(self):
        mod = ExperimentModule()
        info = mod.info()

        assert info.name == "experiments"

    def test_has_3_capabilities(self):
        mod = ExperimentModule()
        caps = mod.capabilities()

        assert len(caps) == 3

    def test_list_protocols_handler(self):
        mod = ExperimentModule()
        result = asyncio.run(mod._list_protocols({}))

        assert "protocols" in result
        assert "count" in result
        assert result["count"] >= 3
