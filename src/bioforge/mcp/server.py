"""MCP server exposing BioForge tools to AI agents and external clients.

V2: Dynamic tool registration from all loaded modules via ModuleRegistry.
Also includes direct tool implementations for standalone MCP usage.
"""

from dataclasses import asdict

from fastmcp import FastMCP

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import (
    gc_content,
    longest_homopolymer,
    reverse_complement,
)
from bioforge.modules.assembly.core.solver import AssemblySolver
from bioforge.modules.assembly.core.thermo import ThermoEngine

mcp = FastMCP("BioForge", version="0.3.0")


# ── Assembly Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def design_assembly(
    sequence: str,
    min_fragment_bp: int = 2000,
    max_fragment_bp: int = 2500,
    overhang_length: int = 25,
    seed: int | None = None,
) -> dict:
    """Design a complete Gibson Assembly partition for a DNA sequence.

    Splits the sequence into fragments and designs orthogonal overhangs
    at each junction. Returns fragments, overhangs, and quality metrics.
    """
    try:
        config = AssemblyConfig(
            min_fragment_bp=min_fragment_bp,
            max_fragment_bp=max_fragment_bp,
            default_overhang_bp=overhang_length,
        )
        solver = AssemblySolver(config=config, seed=seed)
        result = solver.solve(sequence)
        return {
            "feasible": result.feasible,
            "num_fragments": result.partition.num_fragments,
            "fragments": result.fragments,
            "overhangs": result.overhangs,
            "quality_scores": result.quality_scores,
            "total_time_s": result.total_time_s,
            "restarts_used": result.restarts_used,
            "violations": [
                {"constraint": v.constraint_name, "severity": v.severity.value, "message": v.message}
                for v in result.constraint_result.violations
            ],
        }
    except Exception as e:
        return {"error": str(e), "feasible": False}


