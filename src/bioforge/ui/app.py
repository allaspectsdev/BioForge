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
        - **Assembly Designer** — Design Gibson & Golden Gate assemblies with constraint optimization
        - **Sequence Viewer** — Import and explore DNA/RNA/protein sequences
        - **Pipeline Builder** — Create and execute bioinformatics pipelines
        - **AI Agent** — Multi-turn AI assistant with tool use across all modules

        #### Architecture
        - 7 modular plugins implementing the BioForgeModule interface
        - Claude AI agent with domain routing, memory, and streaming
        - Evo 2 genomic foundation model (1B/7B/20B/40B) for embeddings and variant scoring
        - Boltz-2 / OpenFold3 protein structure prediction
        - Constraint-based assembly optimization (simulated annealing)
        - Pipeline DAG execution with Nextflow export
        - 22 MCP tools for integration with any AI client
        """
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Modules", "7")
        st.caption("Assembly, Evo 2, Structure, Alignment, Variants, Experiments, SBOL")
    with col2:
        st.metric("Capabilities", "22")
        st.caption("Gibson, Golden Gate, codon opt, BLAST, variant scoring, ...")
    with col3:
        st.metric("MCP Tools", "22")
        st.caption("Assembly, alignment, variants, structure, SBOL, experiments")
    with col4:
        st.metric("Pipeline Steps", "10")
        st.caption("Assembly, alignment, Evo 2, structure, variants, SBOL export")

    st.divider()

    st.subheader("Foundation Models")
    fm_col1, fm_col2 = st.columns(2)
    with fm_col1:
        st.markdown(
            """
            **Evo 2** (Arc Institute)
            - Genomic foundation model published in *Nature* (March 2026)
            - 1B / 7B / 20B / 40B parameter variants
            - 1M base-pair context window
            - DNA/RNA/protein embeddings, variant scoring, sequence generation
            - 90% accuracy on BRCA1 pathogenicity prediction
            """
        )
    with fm_col2:
        st.markdown(
            """
            **Boltz-2** (MIT License)
            - AlphaFold3-level protein structure prediction
            - Protein-ligand binding affinity (1000x faster than FEP)
            - Multi-chain complex prediction
            - Open source, commercially usable
            """
        )


main()
