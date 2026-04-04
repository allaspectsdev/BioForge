"""Tests for the pipeline DAG graph and builder."""

import pytest

from bioforge.pipeline_engine.dsl import PipelineBuilder, StepConfig
from bioforge.pipeline_engine.graph import PipelineGraph
from bioforge.core.exceptions import PipelineError


class TestPipelineGraph:
    def test_topological_sort(self):
        """A linear 3-step pipeline (A -> B -> C) returns correct order."""
        steps = [
            StepConfig(step_type="t1", name="A"),
            StepConfig(step_type="t2", name="B", inputs={"in": "A.out"}),
            StepConfig(step_type="t3", name="C", inputs={"in": "B.out"}),
        ]
        graph = PipelineGraph(steps)
        order = graph.topological_order()

        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_parallel_groups(self):
        """Independent steps should be grouped together."""
        steps = [
            StepConfig(step_type="t1", name="A"),
            StepConfig(step_type="t2", name="B"),
            StepConfig(step_type="t3", name="C", inputs={"in1": "A.out", "in2": "B.out"}),
        ]
        graph = PipelineGraph(steps)
        groups = graph.parallel_groups()

        # A and B are independent and should be in the first group
        assert len(groups) == 2
        assert set(groups[0]) == {"A", "B"}
        assert groups[1] == ["C"]

    def test_cycle_detection(self):
        """A cycle (A -> B -> A) should raise PipelineError."""
        steps = [
            StepConfig(step_type="t1", name="A", inputs={"in": "B.out"}),
            StepConfig(step_type="t2", name="B", inputs={"in": "A.out"}),
        ]
        graph = PipelineGraph(steps)

        with pytest.raises(PipelineError):
            graph.validate()

    def test_reserved_input_step(self):
        """A reference to '_input' should not raise an error."""
        steps = [
            StepConfig(step_type="t1", name="A", inputs={"in": "_input.sequence"}),
        ]
        graph = PipelineGraph(steps)

        # Should not raise
        graph.validate()

    def test_missing_dependency(self):
        """A reference to a nonexistent step should raise PipelineError."""
        steps = [
            StepConfig(step_type="t1", name="A", inputs={"in": "nonexistent.out"}),
        ]
        graph = PipelineGraph(steps)

        with pytest.raises(PipelineError):
            graph.validate()

    def test_duplicate_names_collapse_in_dict(self):
        """Two steps with the same name collapse in the dict-keyed graph.

        The PipelineGraph stores steps as a dict keyed by name, so duplicate
        names silently overwrite. This test documents that behavior: the graph
        ends up with only one step when two share a name.
        """
        steps = [
            StepConfig(step_type="t1", name="A"),
            StepConfig(step_type="t2", name="A"),
        ]
        graph = PipelineGraph(steps)

        # Dict keyed by name collapses to 1 entry
        assert len(graph.steps) == 1


class TestPipelineBuilder:
    def test_build_simple(self):
        builder = PipelineBuilder("simple_pipeline")
        builder.add_step("assembly.design", "design")
        pipeline = builder.build()

        assert pipeline.name == "simple_pipeline"
        assert len(pipeline.steps) == 1

    def test_connect_steps(self):
        builder = PipelineBuilder("connected")
        builder.add_step("t1", "step_a")
        builder.add_step("t2", "step_b")
        builder.connect("step_a", "output", "step_b", "input")
        pipeline = builder.build()

        # step_b should have step_a.output as its input reference
        step_b = next(s for s in pipeline.steps if s.name == "step_b")
        assert step_b.inputs["input"] == "step_a.output"

    def test_connect_to_input(self):
        builder = PipelineBuilder("from_input")
        builder.add_step("t1", "step_a")
        builder.connect("_input", "sequence", "step_a", "seq")
        pipeline = builder.build()

        step_a = next(s for s in pipeline.steps if s.name == "step_a")
        assert step_a.inputs["seq"] == "_input.sequence"
