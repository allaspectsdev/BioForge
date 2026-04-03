from bioforge.modules.assembly.core.constraints.base import BaseConstraint
from bioforge.modules.assembly.core.models import (
    ConstraintResult,
    ConstraintSeverity,
    ConstraintViolation,
    Partition,
    gc_content,
    longest_homopolymer,
)
from bioforge.modules.assembly.core.thermo import ThermoEngine


class OverhangQualityConstraint(BaseConstraint):
    """C2: Overhang Tm, GC content, homopolymer runs, and length."""

    def __init__(self, config, thermo: ThermoEngine):
        super().__init__(config)
        self.thermo = thermo

    @property
    def name(self) -> str:
        return "overhang_quality"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        violations = []
        oh_seqs = partition.get_overhang_sequences(sequence)

        for i, oh_seq in enumerate(oh_seqs):
            oh_len = len(oh_seq)

            # Length check
            if oh_len < self.config.min_overhang_bp or oh_len > self.config.max_overhang_bp:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=f"Overhang {i}: length {oh_len} outside [{self.config.min_overhang_bp}, {self.config.max_overhang_bp}]",
                        indices=[i],
                    )
                )

            # Tm check
            tm = self.thermo.calc_tm(oh_seq)
            if tm < self.config.min_tm or tm > self.config.max_tm:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=f"Overhang {i}: Tm {tm:.1f}°C outside [{self.config.min_tm}, {self.config.max_tm}]",
                        indices=[i],
                    )
                )

            # GC content check
            gc = gc_content(oh_seq)
            if gc < self.config.min_gc or gc > self.config.max_gc:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.WARNING,
                        message=f"Overhang {i}: GC {gc:.1%} outside [{self.config.min_gc:.0%}, {self.config.max_gc:.0%}]",
                        indices=[i],
                    )
                )

            # Homopolymer check
            hp = longest_homopolymer(oh_seq)
            if hp > self.config.max_homopolymer_run:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=f"Overhang {i}: homopolymer run {hp} > {self.config.max_homopolymer_run}",
                        indices=[i],
                    )
                )

        if violations:
            fail_count = sum(1 for v in violations if v.severity == ConstraintSeverity.FAIL)
            total = len(oh_seqs) if oh_seqs else 1
            score = max(0.0, 1.0 - fail_count / total)
            return ConstraintResult(
                passed=(fail_count == 0), violations=violations, score=score
            )
        return ConstraintResult.ok()
