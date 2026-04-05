"""Tests for MCP server tools — verifying they work without asyncio.run() crashes."""



class TestMCPAssemblyTools:
    """Test synchronous assembly MCP tools."""

    def test_design_assembly_basic(self):
        from bioforge.mcp.server import design_assembly
        seq = "ATCG" * 1000  # 4kb sequence
        result = design_assembly(seq, min_fragment_bp=1500, max_fragment_bp=2500)
        assert "feasible" in result
        assert "error" not in result or not result.get("error")

    def test_calculate_tm(self):
        from bioforge.mcp.server import calculate_tm
        result = calculate_tm("ATCGATCGATCG")
        assert "tm_celsius" in result
        assert "gc_content" in result
        assert result["length"] == 12
        assert 0 <= result["gc_content"] <= 1

    def test_get_reverse_complement(self):
        from bioforge.mcp.server import get_reverse_complement
        result = get_reverse_complement("ATCG")
        assert result == "CGAT"

    def test_check_overhangs_includes_hairpin(self):
        """Verify the overhang check now includes hairpin dG."""
        from bioforge.mcp.server import check_overhangs
        result = check_overhangs(["ATCGATCGATCGATCGATCGATCGATCG"])
        assert len(result["overhangs"]) == 1
        oh = result["overhangs"][0]
        assert "hairpin_dg_kcal" in oh
        assert "pass" in oh

    def test_check_synthesis_feasibility(self):
        """Verify synthesis feasibility uses check_batch, not the old check()."""
        from bioforge.mcp.server import check_synthesis_feasibility
        result = check_synthesis_feasibility(["ATCG" * 250])  # 1kb seq
        assert "error" not in result or not result.get("error")
        assert "results" in result
        assert "all_feasible" in result

    def test_optimize_codons(self):
        from bioforge.mcp.server import optimize_codons
        result = optimize_codons("MKAAL")
        assert "error" not in result or not result.get("error")


class TestMCPAsyncTools:
    """Test async MCP tools work without asyncio.run() crashes."""

    async def test_embed_sequence(self):
        from bioforge.mcp.server import embed_sequence
        result = await embed_sequence("ATCGATCG")
        assert "status" in result
        # Will use mock client since no GPU
        assert result["status"] in ("computed", "failed")

    async def test_score_variant(self):
        from bioforge.mcp.server import score_variant
        result = await score_variant("ATCGATCG", 3, "G", "A")
        assert "position" in result or "error" in result

    async def test_predict_structure(self):
        from bioforge.mcp.server import predict_structure
        result = await predict_structure("MKAAL")
        assert "mean_plddt" in result or "error" in result

    async def test_search_registry(self):
        from bioforge.mcp.server import search_registry
        # May fail due to network, but should not crash
        result = await search_registry("GFP", limit=3)
        assert isinstance(result, dict)

    async def test_pairwise_align(self):
        from bioforge.mcp.server import pairwise_align
        result = await pairwise_align(["ATCGATCG", "ATCAATCG"])
        assert "aligned_sequences" in result
        assert result["alignment_length"] > 0

    async def test_multiple_align(self):
        from bioforge.mcp.server import multiple_align
        result = await multiple_align(["ATCG", "ATAG", "ATCG"])
        assert "aligned_sequences" in result
        assert len(result["aligned_sequences"]) == 3

    async def test_annotate_variants(self):
        from bioforge.mcp.server import annotate_variants
        result = await annotate_variants(
            reference_sequence="ATGATCGATCGATCGATCG",
            variants=[{"chrom": "chr1", "pos": 5, "ref": "C", "alt": "T"}],
        )
        assert "annotations" in result or "error" in result

    async def test_parse_vcf(self):
        from bioforge.mcp.server import parse_vcf
        vcf_content = "chr1\t100\t.\tA\tT\t50\tPASS\t."
        result = await parse_vcf(vcf_content)
        assert result["count"] == 1

    async def test_list_protocols(self):
        from bioforge.mcp.server import list_protocols
        result = await list_protocols()
        assert isinstance(result, dict)

    async def test_import_sbol(self):
        from bioforge.mcp.server import import_sbol
        sbol_doc = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:sbol="http://sbols.org/v3#">
  <sbol:Component rdf:about="https://example.com/part1">
    <sbol:displayId>part1</sbol:displayId>
    <sbol:name>Test Part</sbol:name>
    <sbol:hasSequence>
      <sbol:Sequence rdf:about="https://example.com/part1/seq">
        <sbol:elements>ATCG</sbol:elements>
        <sbol:encoding rdf:resource="http://sbols.org/v3#iupacNucleicAcid"/>
      </sbol:Sequence>
    </sbol:hasSequence>
  </sbol:Component>
</rdf:RDF>"""
        result = await import_sbol(sbol_doc)
        assert result["count"] == 1

    async def test_export_sbol(self):
        from bioforge.mcp.server import export_sbol
        result = await export_sbol(
            name="test",
            sequences=[{"name": "part1", "sequence": "ATCG"}],
        )
        assert "sbol3_document" in result
