"""Organism-specific codon usage frequency tables.

Each table maps all 64 codons to their relative usage frequency (fraction
of usage among synonymous codons for the same amino acid, 0.0 to 1.0).
Values are derived from published codon usage databases:

- E. coli K12: Kazusa Codon Usage Database, GenBank accession U00096
- S. cerevisiae: Kazusa, GenBank accession R64-1-1
- CHO (Cricetulus griseus): Codon Usage Database, high-expression genes
- HEK293 (Homo sapiens): Kazusa, GenBank Human CDS set

References:
    Nakamura, Gojobori, Ikemura (2000) "Codon usage tabulated from
    international DNA sequence databases." Nucleic Acids Res. 28:292.
    Sharp & Li (1987) "The codon adaptation index." Nucleic Acids Res.
    15:1281-1295.
"""

# Standard genetic code for reference
GENETIC_CODE: dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Reverse lookup: amino acid -> list of codons
AA_TO_CODONS: dict[str, list[str]] = {}
for _codon, _aa in GENETIC_CODE.items():
    AA_TO_CODONS.setdefault(_aa, []).append(_codon)


# ---------------------------------------------------------------------------
# E. coli K12 codon usage frequencies
# Source: Kazusa Codon Usage Database (GenBank U00096)
# Values represent fraction of usage among synonymous codons for each amino acid
# ---------------------------------------------------------------------------
_ECOLI_K12: dict[str, float] = {
    # Phe (F)
    "TTT": 0.58, "TTC": 0.42,
    # Leu (L)
    "TTA": 0.13, "TTG": 0.13, "CTT": 0.10, "CTC": 0.10, "CTA": 0.04, "CTG": 0.50,
    # Ile (I)
    "ATT": 0.49, "ATC": 0.42, "ATA": 0.08,
    # Met (M) — single codon
    "ATG": 1.00,
    # Val (V)
    "GTT": 0.26, "GTC": 0.22, "GTA": 0.15, "GTG": 0.37,
    # Ser (S)
    "TCT": 0.15, "TCC": 0.15, "TCA": 0.12, "TCG": 0.15, "AGT": 0.15, "AGC": 0.28,
    # Pro (P)
    "CCT": 0.16, "CCC": 0.12, "CCA": 0.19, "CCG": 0.52,
    # Thr (T)
    "ACT": 0.17, "ACC": 0.44, "ACA": 0.13, "ACG": 0.27,
    # Ala (A)
    "GCT": 0.16, "GCC": 0.27, "GCA": 0.21, "GCG": 0.36,
    # Tyr (Y)
    "TAT": 0.57, "TAC": 0.43,
    # Stop (*)
    "TAA": 0.64, "TAG": 0.07, "TGA": 0.29,
    # His (H)
    "CAT": 0.57, "CAC": 0.43,
    # Gln (Q)
    "CAA": 0.34, "CAG": 0.66,
    # Asn (N)
    "AAT": 0.45, "AAC": 0.55,
    # Lys (K)
    "AAA": 0.74, "AAG": 0.26,
    # Asp (D)
    "GAT": 0.63, "GAC": 0.37,
    # Glu (E)
    "GAA": 0.69, "GAG": 0.31,
    # Cys (C)
    "TGT": 0.45, "TGC": 0.55,
    # Trp (W) — single codon
    "TGG": 1.00,
    # Arg (R)
    "CGT": 0.36, "CGC": 0.40, "CGA": 0.06, "CGG": 0.10, "AGA": 0.04, "AGG": 0.02,
    # Gly (G)
    "GGT": 0.34, "GGC": 0.40, "GGA": 0.11, "GGG": 0.15,
}

