"""Evo 2 BioForge module: AI-powered genomic embedding, variant scoring, and generation."""

from __future__ import annotations

import logging
from typing import Any

from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
    ValidationResult,
)
from bioforge.modules.evo2.client import BaseEvo2Client, MockEvo2Client, create_evo2_client
from bioforge.modules.evo2.embeddings import EmbeddingService
from bioforge.modules.evo2.schemas import (
    EmbedRequest,
    EmbedResult,
    SequenceGenerateRequest,
    SequenceGenerateResult,
    SimilaritySearchRequest,
    SimilaritySearchResult,
    VariantScanRequest,
    VariantScanResult,
)
from bioforge.modules.evo2.variant_scorer import VariantEffectPredictor

logger = logging.getLogger(__name__)


class Evo2Module(BioForgeModule):
    """BioForge module wrapping the Evo 2 genomic foundation model.

    Capabilities:
        - embed_sequence: compute Evo 2 embeddings
        - find_similar: pgvector cosine similarity search
        - score_variants: delta log-likelihood variant effect prediction
        - generate_sequence: nucleotide sequence generation / completion

    Pipeline steps:
        - evo2.embed: embed a sequence within a pipeline
        - evo2.variant_scan: scan variants over a region within a pipeline
    """

    def __init__(
        self,
        client: BaseEvo2Client | None = None,
        *,
        mode: str = "auto",
        api_key: str | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = create_evo2_client(mode=mode, api_key=api_key)
        self._embedding_service = EmbeddingService(self._client)
        self._variant_predictor = VariantEffectPredictor(self._client)

    # ------------------------------------------------------------------
    # BioForgeModule interface
    # ------------------------------------------------------------------

    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="evo2",
            version="0.2.0",
            description=(
                "Evo 2 genomic foundation model (1B/7B/20B/40B): embedding, "
                "variant effect prediction, and sequence generation"
            ),
            author="BioForge",
            tags=["genomics", "embedding", "variant-effect", "generation", "evo2", "foundation-model"],
        )

    def capabilities(self) -> list[ModuleCapability]:
        return [
            ModuleCapability(
                name="embed_sequence",
                description="Compute an Evo 2 embedding for a nucleotide sequence",
                input_schema=EmbedRequest.model_json_schema(),
                output_schema=EmbedResult.model_json_schema(),
                handler=self._handle_embed,
            ),
            ModuleCapability(
                name="find_similar",
                description="Find similar sequences using pgvector cosine similarity",
                input_schema=SimilaritySearchRequest.model_json_schema(),
                output_schema={"type": "array", "items": SimilaritySearchResult.model_json_schema()},
                handler=self._handle_find_similar,
            ),
            ModuleCapability(
                name="score_variants",
                description="Score the effect of single-nucleotide variants via Evo 2 delta log-likelihoods",
                input_schema=VariantScanRequest.model_json_schema(),
                output_schema=VariantScanResult.model_json_schema(),
                handler=self._handle_score_variants,
            ),
            ModuleCapability(
                name="generate_sequence",
                description="Generate a nucleotide sequence continuation using Evo 2",
                input_schema=SequenceGenerateRequest.model_json_schema(),
                output_schema=SequenceGenerateResult.model_json_schema(),
                handler=self._handle_generate,
            ),
        ]

    def pipeline_steps(self) -> list[ModulePipelineStep]:
        return [
            ModulePipelineStep(
                step_type="evo2.embed",
                description="Embed a nucleotide sequence using Evo 2",
                input_ports={"sequence": "str"},
                output_ports={"embedding": "list[float]"},
                handler=self._pipeline_embed,
            ),
            ModulePipelineStep(
                step_type="evo2.variant_scan",
                description="Scan variant effects in a genomic region using Evo 2",
                input_ports={"sequence": "str"},
                output_ports={"variants": "list[dict]"},
                handler=self._pipeline_variant_scan,
            ),
        ]

    def mcp_tools(self) -> list:
        """Return the four capability handler functions for MCP exposure."""
        return [
            self._mcp_embed_sequence,
            self._mcp_find_similar,
            self._mcp_score_variants,
            self._mcp_generate_sequence,
        ]

    async def validate(self, capability_name: str, result: dict) -> ValidationResult:
        """Validate Evo2 outputs — flag low-confidence predictions."""
        checks = []
        warnings = []
        errors = []

        if capability_name == "score_variants":
            variants = result.get("variants", [])
            checks.append(f"variant_count={len(variants)}")

            low_conf_count = sum(
                1 for v in variants
                if isinstance(v, dict) and v.get("confidence", 1.0) < 0.5
            )
            if low_conf_count > 0:
                pct = round(low_conf_count / max(len(variants), 1) * 100)
                warnings.append(
                    f"{low_conf_count} variants ({pct}%) have confidence < 0.5 — "
                    "interpret with caution (short context, near threshold, or extreme GC)"
                )
            checks.append("confidence_regime_audit")

        elif capability_name == "embed_sequence":
            embedding = result.get("embedding", [])
            dim = result.get("dimension", 0)
            checks.append(f"embedding_dimension={dim}")
            if dim == 0 or not embedding:
                errors.append("Empty embedding returned")
            # Check for degenerate embeddings (all zeros)
            if embedding and all(v == 0.0 for v in embedding[:10]):
                warnings.append("Embedding appears degenerate (leading zeros)")
            checks.append("embedding_non_degenerate")

        return ValidationResult(
            valid=len(errors) == 0,
            checks_performed=checks,
            warnings=warnings,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Capability handlers (invoked via ModuleCapability.handler)
    # ------------------------------------------------------------------

    async def _handle_embed(self, request: dict) -> dict:
        """Handle embed_sequence capability invocation."""
        req = EmbedRequest(**request)
        embedding = await self._client.embed(req.sequence)
        result = EmbedResult(
            sequence_id=req.sequence_id,
            embedding=embedding.tolist(),
            dimension=len(embedding),
        )
        return result.model_dump()

    async def _handle_find_similar(self, request: dict) -> dict:
        """Handle find_similar capability invocation.

        NOTE: requires a database session; in a real invocation the session is
        injected by the capability executor.  Here we accept it from the request
        dict under the ``_session`` key.
        """
        req = SimilaritySearchRequest(**{k: v for k, v in request.items() if not k.startswith("_")})
        query_embedding = await self._client.embed(req.query_sequence)
        session = request.get("_session")
        if session is None:
            return {"error": "Database session required for similarity search"}
        hits = await self._embedding_service.similarity_search(
            query_embedding, req.project_id, req.top_k, session
        )
        return {"results": hits}

    async def _handle_score_variants(self, request: dict) -> dict:
        """Handle score_variants capability invocation."""
        req = VariantScanRequest(**request)
        region_end = req.region_end if req.region_end is not None else len(req.sequence)
        variants = await self._variant_predictor.scan_variants(
            req.sequence, req.region_start, region_end
        )
        result = VariantScanResult(
            sequence_length=len(req.sequence),
            region_start=req.region_start,
            region_end=region_end,
            num_variants_scored=len(variants),
            variants=variants,
        )
        return result.model_dump()

    async def _handle_generate(self, request: dict) -> dict:
        """Handle generate_sequence capability invocation."""
        req = SequenceGenerateRequest(**request)
        generated = await self._client.generate(req.prompt_sequence, req.max_length)
        result = SequenceGenerateResult(
            prompt_length=len(req.prompt_sequence),
            generated_sequence=generated,
            generated_length=len(generated),
            full_sequence=req.prompt_sequence + generated,
        )
        return result.model_dump()

    # ------------------------------------------------------------------
    # Pipeline step handlers
    # ------------------------------------------------------------------

    async def _pipeline_embed(self, inputs: dict, params: dict) -> dict:
        """Pipeline step: embed a sequence."""
        sequence = inputs["sequence"]
        embedding = await self._client.embed(sequence)
        return {"embedding": embedding.tolist()}

    async def _pipeline_variant_scan(self, inputs: dict, params: dict) -> dict:
        """Pipeline step: scan variants in a region."""
        sequence = inputs["sequence"]
        region_start = params.get("region_start", 0)
        region_end = params.get("region_end", len(sequence))
        variants = await self._variant_predictor.scan_variants(
            sequence, region_start, region_end
        )
        return {"variants": variants}

    # ------------------------------------------------------------------
    # MCP tool functions
    # ------------------------------------------------------------------

    async def _mcp_embed_sequence(self, args: dict) -> dict:
        """Compute an Evo 2 embedding for a nucleotide sequence.

        Accepts a dict with key ``sequence`` (str).
        Returns a dict with ``embedding`` (list[float]) and ``dimension`` (int).
        """
        sequence = args.get("sequence", "")
        embedding = await self._client.embed(sequence)
        return {"embedding": embedding.tolist(), "dimension": len(embedding)}

    async def _mcp_find_similar(self, args: dict) -> dict:
        """Find sequences similar to a query using pgvector cosine similarity.

        Accepts ``query_sequence`` (str), ``project_id`` (str), ``top_k`` (int).
        Requires ``_session`` to be injected.
        """
        query_sequence = args.get("query_sequence", "")
        project_id = args.get("project_id")
        top_k = args.get("top_k", 10)
        session = args.get("_session")

        query_embedding = await self._client.embed(query_sequence)

        if session is None:
            return {"error": "Database session required", "results": []}

        from uuid import UUID

        hits = await self._embedding_service.similarity_search(
            query_embedding, UUID(project_id), top_k, session
        )
        return {"results": hits}

    async def _mcp_score_variants(self, args: dict) -> dict:
        """Score single-nucleotide variant effects in a genomic region.

        Accepts ``sequence`` (str), ``region_start`` (int), ``region_end`` (int).
        """
        sequence = args.get("sequence", "")
        region_start = args.get("region_start", 0)
        region_end = args.get("region_end", len(sequence))
        variants = await self._variant_predictor.scan_variants(
            sequence, region_start, region_end
        )
        return {
            "num_variants_scored": len(variants),
            "variants": variants,
        }

    async def _mcp_generate_sequence(self, args: dict) -> dict:
        """Generate a nucleotide sequence continuation using Evo 2.

        Accepts ``prompt_sequence`` (str) and ``max_length`` (int, default 100).
        """
        prompt = args.get("prompt_sequence", "")
        max_length = args.get("max_length", 100)
        generated = await self._client.generate(prompt, max_length)
        return {
            "prompt_length": len(prompt),
            "generated_sequence": generated,
            "generated_length": len(generated),
            "full_sequence": prompt + generated,
        }