@mcp.tool()
def design_golden_gate(
    parts: list[str],
    enzyme: str = "BsaI",
    seed: int | None = None,
) -> dict:
    """Design Golden Gate Assembly with Type IIS restriction enzyme overhangs.

    Takes a list of part DNA sequences and designs compatible 4bp overhangs
    using the specified enzyme (BsaI, BpiI, Esp3I, or SapI).
    """
    try:
        from bioforge.modules.assembly.core.golden_gate.gg_solver import GoldenGateSolver
        solver = GoldenGateSolver(enzyme_name=enzyme, seed=seed)
        result = solver.solve(parts)
        return asdict(result) if hasattr(result, "__dataclass_fields__") else result
    except ImportError:
        return {"error": "Golden Gate module not available"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def optimize_codons(
    protein_sequence: str,
    organism: str = "ecoli_k12",
) -> dict:
    """Optimize codons for a protein sequence for expression in a target organism.

    Returns optimized DNA sequence with Codon Adaptation Index (CAI) score.
    """
    try:
        from bioforge.modules.assembly.core.codon.optimizer import CodonOptimizer
        opt = CodonOptimizer(organism=organism)
        result = opt.optimize(protein_sequence)
        return asdict(result) if hasattr(result, "__dataclass_fields__") else result
    except ImportError:
        return {"error": "Codon optimization module not available"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def calculate_tm(sequence: str) -> dict:
    """Calculate melting temperature and properties for a DNA oligonucleotide."""
    engine = ThermoEngine()
    return {
        "sequence": sequence,
        "length": len(sequence),
        "tm_celsius": round(engine.calc_tm(sequence), 1),
        "gc_content": round(gc_content(sequence), 3),
        "longest_homopolymer": longest_homopolymer(sequence),
        "hairpin_dg_kcal": round(engine.calc_hairpin_dg(sequence), 2),
    }


@mcp.tool()
def get_reverse_complement(sequence: str) -> str:
    """Get the reverse complement of a DNA sequence."""
    return reverse_complement(sequence)


@mcp.tool()
def check_overhangs(overhangs: list[str]) -> dict:
    """Check a set of overhang sequences against assembly quality constraints.

    Checks melting temperature, GC content, homopolymer runs, and hairpin
    stability for each overhang sequence.
    """
    engine = ThermoEngine()
    results = []
    for i, seq in enumerate(overhangs):
        seq = seq.upper()
        tm = engine.calc_tm(seq)
        gc = gc_content(seq)
        hp = longest_homopolymer(seq)
        hairpin_dg = engine.calc_hairpin_dg(seq)
        results.append({
            "index": i,
            "sequence": seq,
            "tm": round(tm, 1),
            "gc": round(gc, 3),
            "homopolymer_run": hp,
            "hairpin_dg_kcal": round(hairpin_dg, 2),
            "pass": 50 <= tm <= 65 and 0.4 <= gc <= 0.6 and hp <= 4 and hairpin_dg > -2.0,
        })
    return {"overhangs": results, "all_pass": all(r["pass"] for r in results)}


@mcp.tool()
def check_synthesis_feasibility(
    sequences: list[str],
    provider: str = "idt",
) -> dict:
    """Check if DNA sequences are feasible for synthesis by a given provider.

    Returns per-sequence feasibility with specific failure reasons.
    Supported providers: idt, twist, genscript.
    """
    try:
        from bioforge.modules.assembly.core.synthesis.feasibility import SynthesisFeasibilityChecker
        checker = SynthesisFeasibilityChecker()
        batch_result = checker.check_batch(sequences)
        results = []
        for frag in batch_result.fragments:
            best_provider = frag.recommended_provider
            provider_result = frag.provider_results.get(provider) or (
                frag.provider_results.get(best_provider) if best_provider else None
            )
            results.append({
                "fragment_index": frag.fragment_index,
                "sequence_length": frag.sequence_length,
                "gc_content": frag.gc_content,
                "feasible": frag.is_synthesizable,
                "recommended_provider": frag.recommended_provider,
                "provider_results": {
                    name: {
                        "status": r.status.value,
                        "violations": [
                            {"constraint": v.constraint, "message": v.message, "severity": v.severity}
                            for v in r.violations
                        ],
                        "estimated_cost_usd": r.estimated_cost_usd,
                    }
                    for name, r in frag.provider_results.items()
                },
            })
        return {
            "provider": provider,
            "results": results,
            "all_feasible": batch_result.all_feasible,
            "total_estimated_cost_usd": batch_result.total_estimated_cost_usd,
        }
    except ImportError:
        return {"error": "Synthesis module not available"}
    except Exception as e:
        return {"error": str(e)}


# ── Sequence Intelligence Tools ────────────────────────────────────────────


@mcp.tool()
async def embed_sequence(sequence: str) -> dict:
    """Compute an Evo 2 embedding for a DNA sequence.

    Returns a vector representation capturing sequence features for
    similarity search and variant effect prediction.
    """
    try:
        from bioforge.modules.evo2.client import create_evo2_client
        client = create_evo2_client()
        embedding = await client.embed(sequence)
        return {
            "sequence_length": len(sequence),
            "embedding_dim": len(embedding),
            "embedding_preview": embedding[:10].tolist(),
            "status": "computed",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


@mcp.tool()
async def score_variant(
    sequence: str,
    position: int,
    ref_base: str,
    alt_base: str,
) -> dict:
    """Score a single nucleotide variant using Evo 2.

    Uses embedding-based similarity scoring when log-likelihood is unavailable.
    Positive scores suggest the variant is neutral or beneficial.
    Negative scores suggest the variant is deleterious.
    """
    try:
        from bioforge.modules.evo2.client import create_evo2_client
        client = create_evo2_client()
        scores = await client.score_variants(sequence, [(position, ref_base, alt_base)])
        score = scores[0]
        interpretation = "beneficial" if score > 0.5 else "neutral" if score > -0.5 else "deleterious"
        return {
            "position": position,
            "ref": ref_base,
            "alt": alt_base,
            "score": round(score, 4),
            "interpretation": interpretation,
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def predict_structure(sequence: str) -> dict:
    """Predict protein 3D structure.

    Uses available backend (Boltz-2, OpenFold3, or mock) to predict
    protein structure from amino acid sequence. Returns PDB data and
    per-residue confidence scores (pLDDT).
    """
    try:
        from bioforge.modules.structure.client import create_structure_client
        client = create_structure_client()
        result = await client.predict_structure(sequence)
        return {
            "pdb_string": result.pdb_string[:500] + "..." if len(result.pdb_string) > 500 else result.pdb_string,
            "mean_plddt": result.mean_plddt,
            "num_residues": result.num_residues,
            "plddt_summary": {
                "min": round(min(result.plddt_scores), 1) if result.plddt_scores else 0,
                "max": round(max(result.plddt_scores), 1) if result.plddt_scores else 0,
                "mean": result.mean_plddt,
            },
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def search_registry(query: str, limit: int = 10) -> dict:
    """Search SynBioHub for standard biological parts (promoters, RBS, terminators)."""
    try:
        from bioforge.modules.sbol.module import search_synbiohub
        return await search_synbiohub(query, limit)
    except Exception as e:
        return {"error": str(e)}


# ── Variant Tools ──────────────────────────────────────────────────────────


@mcp.tool()
async def annotate_variants(
    reference_sequence: str,
    variants: list[dict],
    features: list[dict] | None = None,
) -> dict:
    """Annotate genetic variants with genomic context and effect classification.

    Each variant should have: chrom, pos, ref, alt.
    Features should have: start, end, type (CDS/GENE/UTR5/UTR3).
    """
    try:
        from bioforge.modules.variants.module import VariantModule
        mod = VariantModule()
        return await mod._annotate_variants({
            "reference_sequence": reference_sequence,
            "variants": variants,
            "features": features or [],
        })
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def predict_variant_effects(
    reference_sequence: str,
    variants: list[dict],
    features: list[dict] | None = None,
    use_evo2: bool = False,
) -> dict:
    """Predict functional effects of genetic variants.

    Combines annotation with conservation scoring and optional Evo 2 scoring.
    """
    try:
        from bioforge.modules.variants.module import VariantModule
        mod = VariantModule()
        return await mod._predict_effects({
            "reference_sequence": reference_sequence,
            "variants": variants,
            "features": features or [],
            "use_evo2": use_evo2,
        })
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def parse_vcf(vcf_content: str, max_variants: int = 1000) -> dict:
    """Parse a VCF format string into structured variant objects."""
    try:
        from bioforge.modules.variants.module import VariantModule
        mod = VariantModule()
        return await mod._load_vcf({
            "vcf_content": vcf_content,
            "max_variants": max_variants,
        })
    except Exception as e:
        return {"error": str(e)}


# ── Alignment Tools ────────────────────────────────────────────────────────


@mcp.tool()
async def pairwise_align(
    sequences: list[str],
    names: list[str] | None = None,
) -> dict:
    """Align two DNA or protein sequences using Needleman-Wunsch global alignment.

    Returns aligned sequences, identity percentage, gap count, and score.
    """
    try:
        from bioforge.modules.alignment.module import AlignmentModule
        mod = AlignmentModule()
        return await mod._pairwise_align({
            "sequences": sequences,
            "names": names or [],
        })
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def multiple_align(sequences: list[str], names: list[str] | None = None) -> dict:
    """Perform progressive multiple sequence alignment.

    Uses iterative pairwise Needleman-Wunsch alignment to build a multiple alignment.
    """
    try:
        from bioforge.modules.alignment.module import AlignmentModule
        mod = AlignmentModule()
        return await mod._multiple_align({
            "sequences": sequences,
            "names": names or [],
        })
    except Exception as e:
        return {"error": str(e)}


# ── Experiment Tools ───────────────────────────────────────────────────────


@mcp.tool()
async def list_protocols() -> dict:
    """List available wet-lab experiment protocols (Gibson Assembly, Golden Gate, Colony PCR)."""
    try:
        from bioforge.modules.experiments.module import ExperimentModule
        mod = ExperimentModule()
        return await mod._list_protocols({})
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def generate_primer_order(
    primers: list[dict],
    plate_format: int = 96,
    provider: str = "idt",
) -> dict:
    """Generate a primer order sheet (IDT plate CSV format).

    Each primer dict should have 'name' and 'sequence' keys.
    """
    try:
        from bioforge.modules.experiments.module import ExperimentModule
        mod = ExperimentModule()
        return await mod._generate_primer_order({
            "primers": primers,
            "plate_format": plate_format,
            "provider": provider,
        })
    except Exception as e:
        return {"error": str(e)}


# ── SBOL Tools ─────────────────────────────────────────────────────────────


@mcp.tool()
async def import_sbol(content: str) -> dict:
    """Import and parse an SBOL3 document, extracting component sequences."""
    try:
        from bioforge.modules.sbol.module import SBOLModule
        mod = SBOLModule()
        return await mod._import_sbol({"content": content})
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def export_sbol(
    name: str,
    sequences: list[dict],
    namespace: str = "https://bioforge.local",
) -> dict:
    """Export sequences as a valid SBOL3 RDF/XML document.

    Each sequence dict should have 'name', 'sequence', and optional 'type' (DNA/RNA/protein).
    """
    try:
        from bioforge.modules.sbol.module import SBOLModule
        mod = SBOLModule()
        return await mod._export_sbol({
            "name": name,
            "sequences": sequences,
            "namespace": namespace,
        })
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
