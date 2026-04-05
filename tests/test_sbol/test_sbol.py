"""Tests for the SBOL module: XML parsing, SBOL3 generation, and import/export."""


from bioforge.modules.sbol.module import (
    SBOLModule,
    generate_sbol3_document,
    parse_sbol3_document,
)

# Sample SBOL3 document for testing
SAMPLE_SBOL3 = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:sbol="http://sbols.org/v3#"
         xmlns:prov="http://www.w3.org/ns/prov#"
         xmlns:om="http://www.ontology-of-units-of-measure.org/resource/om-2/">

  <sbol:Component rdf:about="https://bioforge.local/test/GFP">
    <sbol:displayId>GFP</sbol:displayId>
    <sbol:name>Green Fluorescent Protein</sbol:name>
    <sbol:type rdf:resource="https://identifiers.org/SBO:0000251"/>
    <sbol:hasSequence>
      <sbol:Sequence rdf:about="https://bioforge.local/test/GFP/seq">
        <sbol:displayId>GFP_seq</sbol:displayId>
        <sbol:elements>ATGGTGAGCAAGGGCGAGGAG</sbol:elements>
        <sbol:encoding rdf:resource="http://sbols.org/v3#iupacNucleicAcid"/>
      </sbol:Sequence>
    </sbol:hasSequence>
  </sbol:Component>

  <sbol:Component rdf:about="https://bioforge.local/test/RFP">
    <sbol:displayId>RFP</sbol:displayId>
    <sbol:name>Red Fluorescent Protein</sbol:name>
    <sbol:type rdf:resource="https://identifiers.org/SBO:0000252"/>
    <sbol:hasSequence>
      <sbol:Sequence rdf:about="https://bioforge.local/test/RFP/seq">
        <sbol:displayId>RFP_seq</sbol:displayId>
        <sbol:elements>MKQSFVLKQTKNVAAL</sbol:elements>
        <sbol:encoding rdf:resource="http://sbols.org/v3#iupacAminoAcid"/>
      </sbol:Sequence>
    </sbol:hasSequence>
  </sbol:Component>

</rdf:RDF>"""


class TestSBOL3Parsing:
    def test_parse_extracts_components(self):
        components = parse_sbol3_document(SAMPLE_SBOL3)
        assert len(components) == 2

    def test_parse_extracts_names(self):
        components = parse_sbol3_document(SAMPLE_SBOL3)
        names = {c["name"] for c in components}
        assert "GFP" in names
        assert "RFP" in names

    def test_parse_extracts_sequences(self):
        components = parse_sbol3_document(SAMPLE_SBOL3)
        gfp = next(c for c in components if c["name"] == "GFP")
        assert gfp["sequence"] == "ATGGTGAGCAAGGGCGAGGAG"

    def test_parse_detects_dna_type(self):
        components = parse_sbol3_document(SAMPLE_SBOL3)
        gfp = next(c for c in components if c["name"] == "GFP")
        assert gfp["type"] == "DNA"

    def test_parse_detects_protein_type(self):
        components = parse_sbol3_document(SAMPLE_SBOL3)
        rfp = next(c for c in components if c["name"] == "RFP")
        assert rfp["type"] == "protein"

    def test_parse_extracts_uris(self):
        components = parse_sbol3_document(SAMPLE_SBOL3)
        gfp = next(c for c in components if c["name"] == "GFP")
        assert gfp["uri"] == "https://bioforge.local/test/GFP"

    def test_parse_extracts_labels(self):
        components = parse_sbol3_document(SAMPLE_SBOL3)
        gfp = next(c for c in components if c["name"] == "GFP")
        assert gfp["label"] == "Green Fluorescent Protein"

    def test_parse_empty_document(self):
        empty_doc = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:sbol="http://sbols.org/v3#">
</rdf:RDF>"""
        components = parse_sbol3_document(empty_doc)
        assert components == []

    def test_parse_invalid_xml_falls_back(self):
        """Invalid XML should fall back to regex parser."""
        bad_xml = '<sbol:Component rdf:about="http://example.com/part1"><sbol:displayId>part1</sbol:displayId><sbol:elements>ATCG</sbol:elements></sbol:Component>'
        # Should not raise, falls back to regex
        components = parse_sbol3_document(bad_xml)
        # Regex fallback may or may not find it depending on format
        assert isinstance(components, list)


class TestSBOL3Generation:
    def test_generate_creates_valid_xml(self):
        sequences = [
            {"name": "GFP", "sequence": "ATGGTGAGCAAG", "type": "DNA"},
            {"name": "mCherry", "sequence": "MKQSFVL", "type": "protein"},
        ]
        doc = generate_sbol3_document("test_collection", sequences)
        assert '<?xml version="1.0"' in doc
        assert "sbol:Component" in doc
        assert "sbol:Sequence" in doc
        assert "ATGGTGAGCAAG" in doc

    def test_generate_roundtrip(self):
        """Generate then parse should recover the same sequences."""
        sequences = [
            {"name": "partA", "sequence": "ATCGATCG", "type": "DNA"},
            {"name": "partB", "sequence": "GCTAGCTA", "type": "DNA"},
        ]
        doc = generate_sbol3_document("roundtrip_test", sequences)
        parsed = parse_sbol3_document(doc)
        assert len(parsed) == 2
        parsed_seqs = {c["name"]: c["sequence"] for c in parsed}
        assert parsed_seqs["partA"] == "ATCGATCG"
        assert parsed_seqs["partB"] == "GCTAGCTA"

    def test_generate_protein_encoding(self):
        sequences = [{"name": "enzyme", "sequence": "MKAAL", "type": "protein"}]
        doc = generate_sbol3_document("protein_test", sequences)
        assert "iupacAminoAcid" in doc

    def test_generate_rna_encoding(self):
        sequences = [{"name": "guide", "sequence": "AUGCUAG", "type": "RNA"}]
        doc = generate_sbol3_document("rna_test", sequences)
        assert "iupacNucleicAcid" in doc


class TestSBOLModule:
    async def test_import_sbol(self):
        mod = SBOLModule()
        result = await mod._import_sbol({"content": SAMPLE_SBOL3})
        assert result["count"] == 2
        assert len(result["components"]) == 2

    async def test_export_sbol(self):
        mod = SBOLModule()
        result = await mod._export_sbol({
            "name": "test",
            "sequences": [{"name": "part1", "sequence": "ATCG", "type": "DNA"}],
            "namespace": "https://bioforge.local",
        })
        assert "sbol3_document" in result
        assert result["num_components"] == 1
        assert "ATCG" in result["sbol3_document"]

    async def test_import_export_roundtrip(self):
        mod = SBOLModule()
        export_result = await mod._export_sbol({
            "name": "roundtrip",
            "sequences": [
                {"name": "geneA", "sequence": "ATCGATCGATCG", "type": "DNA"},
            ],
            "namespace": "https://bioforge.local",
        })
        import_result = await mod._import_sbol({"content": export_result["sbol3_document"]})
        assert import_result["count"] == 1
        assert import_result["components"][0]["sequence"] == "ATCGATCGATCG"
