"""Primer order generation for IDT plate format."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# Nearest-neighbor thermodynamic parameters for Tm calculation (SantaLucia 1998)
# dH in cal/mol, dS in cal/(mol*K)
_NN_PARAMS: dict[str, tuple[float, float]] = {
    "AA": (-7900, -22.2), "AT": (-7200, -20.4), "AG": (-7800, -21.0), "AC": (-8400, -22.4),
    "TA": (-7200, -21.3), "TT": (-7900, -22.2), "TG": (-8500, -22.7), "TC": (-8200, -22.2),
    "GA": (-8200, -22.2), "GT": (-8400, -22.4), "GG": (-8000, -19.9), "GC": (-9800, -24.4),
    "CA": (-8500, -22.7), "CT": (-7800, -21.0), "CG": (-10600, -27.2), "CC": (-8000, -19.9),
}


def calculate_tm(sequence: str, na_mm: float = 50.0, oligo_nm: float = 250.0) -> float:
    """Calculate melting temperature using the nearest-neighbor method.

    Args:
        sequence: DNA sequence (5' to 3').
        na_mm: Monovalent cation concentration in mM.
        oligo_nm: Oligo concentration in nM.

    Returns:
        Predicted Tm in degrees Celsius.
    """
    seq = sequence.upper()
    if len(seq) < 2:
        return 0.0

    dh_total = 0.0  # cal/mol
    ds_total = 0.0  # cal/(mol*K)

    # Initiation parameters
    # 5' end initiation
    if seq[0] in ("A", "T"):
        dh_total += 2300
        ds_total += 4.1
    else:
        dh_total += 100
        ds_total += -2.8

    # 3' end initiation
    if seq[-1] in ("A", "T"):
        dh_total += 2300
        ds_total += 4.1
    else:
        dh_total += 100
        ds_total += -2.8

    # Sum nearest-neighbor contributions
    for i in range(len(seq) - 1):
        dinuc = seq[i : i + 2]
        if dinuc in _NN_PARAMS:
            dh, ds = _NN_PARAMS[dinuc]
            dh_total += dh
            ds_total += ds

    # Gas constant
    R = 1.987  # cal/(mol*K)

    # Salt correction (SantaLucia 1998)
    ds_total += 0.368 * (len(seq) - 1) * math.log(na_mm / 1000.0)

    # Tm calculation (self-complementary vs non-self-complementary)
    # Assume non-self-complementary
    ct = oligo_nm * 1e-9  # Convert to M
    tm_k = dh_total / (ds_total + R * math.log(ct / 4.0))
    tm_c = tm_k - 273.15

    return round(tm_c, 1)


@dataclass
class PrimerEntry:
    """A single primer for ordering."""

    well_position: str
    name: str
    sequence: str
    tm: float
    length: int


@dataclass
class PrimerOrder:
    """Complete primer order for a 96-well plate."""

    primers: list[PrimerEntry] = field(default_factory=list)
    plate_name: str = "BioForge_Primers"

    def to_csv(self) -> str:
        """Generate IDT-format plate CSV."""
        lines = ["Well Position,Name,Sequence"]
        for p in self.primers:
            lines.append(f"{p.well_position},{p.name},{p.sequence}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "plate_name": self.plate_name,
            "num_primers": len(self.primers),
            "csv": self.to_csv(),
            "primers": [
                {
                    "well": p.well_position,
                    "name": p.name,
                    "sequence": p.sequence,
                    "tm": p.tm,
                    "length": p.length,
                }
                for p in self.primers
            ],
        }


class PrimerOrderGenerator:
    """Generates IDT-format primer orders from assembly results.

    Takes an assembly result with fragments and overhangs and produces
    a 96-well plate CSV suitable for IDT oligo ordering.

    Wells are assigned in row-major order (A01, A02, ..., A12, B01, ..., H12).
    Each fragment gets a forward and reverse primer.
    """

    ROWS = "ABCDEFGH"
    COLS = 12
    MAX_WELLS = 96

    def _well_position(self, index: int) -> str:
        """Convert a 0-based index to a well position (A01-H12)."""
        row = self.ROWS[index // self.COLS]
        col = (index % self.COLS) + 1
        return f"{row}{col:02d}"

    def generate(
        self,
        assembly_result: dict,
        plate_name: str = "BioForge_Primers",
        primer_prefix: str = "BF",
    ) -> PrimerOrder:
        """Generate a primer order from an assembly result.

        The assembly_result is expected to have:
        - 'fragments': list of dicts with 'index', 'start', 'end'
        - 'overhangs': list of dicts with 'index', 'sequence'

        For each fragment, generates a forward primer (from the upstream
        overhang) and a reverse primer (reverse complement of the
        downstream overhang).
        """
        fragments = assembly_result.get("fragments", [])
        overhangs = assembly_result.get("overhangs", [])
        sequence = assembly_result.get("sequence", "")

        order = PrimerOrder(plate_name=plate_name)
        well_idx = 0

        for frag in fragments:
            if well_idx >= self.MAX_WELLS:
                break

            frag_idx = frag.get("index", 0)

            # Forward primer: upstream overhang sequence
            fwd_seq = ""
            if frag_idx < len(overhangs):
                fwd_seq = overhangs[frag_idx].get("sequence", "")
            elif sequence and "start" in frag:
                # Fall back to sequence region
                start = max(0, frag["start"])
                fwd_seq = sequence[start : start + 25]

            if fwd_seq:
                fwd_entry = PrimerEntry(
                    well_position=self._well_position(well_idx),
                    name=f"{primer_prefix}_{frag_idx:03d}_F",
                    sequence=fwd_seq.upper(),
                    tm=calculate_tm(fwd_seq),
                    length=len(fwd_seq),
                )
                order.primers.append(fwd_entry)
                well_idx += 1

            if well_idx >= self.MAX_WELLS:
                break

            # Reverse primer: downstream overhang (reverse complement)
            rev_seq = ""
            downstream_idx = frag_idx + 1
            if downstream_idx < len(overhangs):
                oh_seq = overhangs[downstream_idx].get("sequence", "")
                rev_seq = self._reverse_complement(oh_seq)
            elif sequence and "end" in frag:
                end = min(len(sequence), frag["end"])
                region = sequence[max(0, end - 25) : end]
                rev_seq = self._reverse_complement(region)

            if rev_seq:
                rev_entry = PrimerEntry(
                    well_position=self._well_position(well_idx),
                    name=f"{primer_prefix}_{frag_idx:03d}_R",
                    sequence=rev_seq.upper(),
                    tm=calculate_tm(rev_seq),
                    length=len(rev_seq),
                )
                order.primers.append(rev_entry)
                well_idx += 1

        return order

    @staticmethod
    def _reverse_complement(seq: str) -> str:
        """Compute reverse complement of a DNA sequence."""
        comp = {"A": "T", "T": "A", "G": "C", "C": "G",
                "a": "t", "t": "a", "g": "c", "c": "g"}
        return "".join(comp.get(b, "N") for b in reversed(seq.upper()))
