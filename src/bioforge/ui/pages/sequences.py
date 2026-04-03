"""Sequence Viewer page."""

import streamlit as st

from bioforge.modules.assembly.core.models import gc_content, reverse_complement


def show():
    st.title("Sequence Viewer")

    sequence = st.text_area("Paste a DNA/RNA/protein sequence", height=200)

    if sequence:
        seq = sequence.strip().upper().replace("\n", "").replace(" ", "")
        st.markdown(f"**Length:** {len(seq):,} bp")

        dna_bases = set(seq) <= {"A", "T", "C", "G", "N"}
        if dna_bases:
            gc = gc_content(seq)
            col1, col2, col3 = st.columns(3)
            col1.metric("Length", f"{len(seq):,} bp")
            col2.metric("GC Content", f"{gc:.1%}")
            col3.metric("Type", "DNA")

            st.subheader("Reverse Complement")
            rc = reverse_complement(seq)
            st.code(rc[:500] + ("..." if len(rc) > 500 else ""), language=None)

            # Base composition
            st.subheader("Base Composition")
            comp = {b: seq.count(b) for b in "ATCGN" if seq.count(b) > 0}
            st.bar_chart(comp)
        else:
            st.info("Non-DNA sequence detected. Showing basic info only.")
            st.metric("Length", f"{len(seq):,}")
