"""Tests for the variants module: VCF parsing, annotation, and VariantModule."""

import asyncio

from bioforge.modules.variants import VariantModule


# A minimal reference sequence (200 bp) for annotation tests.
# CDS feature covers positions 11-90 (1-based) on the + strand.
_REFERENCE = (
    "AAAAAAAAAA"  # 1-10   (intergenic)
    "ATGAAAGCTTTTGCAGATCCCAGTACTGGGCAACCATTTCAGGACGATCACGTTTAAACTG"
    "CTTCAGGAATCGGCCATGGA"  # 11-90  (CDS: 80bp)
    "TTTTTTTTTT" * 11  # 91-200 (intergenic)
)

_FEATURES = [
    {"type": "CDS", "start": 11, "end": 90, "strand": "+", "name": "testGene"},
]


class TestVCFParsing:
    def test_parse_simple_vcf(self):
        vcf_content = (
            "chr1\t100\t.\tA\tG\t30\tPASS\t.\n"
            "chr1\t200\t.\tC\tT\t40\tPASS\t.\n"
            "chr2\t300\t.\tG\tA\t50\tPASS\t.\n"
        )
        mod = VariantModule()
        result = asyncio.run(mod._load_vcf({"vcf_content": vcf_content}))

        assert result["count"] == 3
        variants = result["variants"]
        assert variants[0]["chrom"] == "chr1"
        assert variants[0]["pos"] == 100
        assert variants[0]["ref"] == "A"
        assert variants[0]["alt"] == "G"
        assert variants[2]["chrom"] == "chr2"
        assert variants[2]["pos"] == 300

    def test_skip_header_lines(self):
        vcf_content = (
            "##fileformat=VCFv4.2\n"
            "##INFO=<ID=DP,Number=1,Type=Integer>\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "chr1\t100\trs123\tA\tG\t30\tPASS\tDP=50\n"
            "chr1\t200\trs456\tC\tT\t40\tPASS\tDP=60\n"
        )
        mod = VariantModule()
        result = asyncio.run(mod._load_vcf({"vcf_content": vcf_content}))

        # Only data lines should be parsed, not headers
        assert result["count"] == 2
        assert result["variants"][0]["pos"] == 100
        assert result["variants"][1]["pos"] == 200


class TestVariantAnnotation:
    def test_coding_variant(self):
        """A variant inside the CDS feature should be annotated as coding."""
        mod = VariantModule()
        result = asyncio.run(
            mod._annotate_variants(
                {
                    "variants": [
                        {"chrom": "chr1", "pos": 20, "ref": "T", "alt": "C"},
                    ],
                    "reference_sequence": _REFERENCE,
                    "features": _FEATURES,
                }
            )
        )

        ann = result["annotations"][0]
        assert ann["region"] == "coding"

    def test_noncoding_variant(self):
        """A variant outside any feature should be intergenic."""
        mod = VariantModule()
        result = asyncio.run(
            mod._annotate_variants(
                {
                    "variants": [
                        {"chrom": "chr1", "pos": 5, "ref": "A", "alt": "G"},
                    ],
                    "reference_sequence": _REFERENCE,
                    "features": _FEATURES,
                }
            )
        )

        ann = result["annotations"][0]
        assert ann["region"] in ("intergenic", "noncoding")

    def test_synonymous(self):
        """A coding SNV that does not change the amino acid -> synonymous."""
        # Position 13 (1-based) in the reference is 'A' within the CDS.
        # CDS starts at pos 11 (0-based index 10).
        # Codon 1 = positions 11,12,13 = "ATG" (Met) -- changing pos 13
        # would change the codon. We need a truly synonymous change.
        # Third codon = positions 17,18,19 = look at the reference...
        # Positions 11-16 (1-based): A T G A A A -> codon1=ATG(M), codon2=AAA(K)
        # For Lys (K): AAA and AAG both encode K. So changing pos 16 (A->G) should be synonymous.
        # pos 16 is the 3rd base of codon 2 (0-based offset 5 from CDS start).
        mod = VariantModule()
        result = asyncio.run(
            mod._annotate_variants(
                {
                    "variants": [
                        {"chrom": "chr1", "pos": 16, "ref": "A", "alt": "G"},
                    ],
                    "reference_sequence": _REFERENCE,
                    "features": _FEATURES,
                }
            )
        )

        ann = result["annotations"][0]
        assert ann["region"] == "coding"
        assert ann["effect"] == "synonymous"

    def test_nonsynonymous(self):
        """A coding SNV that changes the amino acid -> nonsynonymous."""
        # Codon 2 = positions 14,15,16 = "AAA" (K).
        # Changing pos 14 from A->T gives "TAA" = stop => nonsense.
        # Changing pos 14 from A->G gives "GAA" = E => nonsynonymous.
        mod = VariantModule()
        result = asyncio.run(
            mod._annotate_variants(
                {
                    "variants": [
                        {"chrom": "chr1", "pos": 14, "ref": "A", "alt": "G"},
                    ],
                    "reference_sequence": _REFERENCE,
                    "features": _FEATURES,
                }
            )
        )

        ann = result["annotations"][0]
        assert ann["region"] == "coding"
        assert ann["effect"] in ("nonsynonymous", "missense")


class TestVariantModule:
    def test_module_info(self):
        mod = VariantModule()
        info = mod.info()

        assert info.name == "variants"

    def test_has_3_capabilities(self):
        mod = VariantModule()
        caps = mod.capabilities()

        assert len(caps) == 3

    def test_load_vcf_handler(self):
        vcf_content = "chr1\t100\t.\tA\tG\t30\tPASS\t.\n"
        mod = VariantModule()
        result = asyncio.run(mod._load_vcf({"vcf_content": vcf_content}))

        assert result["count"] == 1
        assert result["variants"][0]["chrom"] == "chr1"
        assert result["variants"][0]["ref"] == "A"
        assert result["variants"][0]["alt"] == "G"
