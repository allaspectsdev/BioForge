"""Thermodynamic calculations: Tm, hairpin ΔG, heterodimer ΔG.

Primary backend: primer3-py (C library, accurate to ±2°C).
Fallback: Pure-Python SantaLucia 1998 nearest-neighbor model.
"""

import math
from functools import lru_cache

# SantaLucia 1998 unified nearest-neighbor parameters
# (ΔH in cal/mol, ΔS in cal/mol/K)
NN_PARAMS: dict[str, tuple[float, float]] = {
    "AA": (-7900, -22.2),
    "TT": (-7900, -22.2),
    "AT": (-7200, -20.4),
    "TA": (-7200, -21.3),
    "CA": (-8500, -22.7),
    "TG": (-8500, -22.7),
    "GT": (-8400, -22.4),
    "AC": (-8400, -22.4),
    "CT": (-7800, -21.0),
    "AG": (-7800, -21.0),
    "GA": (-8200, -22.2),
    "TC": (-8200, -22.2),
    "CG": (-10600, -27.2),
    "GC": (-9800, -24.4),
    "GG": (-8000, -19.9),
    "CC": (-8000, -19.9),
}

# Initiation parameters (SantaLucia 1998, Table 2)
# Each duplex has two ends; each end contributes an initiation term
# based on whether that terminal base pair is GC or AT.
INIT_GC = (100, -2.8)     # ΔH cal/mol, ΔS cal/mol/K for terminal GC pair
INIT_AT = (2300, 4.1)     # ΔH cal/mol, ΔS cal/mol/K for terminal AT pair

R = 1.987  # Gas constant in cal/(mol·K)


try:
    import primer3

    _HAS_PRIMER3 = True
except ImportError:
    _HAS_PRIMER3 = False


class ThermoEngine:
    """Thermodynamic calculation engine with primer3 and pure-Python fallback."""

    def __init__(
        self,
        na_conc: float = 50.0,
        mg_conc: float = 1.5,
        oligo_conc: float = 250.0,
    ):
        self.na_conc = na_conc
        self.mg_conc = mg_conc
        self.oligo_conc = oligo_conc
        self._cache: dict[str, float] = {}

        if _HAS_PRIMER3:
            self._thermo = primer3.thermoanalysis.ThermoAnalysis(
                mv_conc=na_conc,
                dv_conc=mg_conc,
                dntp_conc=0.25,
                dna_conc=oligo_conc,
            )
        else:
            self._thermo = None

    def calc_tm(self, seq: str) -> float:
        """Calculate melting temperature in °C."""
        key = f"tm:{seq}"
        if key in self._cache:
            return self._cache[key]

        if self._thermo is not None:
            tm = self._thermo.calc_tm(seq)
        else:
            tm = self._nn_tm(seq)

        self._cache[key] = tm
        return tm

    def calc_hairpin_dg(self, seq: str) -> float:
        """Calculate hairpin ΔG in kcal/mol. More negative = stronger (worse)."""
        key = f"hp:{seq}"
        if key in self._cache:
            return self._cache[key]

        if self._thermo is not None:
            result = self._thermo.calc_hairpin(seq)
            dg = result.dg / 1000.0  # cal → kcal
        else:
            dg = 0.0  # Fallback: assume no hairpin

        self._cache[key] = dg
        return dg

    def calc_homodimer_dg(self, seq: str) -> float:
        """Calculate homodimer ΔG in kcal/mol."""
        key = f"hd:{seq}"
        if key in self._cache:
            return self._cache[key]

        if self._thermo is not None:
            result = self._thermo.calc_homodimer(seq)
            dg = result.dg / 1000.0
        else:
            dg = 0.0

        self._cache[key] = dg
        return dg

    def calc_heterodimer_dg(self, seq1: str, seq2: str) -> float:
        """Calculate heterodimer ΔG in kcal/mol between two sequences."""
        key = f"het:{seq1}:{seq2}"
        if key in self._cache:
            return self._cache[key]

        if self._thermo is not None:
            result = self._thermo.calc_heterodimer(seq1, seq2)
            dg = result.dg / 1000.0
        else:
            dg = 0.0

        self._cache[key] = dg
        return dg

    def clear_cache(self) -> None:
        self._cache.clear()

    @staticmethod
    def _nn_tm(seq: str) -> float:
        """Pure-Python nearest-neighbor Tm calculation (SantaLucia 1998)."""
        seq = seq.upper()
        if len(seq) < 2:
            return 0.0

        dh_total = 0.0
        ds_total = 0.0

        # Sum NN parameters
        for i in range(len(seq) - 1):
            dinuc = seq[i : i + 2]
            if dinuc in NN_PARAMS:
                dh, ds = NN_PARAMS[dinuc]
                dh_total += dh
                ds_total += ds

        # Initiation: one term per terminal base pair
        for terminal in (seq[0], seq[-1]):
            if terminal in ("G", "C"):
                dh_total += INIT_GC[0]
                ds_total += INIT_GC[1]
            else:
                dh_total += INIT_AT[0]
                ds_total += INIT_AT[1]

        # Salt correction (Owczarzy 2004 simplified):
        # Tm_salt = Tm_1M + (4.29 * fGC - 3.95) * 1e-5 * ln([Na+]) + 9.40e-6 * (ln[Na+])^2
        # For the NN method, we apply the SantaLucia 1998 entropy correction:
        # ΔS_salt = 0.368 * (n-1) * ln([Na+])   (units: cal/mol/K, [Na+] in M)
        na_eq = 50.0  # Default Na+ equivalent in mM
        ds_total += 0.368 * (len(seq) - 1) * math.log(na_eq / 1000.0)

        # Tm = ΔH / (ΔS + R·ln(Ct/4)) - 273.15
        ct = 250e-9  # 250 nM oligo
        if ds_total + R * math.log(ct / 4.0) == 0:
            return 0.0

        tm = dh_total / (ds_total + R * math.log(ct / 4.0)) - 273.15
        return tm
