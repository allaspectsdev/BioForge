class BioForgeError(Exception):
    """Base exception for all BioForge errors."""


class NotFoundError(BioForgeError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource: str, id: str):
        self.resource = resource
        self.id = id
        super().__init__(f"{resource} not found: {id}")


class ValidationError(BioForgeError):
    """Raised when input validation fails."""


class StorageError(BioForgeError):
    """Raised when object storage operations fail."""


class PipelineError(BioForgeError):
    """Raised when pipeline validation or execution fails."""


class AssemblyError(BioForgeError):
    """Raised when DNA assembly design fails."""


class NoFeasiblePartitionError(AssemblyError):
    """Raised when no valid partition can be found for a sequence."""

    def __init__(self, message: str, best_effort: object = None):
        self.best_effort = best_effort
        super().__init__(message)


class AgentError(BioForgeError):
    """Raised when AI agent operations fail."""
