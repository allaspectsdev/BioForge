"""Assembly Designer page."""

import streamlit as st

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.solver import AssemblySolver


def show():
    st.title("DNA Assembly Designer")
    st.markdown("Design Gibson Assembly fragments with constraint-based optimization.")

    col1, col2 = st.columns([2, 1])

    with col2:
        st.subheader("Constraints")
        min_frag = st.slider("Min fragment (bp)", 1000, 5000, 2000, 100)
        max_frag = st.slider("Max fragment (bp)", 1500, 10000, 2500, 100)
        oh_len = st.slider("Overhang length (bp)", 15, 40, 25)
        min_tm = st.slider("Min Tm (°C)", 40.0, 70.0, 50.0, 1.0)
        max_tm = st.slider("Max Tm (°C)", 50.0, 80.0, 65.0, 1.0)
        min_hamming = st.slider("Min Hamming distance", 1, 10, 5)
        seed = st.number_input("Random seed", value=42, min_value=0)

    with col1:
        st.subheader("Input Sequence")
        sequence = st.text_area(
            "Paste DNA sequence (ATCG only)",
            height=200,
            placeholder="ATCGATCG...",
        )

        if st.button("Design Assembly", type="primary"):
            if not sequence or len(sequence.strip()) < 1000:
                st.error("Please enter a DNA sequence of at least 1000 bp.")
                return

            seq = sequence.strip().upper().replace("\n", "").replace(" ", "")
            invalid = set(seq) - {"A", "T", "C", "G"}
            if invalid:
                st.error(f"Invalid characters: {invalid}. Use only A, T, C, G.")
                return

            with st.spinner(f"Optimizing assembly for {len(seq):,} bp sequence..."):
                config = AssemblyConfig(
                    min_fragment_bp=min_frag,
                    max_fragment_bp=max_frag,
                    default_overhang_bp=oh_len,
                    min_tm=min_tm,
                    max_tm=max_tm,
                    min_hamming_distance=min_hamming,
                )
                solver = AssemblySolver(config=config, seed=seed)
                result = solver.solve(seq)

            # Results
            if result.feasible:
                st.success(f"Feasible partition found in {result.total_time_s:.2f}s ({result.restarts_used} restarts)")
            else:
                st.warning(f"Best-effort partition (not fully feasible). {result.total_time_s:.2f}s, {result.restarts_used} restarts.")

            # Quality scores
            st.subheader("Quality Scores")
            scores = result.quality_scores
            score_cols = st.columns(5)
            score_cols[0].metric("Total", f"{scores['total']:.2f}")
            score_cols[1].metric("Orthogonality", f"{scores['orthogonality']:.2f}")
            score_cols[2].metric("Tm Uniformity", f"{scores['tm_uniformity']:.2f}")
            score_cols[3].metric("GC Balance", f"{scores['gc_balance']:.2f}")
            score_cols[4].metric("Structure", f"{scores['structure']:.2f}")

            # Fragments table
            st.subheader(f"Fragments ({result.partition.num_fragments})")
            st.dataframe(
                result.fragments,
                use_container_width=True,
                hide_index=True,
            )

            # Overhangs table
            if result.overhangs:
                st.subheader(f"Overhangs ({len(result.overhangs)})")
                st.dataframe(
                    result.overhangs,
                    use_container_width=True,
                    hide_index=True,
                )

            # Violations
            if result.constraint_result.violations:
                st.subheader("Constraint Violations")
                for v in result.constraint_result.violations:
                    icon = "❌" if v.severity.value == "fail" else "⚠️"
                    st.markdown(f"{icon} **{v.constraint_name}**: {v.message}")
