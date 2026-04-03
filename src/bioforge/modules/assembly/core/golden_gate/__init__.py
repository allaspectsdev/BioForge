"""Golden Gate Assembly module for Type IIS restriction enzyme cloning.

Provides overhang design, fidelity scoring, constraint validation, and
sequence domestication for Golden Gate assembly workflows.
"""

from bioforge.modules.assembly.core.golden_gate.domestication import (
    DomesticationEngine,
    DomesticationResult,
    Mutation,
)
from bioforge.modules.assembly.core.golden_gate.enzymes import (
    ENZYMES,
    TypeIISEnzyme,
    bsai_fidelity,
    is_palindromic,
    overhang_fidelity_matrix,
)
from bioforge.modules.assembly.core.golden_gate.gg_constraints import (
    EnzymeCompatibilityConstraint,
    LigationFidelityConstraint,
    OverhangSetConstraint,
)
from bioforge.modules.assembly.core.golden_gate.gg_solver import (
    GoldenGatePart,
    GoldenGateResult,
    GoldenGateSolver,
)

__all__ = [
    "DomesticationEngine",
    "DomesticationResult",
    "ENZYMES",
    "EnzymeCompatibilityConstraint",
    "GoldenGatePart",
    "GoldenGateResult",
    "GoldenGateSolver",
    "LigationFidelityConstraint",
    "Mutation",
    "OverhangSetConstraint",
    "TypeIISEnzyme",
    "bsai_fidelity",
    "is_palindromic",
    "overhang_fidelity_matrix",
]
