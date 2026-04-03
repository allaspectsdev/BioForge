"""Variants module: annotation, effect prediction, and VCF parsing."""

from __future__ import annotations

import logging
from typing import Any

from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
)
from bioforge.modules.variants.schemas import (
    AnnotateVariantsRequest,
    PredictEffectsRequest,
    Variant,
    VariantAnnotation,
    VariantEffectResult,
    VCFImportRequest,
)

logger = logging.getLogger(__name__)

# Standard genetic code
CODON_TABLE: dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def _translate_codon(codon: str) -> str:
    """Translate a 3-letter DNA codon to a single amino acid character."""
    return CODON_TABLE.get(codon.upper(), "X")


def _reverse_complement(seq: str) -> str:
    """Return the reverse complement of a DNA sequence."""
    comp = {"A": "T", "T": "A", "G": "C", "C": "G",
            "a": "t", "t": "a", "g": "c", "c": "g", "N": "N", "n": "n"}
    return "".join(comp.get(b, "N") for b in reversed(seq))


class VariantModule(BioForgeModule):
    """Module for variant annotation, effect prediction, and VCF import.

    Provides capabilities to:
    - Annotate variants as coding/noncoding, synonymous/nonsynonymous/frameshift
    - Predict variant effects (with optional Evo2 integration)
    - Parse VCF format strings into structured variant lists
    """

    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="variants",
            version="0.1.0",
            description="Genetic variant annotation, effect prediction, and VCF import",
            author="BioForge",
            tags=["variants", "mutation", "snp", "vcf", "annotation", "effect"],
        )

    def capabilities(self) -> list[ModuleCapability]:
        return [
            ModuleCapability(
                name="annotate_variants",
                description=(
                    "Annotate a list of variants with genomic context. Determines if each "
                    "variant is in a coding or noncoding region, and for coding variants "
                    "classifies as synonymous, nonsynonymous, frameshift, or nonsense."
                ),
                input_schema=AnnotateVariantsRequest.model_json_schema(),
                output_schema={
                    "type": "object",
                    "properties": {
                        "annotations": {"type": "array"},
                        "summary": {"type": "object"},
                    },
                },
                handler=self._annotate_variants,
            ),
            ModuleCapability(
                name="predict_effects",
                description=(
                    "Predict the functional effects of variants. Combines annotation "
                    "with conservation scoring and optional Evo2 deep learning scoring."
                ),
                input_schema=PredictEffectsRequest.model_json_schema(),
                output_schema={
                    "type": "object",
                    "properties": {"effects": {"type": "array"}},
                },
                handler=self._predict_effects,
            ),
            ModuleCapability(
                name="load_vcf",
                description=(
                    "Parse a VCF format string into a structured list of Variant objects. "
                    "Handles standard VCF 4.x format."
                ),
                input_schema=VCFImportRequest.model_json_schema(),
                output_schema={
                    "type": "object",
                    "properties": {
                        "variants": {"type": "array"},
                        "count": {"type": "integer"},
                    },
                },
                handler=self._load_vcf,
            ),
        ]

    def pipeline_steps(self) -> list[ModulePipelineStep]:
        return [
            ModulePipelineStep(
                step_type="variants.annotate",
                description="Annotate variants with genomic context and effect classification",
                input_ports={"variants": "list[Variant]", "reference_sequence": "str"},
                output_ports={"annotations": "list[VariantAnnotation]"},
                handler=self._annotate_variants_step,
            ),
        ]

    def mcp_tools(self) -> list:
        return [self._annotate_variants, self._predict_effects, self._load_vcf]

    # ------------------------------------------------------------------
    # Capability handlers
    # ------------------------------------------------------------------

    async def _annotate_variants(self, request: dict) -> dict:
        """Annotate variants with genomic context."""
        req = AnnotateVariantsRequest(**request)
        annotations = []

        for variant in req.variants:
            ann = self._annotate_single(variant, req.reference_sequence, req.features)
            annotations.append(ann.model_dump())

        # Summary
        effect_counts: dict[str, int] = {}
        impact_counts: dict[str, int] = {}
        for ann in annotations:
            effect = ann["effect"]
            impact = ann["impact"]
            effect_counts[effect] = effect_counts.get(effect, 0) + 1
            impact_counts[impact] = impact_counts.get(impact, 0) + 1

        return {
            "annotations": annotations,
            "summary": {
                "total_variants": len(annotations),
                "effect_counts": effect_counts,
                "impact_counts": impact_counts,
            },
        }

    async def _predict_effects(self, request: dict) -> dict:
        """Predict functional effects of variants."""
        req = PredictEffectsRequest(**request)
        effects = []

        for variant in req.variants:
            ann = self._annotate_single(variant, req.reference_sequence, req.features)

            # Conservation score (simple mock based on position)
            conservation = self._mock_conservation_score(variant)

            # Evo2 integration
            evo2_score: float | None = None
            if req.use_evo2:
                evo2_score = await self._get_evo2_score(variant, req.reference_sequence)

            # Prediction logic
            prediction, confidence = self._predict_pathogenicity(
                ann, conservation, evo2_score
            )

            effect = VariantEffectResult(
                variant=variant,
                annotation=ann,
                conservation_score=conservation,
                evo2_score=evo2_score,
                prediction=prediction,
                confidence=confidence,
            )
            effects.append(effect.model_dump())

        return {"effects": effects}

    async def _load_vcf(self, request: dict) -> dict:
        """Parse VCF format string into structured variant list."""
        req = VCFImportRequest(**request)
        variants = []

        for line in req.vcf_content.strip().splitlines():
            if line.startswith("#"):
                continue

            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue

            chrom = parts[0]
            try:
                pos = int(parts[1])
            except ValueError:
                continue
            var_id = parts[2] if len(parts) > 2 else "."
            ref = parts[3]
            alt = parts[4]

            qual = 0.0
            if len(parts) > 5 and parts[5] != ".":
                try:
                    qual = float(parts[5])
                except ValueError:
                    pass

            filt = parts[6] if len(parts) > 6 else "."

            info_dict: dict[str, Any] = {}
            if len(parts) > 7 and parts[7] != ".":
                for field in parts[7].split(";"):
                    if "=" in field:
                        k, v = field.split("=", 1)
                        info_dict[k] = v
                    else:
                        info_dict[field] = True

            # Handle multi-allelic: split on comma
            for alt_allele in alt.split(","):
                variants.append(
                    Variant(
                        chrom=chrom,
                        pos=pos,
                        ref=ref,
                        alt=alt_allele.strip(),
                        id=var_id,
                        qual=qual,
                        filter=filt,
                        info=info_dict,
                    ).model_dump()
                )

                if len(variants) >= req.max_variants:
                    break

            if len(variants) >= req.max_variants:
                break

        return {"variants": variants, "count": len(variants)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _annotate_single(
        self,
        variant: Variant,
        reference_sequence: str,
        features: list[dict],
    ) -> VariantAnnotation:
        """Annotate a single variant against the reference and features."""
        pos_0 = variant.pos - 1  # Convert to 0-based

        # Find overlapping features
        overlapping_cds: list[dict] = []
        overlapping_other: list[dict] = []
        gene_name = ""

        for feat in features:
            feat_start = feat.get("start", 0)
            feat_end = feat.get("end", 0)
            feat_type = feat.get("type", "").upper()

            if feat_start <= variant.pos <= feat_end:
                if feat_type == "CDS":
                    overlapping_cds.append(feat)
                elif feat_type == "GENE":
                    gene_name = feat.get("name", "")
                else:
                    overlapping_other.append(feat)

        # Determine region type
        if overlapping_cds:
            region = "coding"
        else:
            # Check for other feature types
            region_types = {f.get("type", "").upper() for f in overlapping_other}
            if "UTR5" in region_types or "5UTR" in region_types:
                region = "utr5"
            elif "UTR3" in region_types or "3UTR" in region_types:
                region = "utr3"
            elif "INTRON" in region_types:
                region = "intron"
            elif "PROMOTER" in region_types:
                region = "promoter"
            elif overlapping_other:
                region = "noncoding"
            else:
                region = "intergenic"

        # For coding variants, determine effect
        effect = "noncoding"
        codon_ref = ""
        codon_alt = ""
        aa_ref = ""
        aa_alt = ""
        aa_position = 0
        impact = "modifier"

        if region == "coding" and reference_sequence and overlapping_cds:
            cds = overlapping_cds[0]
            cds_start = cds.get("start", 1) - 1  # 0-based
            strand = cds.get("strand", "+")

            # Position within CDS
            if strand == "+":
                cds_offset = pos_0 - cds_start
            else:
                cds_end = cds.get("end", len(reference_sequence))
                cds_offset = (cds_end - 1) - pos_0

            if cds_offset >= 0:
                codon_pos = cds_offset // 3
                codon_phase = cds_offset % 3
                aa_position = codon_pos + 1

                # Extract reference codon
                if strand == "+":
                    codon_start = cds_start + (codon_pos * 3)
                else:
                    codon_end_pos = cds.get("end", len(reference_sequence)) - (codon_pos * 3)
                    codon_start = codon_end_pos - 3

                if 0 <= codon_start and codon_start + 3 <= len(reference_sequence):
                    codon_ref_seq = reference_sequence[codon_start:codon_start + 3].upper()
                    if strand == "-":
                        codon_ref_seq = _reverse_complement(codon_ref_seq)
                    codon_ref = codon_ref_seq

                    # Determine variant type
                    ref_len = len(variant.ref)
                    alt_len = len(variant.alt)

                    if ref_len == 1 and alt_len == 1:
                        # SNV
                        codon_alt_list = list(codon_ref)
                        if codon_phase < len(codon_alt_list):
                            if strand == "+":
                                codon_alt_list[codon_phase] = variant.alt.upper()
                            else:
                                comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
                                codon_alt_list[codon_phase] = comp.get(
                                    variant.alt.upper(), "N"
                                )
                        codon_alt = "".join(codon_alt_list)

                        aa_ref = _translate_codon(codon_ref)
                        aa_alt = _translate_codon(codon_alt)

                        if aa_ref == aa_alt:
                            effect = "synonymous"
                            impact = "low"
                        elif aa_alt == "*":
                            effect = "nonsense"
                            impact = "high"
                        else:
                            effect = "nonsynonymous"
                            impact = "moderate"
                    elif (ref_len - alt_len) % 3 != 0:
                        effect = "frameshift"
                        impact = "high"
                    else:
                        effect = "inframe_indel"
                        impact = "moderate"
        elif region in ("utr5", "utr3"):
            effect = "utr"
            impact = "modifier"
        elif region == "promoter":
            effect = "regulatory"
            impact = "moderate"

        return VariantAnnotation(
            variant=variant,
            region=region,
            effect=effect,
            codon_ref=codon_ref,
            codon_alt=codon_alt,
            aa_ref=aa_ref,
            aa_alt=aa_alt,
            aa_position=aa_position,
            gene=gene_name,
            impact=impact,
        )

    @staticmethod
    def _mock_conservation_score(variant: Variant) -> float:
        """Generate a mock conservation score based on variant properties.

        In production, this would query a conservation database or compute
        from a multiple sequence alignment.
        """
        # Simple heuristic: shorter ref/alt = more likely conserved position
        length_factor = 1.0 / (1.0 + abs(len(variant.ref) - len(variant.alt)))
        # Use position to add some variation
        pos_factor = (variant.pos % 10) / 10.0
        return round(min(1.0, length_factor * 0.5 + pos_factor * 0.5), 3)

    async def _get_evo2_score(
        self, variant: Variant, reference_sequence: str
    ) -> float | None:
        """Attempt to get Evo2 variant effect score.

        Tries to import and use the Evo2 module if available.
        Returns None if Evo2 is not installed.
        """
        try:
            from bioforge.modules.evo2.client import get_evo2_client

            client = get_evo2_client()
            scores = client.score_variants(
                reference_sequence,
                [(variant.pos, variant.ref, variant.alt)],
            )
            return round(scores[0], 4) if scores else None
        except (ImportError, AttributeError, Exception):
            logger.debug("Evo2 module not available for variant scoring")
            return None

    @staticmethod
    def _predict_pathogenicity(
        annotation: VariantAnnotation,
        conservation: float,
        evo2_score: float | None,
    ) -> tuple[str, float]:
        """Predict pathogenicity from annotation and scores.

        Returns (prediction_label, confidence).
        """
        # Start with annotation-based scoring
        base_score = 0.0
        if annotation.impact == "high":
            base_score = 0.8
        elif annotation.impact == "moderate":
            base_score = 0.5
        elif annotation.impact == "low":
            base_score = 0.2
        else:
            base_score = 0.1

        # Weight in conservation
        combined = base_score * 0.5 + conservation * 0.3

        # Weight in Evo2 if available
        if evo2_score is not None:
            combined = combined * 0.6 + evo2_score * 0.4
            confidence = 0.7  # Higher confidence with Evo2
        else:
            combined += 0.1  # Small boost for incomplete data
            confidence = 0.4

        # Map score to prediction
        if combined >= 0.8:
            prediction = "pathogenic"
            confidence = min(confidence + 0.2, 1.0)
        elif combined >= 0.6:
            prediction = "likely_pathogenic"
        elif combined >= 0.4:
            prediction = "uncertain"
        elif combined >= 0.2:
            prediction = "likely_benign"
        else:
            prediction = "benign"
            confidence = min(confidence + 0.1, 1.0)

        return prediction, round(confidence, 2)

    # ------------------------------------------------------------------
    # Pipeline step handlers
    # ------------------------------------------------------------------

    async def _annotate_variants_step(self, inputs: dict, params: dict) -> dict:
        """Pipeline step handler for variant annotation."""
        request = {
            "variants": inputs["variants"],
            "reference_sequence": inputs.get("reference_sequence", ""),
            "features": inputs.get("features", []),
            **params,
        }
        result = await self._annotate_variants(request)
        return {"annotations": result["annotations"]}
