from bioforge.modules.assembly.core.constraints.base import BaseConstraint
from bioforge.modules.assembly.core.models import (
    ConstraintResult,
    ConstraintSeverity,
    ConstraintViolation,
    Partition,
)
from bioforge.modules.assembly.core.thermo import ThermoEngine


class HairpinConstraint(BaseConstraint):
    """C4: Overhangs should not form strong secondary structures."""

    def __init__(self, config, thermo: ThermoEngine):
        super().__init__(config)
        self.thermo = thermo

    @property
    def name(self) -> str:
        return "hairpin"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        violations = []
        oh_seqs = partition.get_overhang_sequences(sequence)
        threshold = self.config.max_hairpin_dg_kcal

        for i, oh_seq in enumerate(oh_seqs):
            dg = self.thermo.calc_hairpin_dg(oh_seq)
            if dg < threshold:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=f"Overhang {i}: hairpin ΔG {dg:.1f} kcal/mol < {threshold}",
                        indices=[i],
                    )
                )

        if violations:
            total = len(oh_seqs) if oh_seqs else 1
            score = max(0.0, 1.0 - len(violations) / total)
            return ConstraintResult(passed=False, violations=violations, score=score)
        return ConstraintResult.ok()
