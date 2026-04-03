"""Schemas for the variants module."""

from pydantic import BaseModel, Field


class Variant(BaseModel):
    """A single genetic variant."""

    chrom: str = Field(description="Chromosome or contig name")
    pos: int = Field(description="1-based position on the chromosome")
    ref: str = Field(description="Reference allele")
    alt: str = Field(description="Alternate allele")
    id: str = Field(default=".", description="Variant identifier")
    qual: float = Field(default=0.0, description="Quality score")
    filter: str = Field(default="PASS", description="Filter status")
    info: dict = Field(default_factory=dict, description="Additional info fields")


class VariantAnnotation(BaseModel):
    """Annotation for a single variant."""

    variant: Variant
    region: str = Field(
        description="Genomic region: coding, noncoding, intergenic, utr5, utr3, intron, promoter"
    )
    effect: str = Field(
        default="unknown",
        description="Effect type: synonymous, nonsynonymous, frameshift, nonsense, splice, noncoding",
    )
    codon_ref: str = Field(default="", description="Reference codon (if coding)")
    codon_alt: str = Field(default="", description="Alternate codon (if coding)")
    aa_ref: str = Field(default="", description="Reference amino acid (if coding)")
    aa_alt: str = Field(default="", description="Alternate amino acid (if coding)")
    aa_position: int = Field(default=0, description="Amino acid position (if coding)")
    gene: str = Field(default="", description="Gene name if available")
    impact: str = Field(
        default="unknown",
        description="Impact severity: high, moderate, low, modifier",
    )


class VCFImportRequest(BaseModel):
    """Request to parse a VCF format string into structured variants."""

    vcf_content: str = Field(description="VCF file content as a string")
    max_variants: int = Field(
        default=10000,
        ge=1,
        description="Maximum number of variants to parse",
    )


class VariantEffectResult(BaseModel):
    """Result of variant effect prediction."""

    variant: Variant
    annotation: VariantAnnotation
    conservation_score: float = Field(
        default=0.0,
        description="Conservation score (0-1, higher = more conserved)",
    )
    evo2_score: float | None = Field(
        default=None,
        description="Evo2 model score (if available)",
    )
    prediction: str = Field(
        default="unknown",
        description="Effect prediction: benign, likely_benign, uncertain, likely_pathogenic, pathogenic",
    )
    confidence: float = Field(
        default=0.0,
        description="Prediction confidence (0-1)",
    )


class AnnotateVariantsRequest(BaseModel):
    """Request to annotate a list of variants."""

    variants: list[Variant]
    reference_sequence: str = Field(
        default="",
        description="Reference DNA sequence for determining coding context",
    )
    features: list[dict] = Field(
        default_factory=list,
        description=(
            "Genomic features as dicts with keys: type, start, end, strand, name. "
            "type can be: CDS, gene, mRNA, exon, promoter, UTR5, UTR3"
        ),
    )


class PredictEffectsRequest(BaseModel):
    """Request to predict variant effects."""

    variants: list[Variant]
    reference_sequence: str = Field(
        default="",
        description="Reference DNA sequence",
    )
    features: list[dict] = Field(
        default_factory=list,
        description="Genomic features for annotation context",
    )
    use_evo2: bool = Field(
        default=False,
        description="Whether to attempt Evo2 scoring (requires evo2 module)",
    )
