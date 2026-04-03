"""DAG representation for pipelines."""

from collections import defaultdict

from bioforge.core.exceptions import PipelineError
from bioforge.pipeline_engine.dsl import StepConfig


class PipelineGraph:
    """DAG representation of a pipeline."""

    def __init__(self, steps: list[StepConfig]):
        self.steps = {s.name: s for s in steps}
        self.adjacency: dict[str, list[str]] = defaultdict(list)
        self._build_adjacency()

    def _build_adjacency(self) -> None:
        for step in self.steps.values():
            for port, ref in step.inputs.items():
                src_step = ref.split(".")[0]
                if src_step in self.steps:
                    self.adjacency[src_step].append(step.name)

    def validate(self) -> None:
        self._check_no_duplicate_names()
        self._check_dependencies_exist()
        self._check_no_cycles()

    def _check_no_duplicate_names(self) -> None:
        names = [s.name for s in self.steps.values()]
        if len(names) != len(set(names)):
            raise PipelineError("Duplicate step names in pipeline")

    # Reserved step names injected by the executor at runtime
    RESERVED_STEPS = {"_input"}

    def _check_dependencies_exist(self) -> None:
        for step in self.steps.values():
            for port, ref in step.inputs.items():
                src_step = ref.split(".")[0]
                if src_step not in self.steps and src_step not in self.RESERVED_STEPS:
                    raise PipelineError(
                        f"Step '{step.name}' references unknown step '{src_step}'"
                    )

    def _check_no_cycles(self) -> None:
        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(node: str) -> None:
            if node in in_stack:
                raise PipelineError(f"Cycle detected involving step '{node}'")
            if node in visited:
                return
            in_stack.add(node)
            for neighbor in self.adjacency.get(node, []):
                dfs(neighbor)
            in_stack.discard(node)
            visited.add(node)

        for name in self.steps:
            dfs(name)

    def topological_order(self) -> list[str]:
        """Return steps in execution order."""
        in_degree: dict[str, int] = {name: 0 for name in self.steps}
        for src, dsts in self.adjacency.items():
            for dst in dsts:
                in_degree[dst] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in self.adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.steps):
            raise PipelineError("Unable to determine execution order (cycle exists)")
        return order

    def parallel_groups(self) -> list[list[str]]:
        """Return groups of steps that can execute in parallel."""
        in_degree: dict[str, int] = {name: 0 for name in self.steps}
        for src, dsts in self.adjacency.items():
            for dst in dsts:
                in_degree[dst] += 1

        groups = []
        remaining = dict(in_degree)

        while remaining:
            group = [name for name, deg in remaining.items() if deg == 0]
            if not group:
                raise PipelineError("Unable to schedule steps (cycle exists)")
            groups.append(group)
            for node in group:
                del remaining[node]
                for neighbor in self.adjacency.get(node, []):
                    if neighbor in remaining:
                        remaining[neighbor] -= 1

        return groups
