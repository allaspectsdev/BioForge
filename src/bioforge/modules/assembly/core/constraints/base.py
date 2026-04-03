from abc import ABC, abstractmethod

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import ConstraintResult, Partition


class BaseConstraint(ABC):
    """Abstract base for assembly constraints."""

    def __init__(self, config: AssemblyConfig):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        ...
