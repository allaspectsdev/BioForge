"""Type IIS restriction enzyme definitions and NEB ligation fidelity data.

Type IIS enzymes cut outside their recognition sequence, producing defined
sticky-end overhangs used in Golden Gate assembly. The NEB fidelity data
encodes measured ligation specificity between all possible 4bp overhang pairs.

References:
    Potapov et al. (2018) "Comprehensive Profiling of Four Base Overhang
    Ligation Fidelity by T4 DNA Ligase and Application to DNA Assembly."
    ACS Synth. Biol. 7(11):2665-2674.
"""

from dataclasses import dataclass
from itertools import product

from bioforge.modules.assembly.core.models import reverse_complement


@dataclass(frozen=True, slots=True)
class TypeIISEnzyme:
    """A Type IIS restriction enzyme used in Golden Gate assembly.

    Attributes:
        name: Common enzyme name.
        recognition_site: DNA recognition sequence (5' to 3').
        cut_offset_fwd: Cut position on the forward strand relative to the
            end of the recognition site. Positive = downstream.
        cut_offset_rev: Cut position on the reverse strand relative to the
            end of the recognition site. Positive = downstream.
        overhang_length: Length of the resulting single-stranded overhang.
    """

    name: str
    recognition_site: str
    cut_offset_fwd: int
    cut_offset_rev: int
    overhang_length: int

    @property
    def total_cut_fwd(self) -> int:
        """Total distance from start of recognition site to forward cut."""
        return len(self.recognition_site) + self.cut_offset_fwd

    @property
    def total_cut_rev(self) -> int:
        """Total distance from start of recognition site to reverse cut."""
        return len(self.recognition_site) + self.cut_offset_rev


# Standard Type IIS enzymes used in Golden Gate assembly
ENZYMES: dict[str, TypeIISEnzyme] = {
    "BsaI": TypeIISEnzyme(
        name="BsaI",
        recognition_site="GGTCTC",
        cut_offset_fwd=1,
        cut_offset_rev=5,
        overhang_length=4,
    ),
    "BpiI": TypeIISEnzyme(
        name="BpiI",
        recognition_site="GAAGAC",
        cut_offset_fwd=2,
        cut_offset_rev=6,
        overhang_length=4,
    ),
    "BbsI": TypeIISEnzyme(
        name="BbsI",
        recognition_site="GAAGAC",
        cut_offset_fwd=2,
        cut_offset_rev=6,
        overhang_length=4,
    ),
    "Esp3I": TypeIISEnzyme(
        name="Esp3I",
        recognition_site="CGTCTC",
        cut_offset_fwd=1,
        cut_offset_rev=5,
        overhang_length=4,
    ),
    "BsmBI": TypeIISEnzyme(
        name="BsmBI",
        recognition_site="CGTCTC",
        cut_offset_fwd=1,
        cut_offset_rev=5,
        overhang_length=4,
    ),
    "SapI": TypeIISEnzyme(
        name="SapI",
        recognition_site="GCTCTTC",
        cut_offset_fwd=1,
        cut_offset_rev=4,
        overhang_length=3,
    ),
}


# ---------------------------------------------------------------------------
# NEB Ligation Fidelity Model
# ---------------------------------------------------------------------------
# Approximation of the Potapov et al. (2018) 256x256 fidelity matrix for BsaI.
# True cognate pairs (Watson-Crick complement) receive fidelity 1.0.
# Mismatch pairs are scored based on number of mismatched positions:
#   0 mismatches (cognate): 1.0
#   1 mismatch:             0.05 - 0.15 (position-dependent)
#   2 mismatches:           0.001
#   3 mismatches:           0.0001
#   4 mismatches:           0.00001
#
# Single-mismatch penalties are position-dependent: interior mismatches
# (positions 1,2) ligate more readily than terminal mismatches (positions 0,3).

