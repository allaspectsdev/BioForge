"""IDT plate-format CSV generation for primer and fragment ordering.

Generates 96-well plate layout files compatible with IDT's bulk ordering
system. Maps primers/fragments to wells (A01-H12), calculates melting
temperatures, and checks for self-complementarity issues.

Output CSV format (IDT plate upload):
    Well Position, Name, Sequence, Scale, Purification
    A01, primer_fwd_1, ATGCGATCG..., 25nm, STD
"""

import csv
import io
import logging
import math
from dataclasses import dataclass, field

from bioforge.modules.assembly.core.models import gc_content, reverse_complement
from bioforge.modules.assembly.core.thermo import ThermoEngine

logger = logging.getLogger(__name__)

# 96-well plate layout
ROWS = "ABCDEFGH"
COLS = range(1, 13)
PLATE_WELLS = [f"{row}{col:02d}" for row in ROWS for col in COLS]
MAX_WELLS_PER_PLATE = 96


@dataclass(frozen=True, slots=True)
class PrimerSpec:
    """Specification for a single primer or oligonucleotide.

    Attributes:
        name: Primer name (e.g., "fwd_promoter_1").
        sequence: DNA sequence (5' to 3').
        tm: Calculated melting temperature (C).
        gc: GC content (fraction 0.0-1.0).
        length: Sequence length in bases.
        self_complementarity: Whether self-complementarity was detected.
        scale: Synthesis scale (default "25nm").
        purification: Purification method (default "STD").
    """

    name: str
    sequence: str
    tm: float
    gc: float
    length: int
    self_complementarity: bool = False
    scale: str = "25nm"
    purification: str = "STD"


@dataclass
class PlateLayout:
    """A 96-well plate layout for primer ordering.

    Attributes:
        plate_id: Identifier for this plate.
        wells: Mapping of well position to PrimerSpec.
        primers: List of all primers in plate order.
    """

    plate_id: str = "plate_1"
    wells: dict[str, PrimerSpec] = field(default_factory=dict)
    primers: list[PrimerSpec] = field(default_factory=list)

    @property
    def num_primers(self) -> int:
        return len(self.wells)

    @property
    def is_full(self) -> bool:
        return len(self.wells) >= MAX_WELLS_PER_PLATE


@dataclass
class PrimerOrderResult:
    """Result of primer order generation.

    Attributes:
        plates: List of plate layouts.
        total_primers: Total number of primers across all plates.
        csv_content: The IDT-format CSV as a string.
        warnings: Any warnings generated during layout.
    """

    plates: list[PlateLayout] = field(default_factory=list)
    total_primers: int = 0
    csv_content: str = ""
    warnings: list[str] = field(default_factory=list)