# ---------------------------------------------------------------------------
# S. cerevisiae (yeast) codon usage frequencies
# Source: Kazusa Codon Usage Database (S288C reference genome)
# Yeast has strong codon bias — highly expressed genes use a small subset
# ---------------------------------------------------------------------------
_YEAST: dict[str, float] = {
    # Phe (F)
    "TTT": 0.59, "TTC": 0.41,
    # Leu (L)
    "TTA": 0.28, "TTG": 0.29, "CTT": 0.13, "CTC": 0.06, "CTA": 0.14, "CTG": 0.11,
    # Ile (I)
    "ATT": 0.46, "ATC": 0.26, "ATA": 0.27,
    # Met (M)
    "ATG": 1.00,
    # Val (V)
    "GTT": 0.39, "GTC": 0.21, "GTA": 0.21, "GTG": 0.19,
    # Ser (S)
    "TCT": 0.26, "TCC": 0.16, "TCA": 0.21, "TCG": 0.10, "AGT": 0.16, "AGC": 0.11,
    # Pro (P)
    "CCT": 0.31, "CCC": 0.15, "CCA": 0.42, "CCG": 0.12,
    # Thr (T)
    "ACT": 0.35, "ACC": 0.22, "ACA": 0.30, "ACG": 0.14,
    # Ala (A)
    "GCT": 0.38, "GCC": 0.22, "GCA": 0.29, "GCG": 0.11,
    # Tyr (Y)
    "TAT": 0.56, "TAC": 0.44,
    # Stop (*)
    "TAA": 0.48, "TAG": 0.23, "TGA": 0.29,
    # His (H)
    "CAT": 0.64, "CAC": 0.36,
    # Gln (Q)
    "CAA": 0.69, "CAG": 0.31,
    # Asn (N)
    "AAT": 0.59, "AAC": 0.41,
    # Lys (K)
    "AAA": 0.58, "AAG": 0.42,
    # Asp (D)
    "GAT": 0.65, "GAC": 0.35,
    # Glu (E)
    "GAA": 0.70, "GAG": 0.30,
    # Cys (C)
    "TGT": 0.63, "TGC": 0.37,
    # Trp (W)
    "TGG": 1.00,
    # Arg (R)
    "CGT": 0.14, "CGC": 0.06, "CGA": 0.07, "CGG": 0.04, "AGA": 0.48, "AGG": 0.21,
    # Gly (G)
    "GGT": 0.47, "GGC": 0.19, "GGA": 0.22, "GGG": 0.12,
}

# ---------------------------------------------------------------------------
# CHO (Chinese Hamster Ovary) codon usage frequencies
# Source: Cricetulus griseus CDS data, Kazusa
# CHO is the primary mammalian host for therapeutic protein production
# ---------------------------------------------------------------------------
_CHO: dict[str, float] = {
    # Phe (F)
    "TTT": 0.45, "TTC": 0.55,
    # Leu (L)
    "TTA": 0.07, "TTG": 0.13, "CTT": 0.13, "CTC": 0.20, "CTA": 0.07, "CTG": 0.40,
    # Ile (I)
    "ATT": 0.36, "ATC": 0.48, "ATA": 0.16,
    # Met (M)
    "ATG": 1.00,
    # Val (V)
    "GTT": 0.18, "GTC": 0.24, "GTA": 0.11, "GTG": 0.47,
    # Ser (S)
    "TCT": 0.19, "TCC": 0.22, "TCA": 0.15, "TCG": 0.05, "AGT": 0.15, "AGC": 0.24,
    # Pro (P)
    "CCT": 0.28, "CCC": 0.33, "CCA": 0.27, "CCG": 0.11,
    # Thr (T)
    "ACT": 0.24, "ACC": 0.36, "ACA": 0.28, "ACG": 0.12,
    # Ala (A)
    "GCT": 0.26, "GCC": 0.40, "GCA": 0.23, "GCG": 0.11,
    # Tyr (Y)
    "TAT": 0.43, "TAC": 0.57,
    # Stop (*)
    "TAA": 0.28, "TAG": 0.20, "TGA": 0.52,
    # His (H)
    "CAT": 0.41, "CAC": 0.59,
    # Gln (Q)
    "CAA": 0.25, "CAG": 0.75,
    # Asn (N)
    "AAT": 0.46, "AAC": 0.54,
    # Lys (K)
    "AAA": 0.42, "AAG": 0.58,
    # Asp (D)
    "GAT": 0.46, "GAC": 0.54,
    # Glu (E)
    "GAA": 0.42, "GAG": 0.58,
    # Cys (C)
    "TGT": 0.45, "TGC": 0.55,
    # Trp (W)
    "TGG": 1.00,
    # Arg (R)
    "CGT": 0.08, "CGC": 0.18, "CGA": 0.11, "CGG": 0.20, "AGA": 0.21, "AGG": 0.21,
    # Gly (G)
    "GGT": 0.16, "GGC": 0.34, "GGA": 0.25, "GGG": 0.25,
}