_SINGLE_MISMATCH_BY_POSITION = {
    0: 0.05,   # 5' terminal mismatch — low ligation
    1: 0.15,   # interior position 1 — higher ligation
    2: 0.12,   # interior position 2 — moderately high
    3: 0.06,   # 3' terminal mismatch — low ligation
}


def _all_4bp_overhangs() -> list[str]:
    """Generate all 256 possible 4bp overhangs in lexicographic order."""
    bases = "ACGT"
    return ["".join(combo) for combo in product(bases, repeat=4)]


ALL_4BP_OVERHANGS = _all_4bp_overhangs()
_OVERHANG_INDEX = {oh: i for i, oh in enumerate(ALL_4BP_OVERHANGS)}


def _count_mismatches_by_position(oh1: str, oh2_rc: str) -> list[int]:
    """Return list of positions where oh1 differs from the reverse complement of oh2.

    For cognate pairing, oh1 should equal reverse_complement(oh2), giving
    zero mismatches. Any deviation is a mismatch at that position.
    """
    positions = []
    for i in range(len(oh1)):
        if oh1[i] != oh2_rc[i]:
            positions.append(i)
    return positions


def bsai_fidelity(oh1: str, oh2: str) -> float:
    """Compute the BsaI ligation fidelity between two 4bp overhangs.

    Returns a score from 0.0 to 1.0 representing how readily oh1 will
    ligate with the complement of oh2. A score of 1.0 means oh1 is the
    perfect Watson-Crick complement of oh2 (cognate pair). Lower scores
    indicate increasingly unlikely mis-ligation.

    This approximates the NEB fidelity data from Potapov et al. (2018).

    Args:
        oh1: First 4bp overhang sequence (e.g., "AATG").
        oh2: Second 4bp overhang sequence (e.g., "CATT").

    Returns:
        Ligation fidelity score between 0.0 and 1.0.

    Raises:
        ValueError: If overhangs are not 4bp or contain invalid characters.
    """
    oh1 = oh1.upper()
    oh2 = oh2.upper()

    if len(oh1) != 4 or len(oh2) != 4:
        raise ValueError(
            f"Overhangs must be 4bp, got {len(oh1)}bp and {len(oh2)}bp"
        )
    valid = set("ACGT")
    if not all(c in valid for c in oh1) or not all(c in valid for c in oh2):
        raise ValueError(
            f"Overhangs must contain only A, C, G, T: got '{oh1}', '{oh2}'"
        )

    # Cognate check: oh1 should pair with reverse complement of oh2
    oh2_rc = reverse_complement(oh2)
    mismatch_positions = _count_mismatches_by_position(oh1, oh2_rc)
    n_mismatches = len(mismatch_positions)

    if n_mismatches == 0:
        return 1.0
    elif n_mismatches == 1:
        pos = mismatch_positions[0]
        return _SINGLE_MISMATCH_BY_POSITION.get(pos, 0.10)
    elif n_mismatches == 2:
        return 0.001
    elif n_mismatches == 3:
        return 0.0001
    else:
        return 0.00001


def is_palindromic(overhang: str) -> bool:
    """Check if a 4bp overhang is palindromic (equals its reverse complement).

    Palindromic overhangs self-ligate, which is undesirable in Golden Gate.
    """
    return overhang.upper() == reverse_complement(overhang.upper())


def overhang_fidelity_matrix(overhangs: list[str]) -> list[list[float]]:
    """Compute the full pairwise fidelity matrix for a set of overhangs.

    Returns an NxN matrix where entry [i][j] is the ligation fidelity
    between overhang i and overhang j. Diagonal entries (cognate self-pairs)
    should be 1.0 for well-designed overhang sets.

    Args:
        overhangs: List of 4bp overhang sequences.

    Returns:
        NxN list-of-lists fidelity matrix.
    """
    n = len(overhangs)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            matrix[i][j] = bsai_fidelity(overhangs[i], overhangs[j])
    return matrix