def _check_self_complementarity(
    sequence: str,
    thermo: ThermoEngine | None = None,
    dg_threshold: float = -5.0,
) -> bool:
    """Check if a primer has problematic self-complementarity.

    Uses homodimer ΔG calculation if ThermoEngine is available, otherwise
    falls back to a simple palindrome check.

    Args:
        sequence: Primer sequence.
        thermo: ThermoEngine for ΔG calculation.
        dg_threshold: Maximum ΔG (kcal/mol) for self-complementarity.
            More negative = stronger (worse).

    Returns:
        True if self-complementarity is detected.
    """
    if thermo is not None:
        try:
            dg = thermo.calc_homodimer_dg(sequence)
            return dg < dg_threshold
        except Exception:
            pass

    # Fallback: check if any 6+ base stretch is a palindrome
    seq = sequence.upper()
    rc = reverse_complement(seq)
    for window_len in range(6, len(seq) // 2 + 1):
        for i in range(len(seq) - window_len + 1):
            subseq = seq[i:i + window_len]
            if subseq in rc:
                return True
    return False


class PrimerOrderGenerator:
    """Generates IDT plate-format CSV files for primer ordering.

    Maps primers/fragments to 96-well plate wells in column-major order
    (A01, B01, ..., H01, A02, ..., H12), calculates Tm for each primer,
    and checks for self-complementarity issues.

    Args:
        scale: Default synthesis scale (default "25nm").
        purification: Default purification method (default "STD").
        thermo: ThermoEngine for Tm calculation. If None, creates a
            default instance.
    """

    def __init__(
        self,
        scale: str = "25nm",
        purification: str = "STD",
        thermo: ThermoEngine | None = None,
    ):
        self.scale = scale
        self.purification = purification
        self.thermo = thermo or ThermoEngine()

    def generate_order(
        self,
        primers: list[tuple[str, str]],
        plate_id_prefix: str = "plate",
    ) -> PrimerOrderResult:
        """Generate an IDT plate-format order from a list of primers.

        Args:
            primers: List of (name, sequence) tuples.
            plate_id_prefix: Prefix for plate IDs.

        Returns:
            PrimerOrderResult with plate layouts and CSV content.
        """
        if not primers:
            return PrimerOrderResult()

        # Process each primer
        specs: list[PrimerSpec] = []
        warnings: list[str] = []

        for name, sequence in primers:
            seq = sequence.upper().replace(" ", "").replace("\n", "")

            if len(seq) == 0:
                warnings.append(f"Primer '{name}' has empty sequence, skipping")
                continue

            # Calculate Tm
            tm = self.thermo.calc_tm(seq)

            # Calculate GC
            gc = gc_content(seq)

            # Check self-complementarity
            self_comp = _check_self_complementarity(seq, self.thermo)
            if self_comp:
                warnings.append(
                    f"Primer '{name}' has self-complementarity "
                    f"(may form homodimers)"
                )

            # Tm warnings
            if tm < 50.0:
                warnings.append(
                    f"Primer '{name}' has low Tm ({tm:.1f}C), "
                    f"consider extending"
                )
            elif tm > 72.0:
                warnings.append(
                    f"Primer '{name}' has high Tm ({tm:.1f}C), "
                    f"consider shortening"
                )

            specs.append(
                PrimerSpec(
                    name=name,
                    sequence=seq,
                    tm=round(tm, 1),
                    gc=round(gc, 4),
                    length=len(seq),
                    self_complementarity=self_comp,
                    scale=self.scale,
                    purification=self.purification,
                )
            )

        # Map to plates (96 wells each)
        plates: list[PlateLayout] = []
        plate_num = 1

        for i in range(0, len(specs), MAX_WELLS_PER_PLATE):
            batch = specs[i:i + MAX_WELLS_PER_PLATE]
            plate = PlateLayout(
                plate_id=f"{plate_id_prefix}_{plate_num}",
            )

            for j, spec in enumerate(batch):
                well = PLATE_WELLS[j]
                plate.wells[well] = spec
                plate.primers.append(spec)

            plates.append(plate)
            plate_num += 1

        # Generate CSV
        csv_content = self._generate_csv(plates)

        return PrimerOrderResult(
            plates=plates,
            total_primers=len(specs),
            csv_content=csv_content,
            warnings=warnings,
        )

    def _generate_csv(self, plates: list[PlateLayout]) -> str:
        """Generate IDT plate-format CSV content.

        Format:
            Well Position,Name,Sequence,Scale,Purification
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["Well Position", "Name", "Sequence", "Scale", "Purification"])

        for plate in plates:
            for well, spec in plate.wells.items():
                writer.writerow([
                    well,
                    spec.name,
                    spec.sequence,
                    spec.scale,
                    spec.purification,
                ])

        return output.getvalue()

    def generate_from_assembly_fragments(
        self,
        fragments: list[dict],
        assembly_name: str = "assembly",
    ) -> PrimerOrderResult:
        """Generate primer orders from assembly fragment specifications.

        For each fragment, generates a forward and reverse primer based
        on the fragment boundaries. Primer length is chosen to achieve
        a target Tm of 60C (+/- 5C).

        Args:
            fragments: List of fragment dicts with keys:
                "sequence" (str), "index" (int), optionally "name" (str).
            assembly_name: Base name for primer naming.

        Returns:
            PrimerOrderResult with primers for all fragments.
        """
        primers: list[tuple[str, str]] = []
        target_tm = 60.0

        for frag in fragments:
            seq = frag.get("sequence", "")
            idx = frag.get("index", 0)
            name = frag.get("name", f"frag_{idx}")

            if len(seq) < 18:
                # Sequence too short for primer design — use as-is
                primers.append((f"{assembly_name}_{name}_fwd", seq))
                continue

            # Forward primer: extend from 5' end until target Tm
            fwd_primer = self._design_primer_to_tm(seq, target_tm)
            primers.append((f"{assembly_name}_{name}_fwd", fwd_primer))

            # Reverse primer: extend from 3' end (reverse complement)
            rc_seq = reverse_complement(seq)
            rev_primer = self._design_primer_to_tm(rc_seq, target_tm)
            primers.append((f"{assembly_name}_{name}_rev", rev_primer))

        return self.generate_order(primers, plate_id_prefix=assembly_name)

    def _design_primer_to_tm(
        self,
        template: str,
        target_tm: float,
        min_length: int = 18,
        max_length: int = 35,
    ) -> str:
        """Design a primer from a template to achieve a target Tm.

        Extends from the 5' end of the template, adding bases until
        the calculated Tm reaches the target.

        Args:
            template: Template sequence to design primer from.
            target_tm: Target melting temperature in C.
            min_length: Minimum primer length.
            max_length: Maximum primer length.

        Returns:
            Primer sequence.
        """
        template = template.upper()

        best_primer = template[:min_length]
        best_diff = abs(self.thermo.calc_tm(best_primer) - target_tm)

        for length in range(min_length, min(max_length + 1, len(template) + 1)):
            primer = template[:length]
            tm = self.thermo.calc_tm(primer)
            diff = abs(tm - target_tm)

            if diff < best_diff:
                best_diff = diff
                best_primer = primer

            if tm >= target_tm:
                break

        return best_primer
