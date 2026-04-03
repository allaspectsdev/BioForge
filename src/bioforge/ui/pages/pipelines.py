"""Pipeline Builder page."""

import streamlit as st


def show():
    st.title("Pipeline Builder")
    st.markdown("Build bioinformatics pipelines with a visual DAG editor.")

    st.info(
        "The pipeline builder provides a graphical interface for constructing "
        "bioinformatics workflows. Connect steps, configure parameters, and "
        "execute pipelines with a single click."
    )

    st.subheader("Available Step Types")
    steps = [
        {"Type": "assembly.design", "Description": "Design Gibson Assembly partition", "Module": "Assembly"},
    ]
    st.dataframe(steps, use_container_width=True, hide_index=True)

    st.subheader("Example Pipeline")
    st.code(
        """
from bioforge.pipeline_engine.dsl import PipelineBuilder

pipeline = (
    PipelineBuilder("gibson_assembly", "Design Gibson Assembly")
    .add_step("assembly.design", "design",
              params={"min_fragment_bp": 2000, "max_fragment_bp": 2500})
    .build()
)
""",
        language="python",
    )

    st.markdown(
        "Use the **AI Agent** page to describe your pipeline in natural language "
        "and have it constructed automatically."
    )
