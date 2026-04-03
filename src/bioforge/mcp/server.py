"""MCP server exposing BioForge tools to AI agents and external clients."""

from fastmcp import FastMCP

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import gc_content, longest_homopolymer, reverse_complement
from bioforge.modules.assembly.core.solver import AssemblySolver
from bioforge.modules.assembly.core.thermo import ThermoEngine

mcp = FastMCP("BioForge", version="0.1.0")


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
    }


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
