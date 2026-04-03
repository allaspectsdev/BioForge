"""DNA synthesis integration module.

Provides synthesis feasibility checking against real provider constraints
(IDT, Twist Bioscience, GenScript) and IDT plate-format order generation
for primer and fragment ordering.
"""

from bioforge.modules.assembly.core.synthesis.feasibility import (
    BatchFeasibilityResult,
    FragmentFeasibility,
    SynthesisFeasibilityChecker,
)
from bioforge.modules.assembly.core.synthesis.primer_ordering import (
    PlateLayout,
    PrimerOrderGenerator,
    PrimerOrderResult,
    PrimerSpec,
)
from bioforge.modules.assembly.core.synthesis.providers import (
    FeasibilityResult,
    FeasibilityStatus,
    GenScriptProvider,
    IDTProvider,
    ProductType,
    SynthesisProvider,
    TwistProvider,
)

__all__ = [
    "BatchFeasibilityResult",
    "FeasibilityResult",
    "FeasibilityStatus",
    "FragmentFeasibility",
    "GenScriptProvider",
    "IDTProvider",
    "PlateLayout",
    "PrimerOrderGenerator",
    "PrimerOrderResult",
    "PrimerSpec",
    "ProductType",
    "SynthesisFeasibilityChecker",
    "SynthesisProvider",
    "TwistProvider",
]
