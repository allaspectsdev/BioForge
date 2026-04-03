"""Structure prediction BioForge module: protein folding via ESMFold / OpenFold3."""

from __future__ import annotations

import logging
from typing import Any

from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
)
from bioforge.modules.structure.client import (
    BaseStructureClient,
    MockStructureClient,
    create_structure_client,
)
from bioforge.modules.structure.schemas import (
    ComplexPredictionRequest,
    PDBResultSchema,
    StructurePredictionRequest,
)

logger = logging.getLogger(__name__)


class StructureModule(BioForgeModule):
    """BioForge module for protein structure prediction.

    Capabilities:
        - structure.predict: predict 3-D structure of a single protein chain
        - structure.predict_complex: predict a multi-chain protein complex

    Pipeline steps:
        - structure.fold: fold a protein sequence within a pipeline
    """

    def __init__(
        self,
        client: BaseStructureClient | None = None,
        *,
        mode: str = "auto",
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = create_structure_client(mode=mode)

    # ------------------------------------------------------------------
    # BioForgeModule interface
    # ------------------------------------------------------------------

    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="structure",
            version="0.1.0",
            description="Protein structure prediction via ESMFold API or local OpenFold3",
            author="BioForge",
            tags=["protein", "structure", "folding", "esmfold", "openfold"],
        )

    def capabilities(self) -> list[ModuleCapability]:
        return [
            ModuleCapability(
                name="structure.predict",
                description="Predict the 3-D structure of a single protein chain",
                input_schema=StructurePredictionRequest.model_json_schema(),
                output_schema=PDBResultSchema.model_json_schema(),
                handler=self._handle_predict,
            ),
            ModuleCapability(
                name="structure.predict_complex",
                description="Predict the structure of a multi-chain protein complex",
                input_schema=ComplexPredictionRequest.model_json_schema(),
                output_schema=PDBResultSchema.model_json_schema(),
                handler=self._handle_predict_complex,
            ),
        ]

    def pipeline_steps(self) -> list[ModulePipelineStep]:
        return [
            ModulePipelineStep(
                step_type="structure.fold",
                description="Fold a protein sequence to predict its 3-D structure",
                input_ports={"sequence": "str"},
                output_ports={"pdb_string": "str", "mean_plddt": "float"},
                handler=self._pipeline_fold,
            ),
        ]

    def mcp_tools(self) -> list:
        """Return tool functions for MCP exposure."""
        return [
            self._mcp_predict_structure,
            self._mcp_predict_complex,
        ]

    # ------------------------------------------------------------------
    # Capability handlers
    # ------------------------------------------------------------------

    async def _handle_predict(self, request: dict) -> dict:
        """Handle structure.predict capability invocation."""
        req = StructurePredictionRequest(**request)
        result = await self._client.predict_structure(req.sequence)
        return PDBResultSchema(
            pdb_string=result.pdb_string,
            plddt_scores=result.plddt_scores,
            mean_plddt=result.mean_plddt,
            num_residues=result.num_residues,
        ).model_dump()

    async def _handle_predict_complex(self, request: dict) -> dict:
        """Handle structure.predict_complex capability invocation."""
        req = ComplexPredictionRequest(**request)
        result = await self._client.predict_complex(req.sequences)
        return PDBResultSchema(
            pdb_string=result.pdb_string,
            plddt_scores=result.plddt_scores,
            mean_plddt=result.mean_plddt,
            num_residues=result.num_residues,
        ).model_dump()

    # ------------------------------------------------------------------
    # Pipeline step handler
    # ------------------------------------------------------------------

    async def _pipeline_fold(self, inputs: dict, params: dict) -> dict:
        """Pipeline step: fold a protein sequence."""
        sequence = inputs["sequence"]
        result = await self._client.predict_structure(sequence)
        return {
            "pdb_string": result.pdb_string,
            "mean_plddt": result.mean_plddt,
        }

    # ------------------------------------------------------------------
    # MCP tool functions
    # ------------------------------------------------------------------

    async def _mcp_predict_structure(self, args: dict) -> dict:
        """Predict the 3-D structure of a protein sequence.

        Accepts a dict with key ``sequence`` (str, amino-acid one-letter code).
        Returns PDB string, per-residue pLDDT scores, and mean pLDDT.
        """
        sequence = args.get("sequence", "")
        result = await self._client.predict_structure(sequence)
        return {
            "pdb_string": result.pdb_string,
            "plddt_scores": result.plddt_scores,
            "mean_plddt": result.mean_plddt,
            "num_residues": result.num_residues,
        }

    async def _mcp_predict_complex(self, args: dict) -> dict:
        """Predict the structure of a multi-chain protein complex.

        Accepts a dict with key ``sequences`` (list[str]).
        """
        sequences = args.get("sequences", [])
        if not sequences:
            return {"error": "At least one sequence is required"}
        result = await self._client.predict_complex(sequences)
        return {
            "pdb_string": result.pdb_string,
            "plddt_scores": result.plddt_scores,
            "mean_plddt": result.mean_plddt,
            "num_residues": result.num_residues,
        }
