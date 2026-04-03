"""Codon optimization module for organism-specific DNA sequence design.

Provides codon usage tables, a Codon Adaptation Index (CAI) calculator,
and a beam-search codon optimizer with constraint awareness.
"""

from bioforge.modules.assembly.core.codon.cai import (
    compute_cai,
    compute_relative_adaptiveness_table,
)
from bioforge.modules.assembly.core.codon.optimizer import (
    CodonOptimizationResult,
    CodonOptimizer,
)
from bioforge.modules.assembly.core.codon.tables import (
    AA_TO_CODONS,
    CODON_TABLES,
    GENETIC_CODE,
    codon_frequency,
    get_codon_table,
)

__all__ = [
    "AA_TO_CODONS",
    "CODON_TABLES",
    "CodonOptimizationResult",
    "CodonOptimizer",
    "GENETIC_CODE",
    "codon_frequency",
    "compute_cai",
    "compute_relative_adaptiveness_table",
    "get_codon_table",
]
