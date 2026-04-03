"""MCP tool definitions for the assembly module."""

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import gc_content, longest_homopolymer, reverse_complement
from bioforge.modules.assembly.core.solver import AssemblySolver
from bioforge.modules.assembly.core.thermo import ThermoEngine


async def design_assembly(args: dict) -> dict:
    """Design a complete Gibson Assembly partition for a DNA sequence.

    Splits the sequence into fragments within [2000, 2500] bp and designs
    orthogonal overhangs at each junction.
    """
    sequence = args.get("sequence", "")
    seed = args.get("seed")
    config_overrides = args.get("constraints", {})

    config = AssemblyConfig(**{
        k: v for k, v in config_overrides.items()
        if hasattr(AssemblyConfig, k) and v is not None
    }) if config_overrides else AssemblyConfig()

    solver = AssemblySolver(config=config, seed=seed)
    result = solver.solve(sequence)

    return {
        "feasible": result.feasible,
        "num_fragments": result.partition.num_fragments,
        "fragments": result.fragments,
        "overhangs": result.overhangs,
        "quality_scores": result.quality_scores,
        "restarts_used": result.restarts_used,
        "total_time_s": result.total_time_s,
        "violations": [
            {"constraint": v.constraint_name, "severity": v.severity.value, "message": v.message}
            for v in result.constraint_result.violations
        ],
    }


async def calculate_tm(args: dict) -> dict:
    """Calculate melting temperature for a DNA sequence using nearest-neighbor thermodynamics."""
    sequence = args.get("sequence", "")
    engine = ThermoEngine()
    tm = engine.calc_tm(sequence)
    gc = gc_content(sequence)
    hp = longest_homopolymer(sequence)
    hairpin_dg = engine.calc_hairpin_dg(sequence)

    return {
        "sequence": sequence,
        "length": len(sequence),
        "tm_celsius": round(tm, 1),
        "gc_content": round(gc, 3),
        "longest_homopolymer": hp,
        "hairpin_dg_kcal": round(hairpin_dg, 2),
    }


async def check_overhang_quality(args: dict) -> dict:
    """Evaluate a set of overhang sequences against quality constraints."""
    overhangs = args.get("overhangs", [])
    engine = ThermoEngine()

    results = []
    for i, seq in enumerate(overhangs):
        seq = seq.upper()
        tm = engine.calc_tm(seq)
        gc = gc_content(seq)
        hp = longest_homopolymer(seq)
        hairpin_dg = engine.calc_hairpin_dg(seq)

        issues = []
        if tm < 50 or tm > 65:
            issues.append(f"Tm {tm:.1f}°C outside [50, 65]")
        if gc < 0.4 or gc > 0.6:
            issues.append(f"GC {gc:.1%} outside [40%, 60%]")
        if hp > 4:
            issues.append(f"Homopolymer run {hp} > 4")
        if hairpin_dg < -2.0:
            issues.append(f"Hairpin ΔG {hairpin_dg:.1f} < -2.0 kcal/mol")

        results.append({
            "index": i,
            "sequence": seq,
            "tm": round(tm, 1),
            "gc": round(gc, 3),
            "homopolymer_run": hp,
            "hairpin_dg": round(hairpin_dg, 2),
            "pass": len(issues) == 0,
            "issues": issues,
        })

    return {"overhangs": results, "all_pass": all(r["pass"] for r in results)}


async def reverse_complement_tool(args: dict) -> dict:
    """Compute the reverse complement of a DNA sequence."""
    sequence = args.get("sequence", "")
    rc = reverse_complement(sequence)
    return {"sequence": sequence, "reverse_complement": rc}
