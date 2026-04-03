"""Codon Adaptation Index (CAI) calculator.

Implements the Sharp & Li (1987) CAI metric, which measures how well
the codon usage of a gene matches the preferred codon usage of a target
organism. CAI ranges from 0.0 (worst adapted) to 1.0 (perfectly adapted,
using only the most frequent codon for each amino acid).

The CAI is computed as the geometric mean of the relative adaptiveness
values (w_i) for each codon in the sequence:

    CAI = (prod(w_i for i in 1..L))^(1/L)

where w_i = f(codon_i) / f(max_codon_for_aa_i), and L is the number
of codons (excluding stop codons and single-codon amino acids like Met, Trp).

References:
    Sharp PM, Li WH (1987) "The codon adaptation index — a measure of
    directional synonymous codon usage bias, and its potential applications."
    Nucleic Acids Res. 15:1281-1295.
"""

import math

from bioforge.modules.assembly.core.codon.tables import (
    AA_TO_CODONS,
    CODON_TABLES,
    GENETIC_CODE,
)


def _compute_relative_adaptiveness(organism: str) -> dict[str, float]:
    """Compute relative adaptiveness w_i for every codon.

    w_i = freq(codon) / max_freq(codons for same amino acid)

    Codons for Met and Trp (single-codon amino acids) get w=1.0 by definition.
    Stop codons are excluded.

    Args:
        organism: Key into CODON_TABLES.

    Returns:
        Dict mapping each sense codon to its relative adaptiveness (0.0-1.0).
    """
    if organism not in CODON_TABLES:
        raise ValueError(
            f"Unknown organism '{organism}'. "
            f"Available: {', '.join(sorted(CODON_TABLES.keys()))}"
        )

    table = CODON_TABLES[organism]
    w_values: dict[str, float] = {}

    for aa, codons in AA_TO_CODONS.items():
        if aa == "*":
            # Skip stop codons
            continue

        # Find maximum frequency for this amino acid
        max_freq = max(table.get(c, 0.0) for c in codons)
        if max_freq == 0.0:
            # Fallback: assign equal weight
            for c in codons:
                w_values[c] = 1.0 / len(codons)
            continue

        for c in codons:
            freq = table.get(c, 0.0)
            w_values[c] = freq / max_freq if max_freq > 0 else 0.0

    return w_values


def compute_cai(dna_sequence: str, organism: str) -> float:
    """Compute the Codon Adaptation Index for a DNA sequence.

    Args:
        dna_sequence: DNA coding sequence (must be in-frame, length
            divisible by 3). Only sense codons (not stop) contribute.
        organism: Target organism name (key into CODON_TABLES).

    Returns:
        CAI score from 0.0 to 1.0. Higher values indicate better codon
        adaptation to the target organism.

    Raises:
        ValueError: If organism is unknown or sequence length is not
            divisible by 3.
    """
    seq = dna_sequence.upper().replace(" ", "").replace("\n", "")

    if len(seq) % 3 != 0:
        raise ValueError(
            f"Sequence length ({len(seq)}) is not divisible by 3. "
            f"Provide an in-frame coding sequence."
        )

    if len(seq) < 3:
        raise ValueError("Sequence must contain at least one codon.")

    w_values = _compute_relative_adaptiveness(organism)

    # Extract codons and compute geometric mean of w values
    log_sum = 0.0
    codon_count = 0

    for i in range(0, len(seq), 3):
        codon = seq[i:i + 3]
        if len(codon) != 3:
            continue

        aa = GENETIC_CODE.get(codon)
        if aa is None or aa == "*":
            # Skip unknown or stop codons
            continue

        # Skip single-codon amino acids (Met, Trp) — they don't
        # contribute discriminatory information to CAI
        if aa in ("M", "W"):
            continue

        w = w_values.get(codon, 0.0)
        if w <= 0.0:
            # Avoid log(0): treat as extremely rare codon
            w = 0.001

        log_sum += math.log(w)
        codon_count += 1

    if codon_count == 0:
        return 0.0

    # CAI = geometric mean = exp(mean of log values)
    cai = math.exp(log_sum / codon_count)
    return min(1.0, max(0.0, cai))


def compute_relative_adaptiveness_table(
    organism: str,
) -> dict[str, dict[str, float]]:
    """Get the full relative adaptiveness table organized by amino acid.

    Useful for inspecting which codons are preferred for each amino acid
    in a given organism.

    Args:
        organism: Target organism name.

    Returns:
        Nested dict: {amino_acid: {codon: w_value, ...}, ...}
    """
    w_values = _compute_relative_adaptiveness(organism)

    result: dict[str, dict[str, float]] = {}
    for aa, codons in AA_TO_CODONS.items():
        if aa == "*":
            continue
        result[aa] = {c: w_values.get(c, 0.0) for c in codons}

    return result
