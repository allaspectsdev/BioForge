from dataclasses import dataclass, field
from enum import Enum


COMPLEMENT = str.maketrans("ATCGatcgNn", "TAGCtagcNn")


def reverse_complement(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


def gc_content(seq: str) -> float:
    s = seq.upper()
    gc = sum(1 for c in s if c in ("G", "C"))
    total = len(s)
    return gc / total if total > 0 else 0.0


def longest_homopolymer(seq: str) -> int:
    if not seq:
        return 0
    max_run = 1
    current_run = 1
    for i in range(1, len(seq)):
        if seq[i] == seq[i - 1]:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    return max_run


@dataclass(frozen=True, slots=True)
class Overhang:
    """A sticky-end overhang at a junction between fragments."""

    sequence: str
    position: int  # Start position in the original sequence
    length: int
    tm: float = 0.0
    gc: float = 0.0
    homopolymer_run: int = 0
    hairpin_dg: float = 0.0  # kcal/mol


@dataclass(frozen=True, slots=True)
class Fragment:
    """A contiguous DNA fragment in the partition."""

    index: int
    start: int  # Inclusive
    end: int  # Exclusive
    length: int


class ConstraintSeverity(Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass
class ConstraintViolation:
    constraint_name: str
    severity: ConstraintSeverity
    message: str
    indices: list[int] = field(default_factory=list)  # Affected fragment/overhang indices


@dataclass
class ConstraintResult:
    passed: bool
    violations: list[ConstraintViolation] = field(default_factory=list)
    score: float = 1.0  # 1.0 = perfect, 0.0 = worst

    @staticmethod
    def ok() -> "ConstraintResult":
        return ConstraintResult(passed=True)

    @staticmethod
    def fail(violations: list[ConstraintViolation]) -> "ConstraintResult":
        return ConstraintResult(passed=False, violations=violations, score=0.0)


@dataclass
class Partition:
    """Boundary-centric representation of a sequence partition.

    boundaries[i] is the position in the original sequence where fragment i ends
    and fragment i+1 begins. overhang_lengths[i] is the overhang length at boundary i.
    """

    sequence_length: int
    boundaries: list[int]  # k-1 boundary positions for k fragments
    overhang_lengths: list[int]  # One per boundary

    @property
    def num_fragments(self) -> int:
        return len(self.boundaries) + 1

    def get_fragments(self) -> list[Fragment]:
        """Materialize Fragment objects from boundaries."""
        fragments = []
        starts = [0] + self.boundaries
        ends = self.boundaries + [self.sequence_length]
        for i, (s, e) in enumerate(zip(starts, ends)):
            fragments.append(Fragment(index=i, start=s, end=e, length=e - s))
        return fragments

    def get_overhang_sequences(self, sequence: str) -> list[str]:
        """Extract overhang sequences at each boundary from the source sequence."""
        overhangs = []
        for boundary, oh_len in zip(self.boundaries, self.overhang_lengths):
            # Overhang is centered on the boundary
            half = oh_len // 2
            start = max(0, boundary - half)
            end = min(self.sequence_length, start + oh_len)
            overhangs.append(sequence[start:end].upper())
        return overhangs

    def get_overhangs(self, sequence: str) -> list[Overhang]:
        """Materialize Overhang objects with basic metrics."""
        result = []
        for i, (boundary, oh_len) in enumerate(
            zip(self.boundaries, self.overhang_lengths)
        ):
            half = oh_len // 2
            start = max(0, boundary - half)
            end = min(self.sequence_length, start + oh_len)
            seq = sequence[start:end].upper()
            result.append(
                Overhang(
                    sequence=seq,
                    position=start,
                    length=len(seq),
                    gc=gc_content(seq),
                    homopolymer_run=longest_homopolymer(seq),
                )
            )
        return result
