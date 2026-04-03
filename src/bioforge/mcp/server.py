"""MCP server exposing BioForge tools to AI agents and external clients.

V2: Dynamic tool registration from all loaded modules via ModuleRegistry.
Also includes direct tool implementations for standalone MCP usage.
"""

from fastmcp import FastMCP

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import gc_content, longest_homopolymer, reverse_complement
from bioforge.modules.assembly.core.solver import AssemblySolver
from bioforge.modules.assembly.core.thermo import ThermoEngine

mcp = FastMCP("BioForge", version="0.2.0")


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
        return result
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
        return result
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
    """Check a set of overhang sequences against assembly quality constraints."""
    engine = ThermoEngine()
    results = []
    for i, seq in enumerate(overhangs):
        seq = seq.upper()
        tm = engine.calc_tm(seq)
        gc = gc_content(seq)
        results.append({
            "index": i,
            "sequence": seq,
            "tm": round(tm, 1),
            "gc": round(gc, 3),
            "homopolymer_run": longest_homopolymer(seq),
            "pass": 50 <= tm <= 65 and 0.4 <= gc <= 0.6 and longest_homopolymer(seq) <= 4,
        })
    return {"overhangs": results, "all_pass": all(r["pass"] for r in results)}


@mcp.tool()
def check_synthesis_feasibility(
    sequences: list[str],
    provider: str = "idt",
) -> dict:
    """Check if DNA sequences are feasible for synthesis by a given provider.

    Returns per-sequence feasibility with specific failure reasons.
    """
    try:
        from bioforge.modules.assembly.core.synthesis.feasibility import SynthesisFeasibilityChecker
        checker = SynthesisFeasibilityChecker()
        results = [checker.check(seq, provider) for seq in sequences]
        return {
            "provider": provider,
            "results": results,
            "all_feasible": all(r["feasible"] for r in results),
        }
    except ImportError:
        return {"error": "Synthesis module not available"}
    except Exception as e:
        return {"error": str(e)}


# ── Sequence Intelligence Tools ────────────────────────────────────────────


@mcp.tool()
def embed_sequence(sequence: str) -> dict:
    """Compute an Evo 2 embedding for a DNA sequence.

    Returns a vector representation capturing sequence features for
    similarity search and variant effect prediction.
    """
    try:
        from bioforge.modules.evo2.client import get_evo2_client
        client = get_evo2_client()
        embedding = client.embed(sequence)
        return {
            "sequence_length": len(sequence),
            "embedding_dim": len(embedding),
            "embedding": embedding[:10].tolist(),  # Preview first 10 dims
            "status": "computed",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


@mcp.tool()
def score_variant(
    sequence: str,
    position: int,
    ref_base: str,
    alt_base: str,
) -> dict:
    """Score a single nucleotide variant using Evo 2 log-likelihood ratio.

    Positive scores suggest the variant is neutral or beneficial.
    Negative scores suggest the variant is deleterious.
    """
    try:
        from bioforge.modules.evo2.client import get_evo2_client
        client = get_evo2_client()
        scores = client.score_variants(sequence, [(position, ref_base, alt_base)])
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
def predict_structure(sequence: str) -> dict:
    """Predict protein 3D structure using ESMFold or OpenFold3.

    Returns PDB data and per-residue confidence scores (pLDDT).
    """
    try:
        from bioforge.modules.structure.client import get_structure_client
        client = get_structure_client()
        result = client.predict_structure(sequence)
        return result
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def search_registry(query: str, limit: int = 10) -> dict:
    """Search SynBioHub for standard biological parts (promoters, RBS, terminators)."""
    try:
        from bioforge.modules.sbol.registry import search_synbiohub
        return search_synbiohub(query, limit)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
