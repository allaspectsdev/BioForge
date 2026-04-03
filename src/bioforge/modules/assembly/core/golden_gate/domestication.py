"""Sequence domestication for Golden Gate assembly.

Removes internal Type IIS restriction enzyme recognition sites from DNA
sequences by introducing synonymous (silent) codon mutations. This is
required before a part can be used in a Golden Gate reaction, since
internal sites would cause unwanted cleavage.

The engine respects the genetic code: only mutations that preserve the
encoded amino acid are introduced. Non-coding regions cannot be
automatically domesticated and are flagged for manual review.
"""

import logging
from dataclasses import dataclass, field

from bioforge.modules.assembly.core.golden_gate.enzymes import ENZYMES, TypeIISEnzyme
from bioforge.modules.assembly.core.models import reverse_complement

logger = logging.getLogger(__name__)


# Standard genetic code: codon -> amino acid
CODON_TO_AA: dict[str, str] = {
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

# Reverse map: amino acid -> list of synonymous codons
AA_TO_CODONS: dict[str, list[str]] = {}
for _codon, _aa in CODON_TO_AA.items():
    AA_TO_CODONS.setdefault(_aa, []).append(_codon)


@dataclass(frozen=True, slots=True)
class Mutation:
    """A single silent mutation introduced during domestication.

    Attributes:
        position: 0-based position in the original sequence.
        original_codon: The original codon at this position.
        mutated_codon: The replacement codon (synonymous).
        amino_acid: The amino acid encoded by both codons.
        site_destroyed: The enzyme recognition site that was destroyed.
        strand: Which strand the site was on ("fwd" or "rev").
    """

    position: int
    original_codon: str
    mutated_codon: str
    amino_acid: str
    site_destroyed: str
    strand: str


@dataclass
class DomesticationResult:
    """Result of sequence domestication.

    Attributes:
        original_sequence: The input sequence.
        domesticated_sequence: The modified sequence with sites removed.
        mutations: List of silent mutations introduced.
        sites_found: Total number of internal enzyme sites found.
        sites_removed: Number of sites successfully removed.
        sites_remaining: Number of sites that could not be removed
            (e.g., in non-coding regions or unavoidable).
        enzyme: The enzyme used for domestication.
    """

    original_sequence: str
    domesticated_sequence: str
    mutations: list[Mutation] = field(default_factory=list)
    sites_found: int = 0
    sites_removed: int = 0
    sites_remaining: int = 0
    enzyme: str = ""


def _find_sites(sequence: str, enzyme: TypeIISEnzyme) -> list[tuple[int, str]]:
    """Find all enzyme recognition sites in a sequence on both strands.

    Returns:
        List of (position, strand) tuples. Position is 0-based index
        in the sequence where the site starts.
    """
    sites: list[tuple[int, str]] = []
    site_fwd = enzyme.recognition_site.upper()
    site_rev = reverse_complement(site_fwd)
    seq = sequence.upper()

    # Forward strand
    pos = 0
    while True:
        idx = seq.find(site_fwd, pos)
        if idx == -1:
            break
        sites.append((idx, "fwd"))
        pos = idx + 1

    # Reverse strand
    pos = 0
    while True:
        idx = seq.find(site_rev, pos)
        if idx == -1:
            break
        sites.append((idx, "rev"))
        pos = idx + 1

    return sorted(sites, key=lambda x: x[0])


def _codons_overlapping_site(
    site_start: int,
    site_len: int,
    cds_start: int,
    seq_len: int,
) -> list[int]:
    """Find which codon positions (in-frame relative to cds_start) overlap a site.

    Returns a list of codon start positions (0-based in the sequence) that
    overlap with the recognition site.
    """
    site_end = site_start + site_len
    codon_positions = []

    # Walk codons from cds_start
    pos = cds_start
    while pos + 3 <= seq_len:
        codon_end = pos + 3
        # Check if this codon overlaps the site
        if pos < site_end and codon_end > site_start:
            codon_positions.append(pos)
        if pos >= site_end:
            break
        pos += 3

    return codon_positions


class DomesticationEngine:
    """Removes internal enzyme recognition sites via synonymous mutations.

    For each internal Type IIS enzyme site found in a coding sequence, the
    engine tries all synonymous codon substitutions at overlapping positions
    until one is found that destroys the recognition site without changing
    the protein sequence.

    Args:
        enzyme_name: Name of the enzyme to domesticate for (default "BsaI").
        codon_table: Organism-specific codon preferences. If provided,
            the engine will prefer higher-frequency codons when multiple
            synonymous options exist. Should be a dict mapping codons to
            usage frequencies.
    """

    def __init__(
        self,
        enzyme_name: str = "BsaI",
        codon_table: dict[str, float] | None = None,
    ):
        if enzyme_name not in ENZYMES:
            raise ValueError(f"Unknown enzyme: {enzyme_name}")
        self.enzyme = ENZYMES[enzyme_name]
        self.codon_table = codon_table or {}

    def domesticate(
        self,
        sequence: str,
        cds_start: int = 0,
        cds_end: int | None = None,
    ) -> DomesticationResult:
        """Remove internal enzyme sites from a sequence using silent mutations.

        Args:
            sequence: DNA sequence to domesticate.
            cds_start: Start position of the coding sequence (0-based).
                Only sites within the CDS can be automatically removed.
            cds_end: End position of the coding sequence (exclusive).
                Defaults to len(sequence).

        Returns:
            DomesticationResult with the modified sequence and mutation log.
        """
        if cds_end is None:
            cds_end = len(sequence)

        seq = list(sequence.upper())
        original = sequence.upper()
        site_len = len(self.enzyme.recognition_site)

        # Find all internal sites
        sites = _find_sites("".join(seq), self.enzyme)
        total_sites = len(sites)

        if total_sites == 0:
            return DomesticationResult(
                original_sequence=original,
                domesticated_sequence=original,
                sites_found=0,
                sites_removed=0,
                sites_remaining=0,
                enzyme=self.enzyme.name,
            )

        mutations: list[Mutation] = []
        sites_removed = 0
        sites_remaining = 0

        # Process each site
        for site_start, strand in sites:
            # Re-check if site still exists (previous mutation may have destroyed it)
            current_seq = "".join(seq)
            site_fwd = self.enzyme.recognition_site.upper()
            site_rev = reverse_complement(site_fwd)
            check_site = site_fwd if strand == "fwd" else site_rev

            if current_seq[site_start:site_start + site_len] != check_site:
                # Site already destroyed by a previous mutation
                sites_removed += 1
                continue

            # Check if site is within the CDS
            site_end = site_start + site_len
            if site_start < cds_start or site_end > cds_end:
                logger.warning(
                    "Enzyme site at position %d is outside CDS (%d-%d), "
                    "cannot auto-domesticate",
                    site_start, cds_start, cds_end,
                )
                sites_remaining += 1
                continue

            # Find overlapping codons
            codon_positions = _codons_overlapping_site(
                site_start, site_len, cds_start, len(seq)
            )

            if not codon_positions:
                sites_remaining += 1
                continue

            # Try synonymous substitution at each overlapping codon
            fixed = False
            for codon_pos in codon_positions:
                original_codon = "".join(seq[codon_pos:codon_pos + 3])
                if len(original_codon) != 3:
                    continue

                aa = CODON_TO_AA.get(original_codon)
                if aa is None:
                    continue

                # Get all synonymous codons
                synonymous = [
                    c for c in AA_TO_CODONS[aa] if c != original_codon
                ]

                # Sort by codon usage preference (higher frequency first)
                if self.codon_table:
                    synonymous.sort(
                        key=lambda c: self.codon_table.get(c, 0.0),
                        reverse=True,
                    )

                for alt_codon in synonymous:
                    # Test if this substitution destroys the site
                    test_seq = list(seq)
                    test_seq[codon_pos:codon_pos + 3] = list(alt_codon)
                    test_region = "".join(
                        test_seq[site_start:site_start + site_len]
                    )

                    if test_region != check_site:
                        # Success: this mutation destroys the site
                        seq[codon_pos:codon_pos + 3] = list(alt_codon)
                        mutations.append(
                            Mutation(
                                position=codon_pos,
                                original_codon=original_codon,
                                mutated_codon=alt_codon,
                                amino_acid=aa,
                                site_destroyed=check_site,
                                strand=strand,
                            )
                        )
                        sites_removed += 1
                        fixed = True
                        break

                if fixed:
                    break

            if not fixed:
                logger.warning(
                    "Could not remove %s site at position %d with silent mutations",
                    self.enzyme.name, site_start,
                )
                sites_remaining += 1

        return DomesticationResult(
            original_sequence=original,
            domesticated_sequence="".join(seq),
            mutations=mutations,
            sites_found=total_sites,
            sites_removed=sites_removed,
            sites_remaining=sites_remaining,
            enzyme=self.enzyme.name,
        )