# ---------------------------------------------------------------------------
# HEK293 (Human Embryonic Kidney) codon usage frequencies
# Source: Homo sapiens CDS data, Kazusa (GenBank high-expression CDS set)
# Nearly identical to general human codon usage
# ---------------------------------------------------------------------------
_HEK293: dict[str, float] = {
    # Phe (F)
    "TTT": 0.45, "TTC": 0.55,
    # Leu (L)
    "TTA": 0.07, "TTG": 0.13, "CTT": 0.13, "CTC": 0.20, "CTA": 0.07, "CTG": 0.40,
    # Ile (I)
    "ATT": 0.36, "ATC": 0.48, "ATA": 0.16,
    # Met (M)
    "ATG": 1.00,
    # Val (V)
    "GTT": 0.18, "GTC": 0.24, "GTA": 0.11, "GTG": 0.47,
    # Ser (S)
    "TCT": 0.18, "TCC": 0.22, "TCA": 0.15, "TCG": 0.06, "AGT": 0.15, "AGC": 0.24,
    # Pro (P)
    "CCT": 0.28, "CCC": 0.33, "CCA": 0.27, "CCG": 0.11,
    # Thr (T)
    "ACT": 0.24, "ACC": 0.36, "ACA": 0.28, "ACG": 0.12,
    # Ala (A)
    "GCT": 0.26, "GCC": 0.40, "GCA": 0.23, "GCG": 0.11,
    # Tyr (Y)
    "TAT": 0.43, "TAC": 0.57,
    # Stop (*)
    "TAA": 0.28, "TAG": 0.20, "TGA": 0.52,
    # His (H)
    "CAT": 0.41, "CAC": 0.59,
    # Gln (Q)
    "CAA": 0.25, "CAG": 0.75,
    # Asn (N)
    "AAT": 0.46, "AAC": 0.54,
    # Lys (K)
    "AAA": 0.43, "AAG": 0.57,
    # Asp (D)
    "GAT": 0.46, "GAC": 0.54,
    # Glu (E)
    "GAA": 0.42, "GAG": 0.58,
    # Cys (C)
    "TGT": 0.45, "TGC": 0.55,
    # Trp (W)
    "TGG": 1.00,
    # Arg (R)
    "CGT": 0.08, "CGC": 0.19, "CGA": 0.11, "CGG": 0.21, "AGA": 0.20, "AGG": 0.20,
    # Gly (G)
    "GGT": 0.16, "GGC": 0.34, "GGA": 0.25, "GGG": 0.25,
}

# ---------------------------------------------------------------------------
# Master lookup table: organism name -> codon frequency dict
# ---------------------------------------------------------------------------
CODON_TABLES: dict[str, dict[str, float]] = {
    "ecoli_k12": _ECOLI_K12,
    "yeast": _YEAST,
    "cho": _CHO,
    "hek293": _HEK293,
}


def get_codon_table(organism: str) -> dict[str, float]:
    """Retrieve the codon usage table for an organism.

    Args:
        organism: Organism name (e.g., "ecoli_k12", "yeast", "cho", "hek293").

    Returns:
        Dict mapping each codon to its relative usage frequency.

    Raises:
        ValueError: If organism is not in the database.
    """
    if organism not in CODON_TABLES:
        raise ValueError(
            f"Unknown organism '{organism}'. "
            f"Available: {', '.join(sorted(CODON_TABLES.keys()))}"
        )
    return CODON_TABLES[organism]


def codon_frequency(codon: str, organism: str) -> float:
    """Get the usage frequency of a specific codon for an organism.

    Args:
        codon: 3-letter DNA codon (e.g., "ATG").
        organism: Organism name.

    Returns:
        Usage frequency (0.0 to 1.0).
    """
    table = get_codon_table(organism)
    return table.get(codon.upper(), 0.0)
