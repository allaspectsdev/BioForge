"""DNA synthesis provider abstractions and concrete implementations.

Defines the interface for querying synthesis providers about sequence
feasibility, along with concrete implementations encoding real-world
constraints from IDT, Twist Bioscience, and GenScript.

Provider constraints are based on published product specifications:
- IDT gBlocks: up to 3000bp, GC 25-65%, no homopolymers >20bp
- IDT eBlocks: up to 5000bp, same GC/homopolymer constraints
- Twist: up to 5000bp, GC 25-65%
- GenScript: up to 12000bp (gene synthesis), GC 15-90%
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from bioforge.modules.assembly.core.models import gc_content, longest_homopolymer


class ProductType(Enum):
    """Synthesis product types."""

    GBLOCK = "gBlock"        # IDT gBlocks Gene Fragments
    EBLOCK = "eBlock"        # IDT eBlocks Gene Fragments
    GENE = "gene"            # Full gene synthesis
    OLIGO = "oligo"          # Oligonucleotide
    FRAGMENT = "fragment"    # Generic fragment


class FeasibilityStatus(Enum):
    """Overall feasibility determination."""

    FEASIBLE = "feasible"
    MARGINAL = "marginal"      # May require manual review
    INFEASIBLE = "infeasible"


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    """A specific constraint violation found during feasibility checking."""

    constraint: str
    message: str
    severity: str  # "error" or "warning"
    position: int | None = None  # Position in sequence, if applicable


@dataclass
class FeasibilityResult:
    """Result of a synthesis feasibility check for a single sequence.

    Attributes:
        provider: Name of the synthesis provider.
        product_type: Recommended product type for this sequence.
        status: Overall feasibility status.
        violations: List of specific constraint violations.
        sequence_length: Length of the checked sequence.
        gc_content: GC content of the sequence.
        estimated_cost_usd: Rough cost estimate, if available.
    """

    provider: str
    product_type: ProductType
    status: FeasibilityStatus
    violations: list[ConstraintViolation] = field(default_factory=list)
    sequence_length: int = 0
    gc_content: float = 0.0
    estimated_cost_usd: float | None = None

    @property
    def is_feasible(self) -> bool:
        return self.status == FeasibilityStatus.FEASIBLE

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")


class SynthesisProvider(ABC):
    """Abstract base for DNA synthesis providers.

    Subclasses implement the specific constraint checking logic for
    each provider's product specifications.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @abstractmethod
    def check_feasibility(self, sequence: str) -> FeasibilityResult:
        """Check if a sequence can be synthesized by this provider.

        Args:
            sequence: DNA sequence to check.

        Returns:
            FeasibilityResult with detailed constraint analysis.
        """
        ...

    def _find_repeats(
        self,
        sequence: str,
        min_repeat_length: int = 10,
        max_repeat_count: int = 5,
    ) -> list[ConstraintViolation]:
        """Find repeated subsequences that may cause synthesis difficulties.

        Scans for any subsequence of `min_repeat_length` or longer that
        appears more than `max_repeat_count` times.
        """
        violations = []
        seq = sequence.upper()

        # Check for exact repeats of various lengths
        for repeat_len in range(min_repeat_length, min(30, len(seq) // 2) + 1):
            seen: dict[str, list[int]] = {}
            for i in range(len(seq) - repeat_len + 1):
                subseq = seq[i:i + repeat_len]
                if subseq not in seen:
                    seen[subseq] = []
                seen[subseq].append(i)

            for subseq, positions in seen.items():
                if len(positions) > max_repeat_count:
                    violations.append(
                        ConstraintViolation(
                            constraint="repeat",
                            message=(
                                f"{repeat_len}bp sequence '{subseq[:20]}...' "
                                f"repeated {len(positions)} times "
                                f"(max {max_repeat_count})"
                            ),
                            severity="error",
                            position=positions[0],
                        )
                    )
                    break  # One violation per repeat length is sufficient

        return violations


class IDTProvider(SynthesisProvider):
    """Integrated DNA Technologies (IDT) synthesis feasibility checker.

    Encodes real IDT product constraints:
    - gBlocks: 125-3000bp, GC 25-65%, no homopolymers >20bp
    - eBlocks: 300-5000bp, GC 25-65%, no homopolymers >20bp
    - Oligos: up to 200bp
    - Max 5 repeats of any 10bp+ subsequence
    """

    @property
    def name(self) -> str:
        return "IDT"

    def check_feasibility(self, sequence: str) -> FeasibilityResult:
        """Check sequence against IDT synthesis constraints."""
        seq = sequence.upper().replace(" ", "").replace("\n", "")
        violations: list[ConstraintViolation] = []
        seq_len = len(seq)
        gc = gc_content(seq)
        max_homo = longest_homopolymer(seq)

        # Determine product type
        if seq_len <= 200:
            product = ProductType.OLIGO
        elif seq_len <= 3000:
            product = ProductType.GBLOCK
        else:
            product = ProductType.EBLOCK

        # Length constraints
        if product == ProductType.GBLOCK:
            if seq_len < 125:
                violations.append(
                    ConstraintViolation(
                        constraint="length",
                        message=f"gBlock minimum length is 125bp, got {seq_len}bp",
                        severity="error",
                    )
                )
            if seq_len > 3000:
                violations.append(
                    ConstraintViolation(
                        constraint="length",
                        message=f"gBlock maximum length is 3000bp, got {seq_len}bp",
                        severity="error",
                    )
                )
        elif product == ProductType.EBLOCK:
            if seq_len < 300:
                violations.append(
                    ConstraintViolation(
                        constraint="length",
                        message=f"eBlock minimum length is 300bp, got {seq_len}bp",
                        severity="error",
                    )
                )
            if seq_len > 5000:
                violations.append(
                    ConstraintViolation(
                        constraint="length",
                        message=f"eBlock maximum length is 5000bp, got {seq_len}bp",
                        severity="error",
                    )
                )

        # GC content (applies to all IDT products)
        if gc < 0.25:
            violations.append(
                ConstraintViolation(
                    constraint="gc_content",
                    message=f"GC content {gc:.1%} below IDT minimum of 25%",
                    severity="error",
                )
            )
        elif gc > 0.65:
            violations.append(
                ConstraintViolation(
                    constraint="gc_content",
                    message=f"GC content {gc:.1%} above IDT maximum of 65%",
                    severity="error",
                )
            )

        # Homopolymer runs
        if max_homo > 20:
            violations.append(
                ConstraintViolation(
                    constraint="homopolymer",
                    message=(
                        f"Homopolymer run of {max_homo}bp exceeds "
                        f"IDT maximum of 20bp"
                    ),
                    severity="error",
                )
            )
        elif max_homo > 15:
            violations.append(
                ConstraintViolation(
                    constraint="homopolymer",
                    message=(
                        f"Homopolymer run of {max_homo}bp may cause "
                        f"synthesis difficulty (warning at >15bp)"
                    ),
                    severity="warning",
                )
            )

        # Repeat sequences
        repeat_violations = self._find_repeats(
            seq, min_repeat_length=10, max_repeat_count=5
        )
        violations.extend(repeat_violations)

        # Local GC extremes (sliding window)
        window_size = 100
        if seq_len >= window_size:
            for i in range(0, seq_len - window_size + 1, 50):
                window = seq[i:i + window_size]
                window_gc = gc_content(window)
                if window_gc < 0.15 or window_gc > 0.80:
                    violations.append(
                        ConstraintViolation(
                            constraint="local_gc",
                            message=(
                                f"Extreme local GC ({window_gc:.1%}) in "
                                f"100bp window at position {i}"
                            ),
                            severity="warning",
                            position=i,
                        )
                    )
                    break  # One warning is enough

        # Invalid characters
        invalid = set(seq) - set("ACGTN")
        if invalid:
            violations.append(
                ConstraintViolation(
                    constraint="characters",
                    message=f"Invalid characters in sequence: {invalid}",
                    severity="error",
                )
            )

        # Determine status
        error_count = sum(1 for v in violations if v.severity == "error")
        warning_count = sum(1 for v in violations if v.severity == "warning")

        if error_count > 0:
            status = FeasibilityStatus.INFEASIBLE
        elif warning_count > 0:
            status = FeasibilityStatus.MARGINAL
        else:
            status = FeasibilityStatus.FEASIBLE

        # Rough cost estimate
        cost = None
        if product == ProductType.GBLOCK:
            cost = max(89.0, seq_len * 0.10)  # ~$0.10/bp, min $89
        elif product == ProductType.EBLOCK:
            cost = max(169.0, seq_len * 0.06)  # ~$0.06/bp, min $169
        elif product == ProductType.OLIGO:
            cost = max(10.0, seq_len * 0.20)  # ~$0.20/base

        return FeasibilityResult(
            provider=self.name,
            product_type=product,
            status=status,
            violations=violations,
            sequence_length=seq_len,
            gc_content=round(gc, 4),
            estimated_cost_usd=round(cost, 2) if cost else None,
        )


class TwistProvider(SynthesisProvider):
    """Twist Bioscience synthesis feasibility checker.

    Stub implementation with basic constraints:
    - Genes: up to 5000bp
    - GC: 25-65%
    - No extreme homopolymers
    """

    @property
    def name(self) -> str:
        return "Twist"

    def check_feasibility(self, sequence: str) -> FeasibilityResult:
        """Check sequence against Twist Bioscience constraints."""
        seq = sequence.upper().replace(" ", "").replace("\n", "")
        violations: list[ConstraintViolation] = []
        seq_len = len(seq)
        gc = gc_content(seq)

        product = ProductType.GENE if seq_len > 300 else ProductType.FRAGMENT

        # Length
        if seq_len > 5000:
            violations.append(
                ConstraintViolation(
                    constraint="length",
                    message=f"Twist maximum length is 5000bp, got {seq_len}bp",
                    severity="error",
                )
            )
        if seq_len < 300 and product == ProductType.GENE:
            violations.append(
                ConstraintViolation(
                    constraint="length",
                    message=f"Twist gene minimum length is 300bp, got {seq_len}bp",
                    severity="error",
                )
            )

        # GC
        if gc < 0.25 or gc > 0.65:
            violations.append(
                ConstraintViolation(
                    constraint="gc_content",
                    message=f"GC content {gc:.1%} outside Twist range (25-65%)",
                    severity="error",
                )
            )

        # Homopolymer
        max_homo = longest_homopolymer(seq)
        if max_homo > 15:
            violations.append(
                ConstraintViolation(
                    constraint="homopolymer",
                    message=f"Homopolymer run of {max_homo}bp may cause issues",
                    severity="warning",
                )
            )

        error_count = sum(1 for v in violations if v.severity == "error")
        status = (
            FeasibilityStatus.INFEASIBLE if error_count > 0
            else FeasibilityStatus.MARGINAL if violations
            else FeasibilityStatus.FEASIBLE
        )

        # Twist pricing: ~$0.07/bp for genes, ~$0.09/bp for fragments
        cost = seq_len * 0.07 if product == ProductType.GENE else seq_len * 0.09

        return FeasibilityResult(
            provider=self.name,
            product_type=product,
            status=status,
            violations=violations,
            sequence_length=seq_len,
            gc_content=round(gc, 4),
            estimated_cost_usd=round(cost, 2),
        )


class GenScriptProvider(SynthesisProvider):
    """GenScript synthesis feasibility checker.

    Stub implementation with basic constraints:
    - Gene synthesis: up to 12000bp
    - GC: 15-90% (more permissive than IDT/Twist)
    """

    @property
    def name(self) -> str:
        return "GenScript"

    def check_feasibility(self, sequence: str) -> FeasibilityResult:
        """Check sequence against GenScript constraints."""
        seq = sequence.upper().replace(" ", "").replace("\n", "")
        violations: list[ConstraintViolation] = []
        seq_len = len(seq)
        gc = gc_content(seq)

        product = ProductType.GENE

        # Length
        if seq_len > 12000:
            violations.append(
                ConstraintViolation(
                    constraint="length",
                    message=f"GenScript maximum length is 12000bp, got {seq_len}bp",
                    severity="error",
                )
            )

        # GC (GenScript is more permissive)
        if gc < 0.15 or gc > 0.90:
            violations.append(
                ConstraintViolation(
                    constraint="gc_content",
                    message=f"GC content {gc:.1%} outside GenScript range (15-90%)",
                    severity="error",
                )
            )
        elif gc < 0.25 or gc > 0.75:
            violations.append(
                ConstraintViolation(
                    constraint="gc_content",
                    message=(
                        f"GC content {gc:.1%} in marginal range — "
                        f"may require optimization"
                    ),
                    severity="warning",
                )
            )

        # Homopolymer
        max_homo = longest_homopolymer(seq)
        if max_homo > 20:
            violations.append(
                ConstraintViolation(
                    constraint="homopolymer",
                    message=f"Homopolymer run of {max_homo}bp may cause issues",
                    severity="warning",
                )
            )

        error_count = sum(1 for v in violations if v.severity == "error")
        status = (
            FeasibilityStatus.INFEASIBLE if error_count > 0
            else FeasibilityStatus.MARGINAL if violations
            else FeasibilityStatus.FEASIBLE
        )

        # GenScript pricing: ~$0.12/bp for standard, varies with complexity
        cost = seq_len * 0.12

        return FeasibilityResult(
            provider=self.name,
            product_type=product,
            status=status,
            violations=violations,
            sequence_length=seq_len,
            gc_content=round(gc, 4),
            estimated_cost_usd=round(cost, 2),
        )
