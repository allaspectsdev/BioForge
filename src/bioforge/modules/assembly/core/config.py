from dataclasses import dataclass


@dataclass(frozen=True)
class AssemblyConfig:
    """Centralized thresholds for DNA fragment assembly design."""

    # C1: Fragment length constraints (bp)
    min_fragment_bp: int = 2000
    max_fragment_bp: int = 2500

    # C2: Overhang length (bp)
    min_overhang_bp: int = 20
    max_overhang_bp: int = 30
    default_overhang_bp: int = 25

    # C2: Melting temperature (°C)
    min_tm: float = 50.0
    max_tm: float = 65.0

    # C2: GC content (fraction)
    min_gc: float = 0.40
    max_gc: float = 0.60

    # C2: Homopolymer
    max_homopolymer_run: int = 4

    # C3: Orthogonality
    min_hamming_distance: int = 5
    min_ddg_kcal: float = 4.0

    # C4: Hairpin
    max_hairpin_dg_kcal: float = -2.0  # More negative = stronger hairpin = bad

    # Solver parameters
    max_restarts: int = 50
    max_iterations_per_restart: int = 500
    sa_initial_temp: float = 10.0
    sa_cooling_rate: float = 0.98
    boundary_deltas: tuple[int, ...] = (-50, -25, -10, -5, 5, 10, 25, 50)
    overhang_deltas: tuple[int, ...] = (-2, -1, 1, 2)

    # Scorer weights
    weight_orthogonality: float = 0.40
    weight_tm_uniformity: float = 0.20
    weight_gc_balance: float = 0.20
    weight_structure_avoidance: float = 0.20

    # Thermodynamic conditions
    na_conc_mm: float = 50.0   # Sodium concentration (mM)
    mg_conc_mm: float = 1.5    # Magnesium concentration (mM)
    oligo_conc_nm: float = 250.0  # Oligo concentration (nM)
