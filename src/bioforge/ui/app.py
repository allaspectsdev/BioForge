"""BioForge Streamlit Dashboard."""

import streamlit as st

st.set_page_config(
    page_title="BioForge",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.sidebar.title("BioForge")
    st.sidebar.markdown("AI-first bioinformatics platform")
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["Home", "Assembly Designer", "Sequence Viewer", "Pipeline Builder", "AI Agent"],
    )

    if page == "Home":
        show_home()
    elif page == "Assembly Designer":
        from bioforge.ui.pages import assembly
        assembly.show()
    elif page == "Sequence Viewer":
        from bioforge.ui.pages import sequences
        sequences.show()
    elif page == "Pipeline Builder":
        from bioforge.ui.pages import pipelines
        pipelines.show()
    elif page == "AI Agent":
        from bioforge.ui.pages import agent
        agent.show()


def show_home():
    st.title("BioForge")
    st.markdown(
        """
        ### AI-First Bioinformatics Platform

        **BioForge** unifies bioinformatics tool orchestration, AI-assisted design,
        and pipeline execution in a single platform.

        #### Quick Start
        - **Assembly Designer** — Design Gibson Assembly fragments with constraint optimization
        - **Sequence Viewer** — Import and explore DNA/RNA/protein sequences
        - **Pipeline Builder** — Create and execute bioinformatics pipelines
        - **AI Agent** — Chat with an AI assistant about your bioinformatics problems

        #### Architecture
        - Modular plugin system for bioinformatics tools
        - Claude AI agent with MCP tool integration
        - Constraint-based optimization (Tm, GC, orthogonality)
        - Pipeline DAG execution with Nextflow export
        """
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Modules Loaded", "1")
        st.caption("Assembly")
    with col2:
        st.metric("Constraint Types", "4")
        st.caption("Length, Quality, Hairpin, Orthogonality")
    with col3:
        st.metric("MCP Tools", "4")
        st.caption("design, calculate_tm, check, reverse_complement")


main()
