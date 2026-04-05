"""SBOL module: Synthetic Biology Open Language import/export and registry search."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
)
from bioforge.modules.sbol.schemas import (
    RegistryPart,
    RegistrySearchRequest,
    SBOLExportRequest,
    SBOLImportRequest,
)

logger = logging.getLogger(__name__)

SYNBIOHUB_PUBLIC = "https://synbiohub.org"


# ---------------------------------------------------------------------------
# SBOL3 parsing / generation helpers
# ---------------------------------------------------------------------------


def parse_sbol3_document(content: str) -> list[dict]:
    """Parse SBOL3 XML and extract component sequences.

    Uses ElementTree XML parser for robust handling of namespaced attributes,
    nested elements, and real-world SBOL3 documents from SynBioHub/iGEM.
    """
    # Define SBOL3 namespaces
    ns = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "sbol": "http://sbols.org/v3#",
        "prov": "http://www.w3.org/ns/prov#",
    }

    components: list[dict] = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        logger.warning("Failed to parse SBOL3 document as XML, falling back to regex")
        return _parse_sbol3_regex_fallback(content)

    # Find all Component elements (try both namespaced and prefixed)
    for comp in root.findall("sbol:Component", ns):
        uri = comp.get(f"{{{ns['rdf']}}}about", "")

        display_id_el = comp.find("sbol:displayId", ns)
        name_el = comp.find("sbol:name", ns)
        type_el = comp.find("sbol:type", ns)

        # Extract sequence from nested Sequence element
        sequence_text = ""
        encoding = ""
        seq_el = comp.find(".//sbol:Sequence", ns)
        if seq_el is not None:
            elements_el = seq_el.find("sbol:elements", ns)
            if elements_el is not None and elements_el.text:
                sequence_text = elements_el.text.strip()
            encoding_el = seq_el.find("sbol:encoding", ns)
            if encoding_el is not None:
                encoding = encoding_el.get(f"{{{ns['rdf']}}}resource", "")

        # Determine sequence type from encoding
        seq_type = "DNA"
        if encoding:
            if "AminoAcid" in encoding or "iupacAminoAcid" in encoding:
                seq_type = "protein"
            elif "rna" in encoding.lower():
                seq_type = "RNA"

        sbol_type = ""
        if type_el is not None:
            sbol_type = type_el.get(f"{{{ns['rdf']}}}resource", "")

        components.append({
            "uri": uri,
            "name": display_id_el.text if display_id_el is not None and display_id_el.text else "",
            "label": name_el.text if name_el is not None and name_el.text else "",
            "sequence": sequence_text,
            "type": seq_type,
            "sbol_type": sbol_type,
        })

    return components


def _parse_sbol3_regex_fallback(content: str) -> list[dict]:
    """Regex fallback for documents that fail XML parsing (e.g. fragments)."""
    components: list[dict] = []
    comp_pattern = re.compile(
        r'<sbol:Component[^>]*about="([^"]*)"(.*?)</sbol:Component>',
        re.DOTALL,
    )
    for match in comp_pattern.finditer(content):
        uri = match.group(1)
        block = match.group(2)
        name_match = re.search(r"<sbol:displayId>([^<]*)</sbol:displayId>", block)
        label_match = re.search(r"<sbol:name>([^<]*)</sbol:name>", block)
        elements_match = re.search(r"<sbol:elements>([^<]*)</sbol:elements>", block)
        encoding_match = re.search(r'<sbol:encoding[^>]*resource="([^"]*)"', block)
        type_match = re.search(r'<sbol:type[^>]*resource="([^"]*)"', block)

        seq_type = "DNA"
        if encoding_match:
            enc = encoding_match.group(1)
            if "AminoAcid" in enc:
                seq_type = "protein"
            elif "rna" in enc.lower():
                seq_type = "RNA"

        components.append({
            "uri": uri,
            "name": name_match.group(1) if name_match else "",
            "label": label_match.group(1) if label_match else "",
            "sequence": elements_match.group(1) if elements_match else "",
            "type": seq_type,
            "sbol_type": type_match.group(1) if type_match else "",
        })
    return components


def generate_sbol3_document(
    name: str,
    sequences: list[dict],
    namespace: str = "https://bioforge.local",
) -> str:
    """Generate a minimal valid SBOL3 document in RDF/XML format.

    Args:
        name: Collection/document name.
        sequences: List of dicts with 'name', 'sequence', and optional 'type'.
        namespace: Base namespace URI.

    Returns:
        SBOL3 RDF/XML string.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        '         xmlns:sbol="http://sbols.org/v3#"',
        '         xmlns:prov="http://www.w3.org/ns/prov#"',
        '         xmlns:om="http://www.ontology-of-units-of-measure.org/resource/om-2/">',
        "",
        f'  <!-- BioForge SBOL3 Export: {name} -->',
        "",
    ]

    for seq_info in sequences:
        seq_name = seq_info.get("name", "unnamed")
        seq_data = seq_info.get("sequence", "")
        seq_type = seq_info.get("type", "DNA").lower()

        # Determine encoding URI
        if seq_type in ("dna", "rna"):
            encoding = "http://sbols.org/v3#iupacNucleicAcid"
        else:
            encoding = "http://sbols.org/v3#iupacAminoAcid"

        # Determine component type
        if seq_type == "dna":
            sbo_type = "https://identifiers.org/SBO:0000251"  # DNA
        elif seq_type == "rna":
            sbo_type = "https://identifiers.org/SBO:0000250"  # RNA
        else:
            sbo_type = "https://identifiers.org/SBO:0000252"  # Protein

        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", seq_name)
        comp_uri = f"{namespace}/{name}/{safe_name}"
        seq_uri = f"{comp_uri}/seq"

        lines.extend(
            [
                f'  <sbol:Component rdf:about="{comp_uri}">',
                f"    <sbol:displayId>{safe_name}</sbol:displayId>",
                f"    <sbol:name>{seq_name}</sbol:name>",
                f'    <sbol:type rdf:resource="{sbo_type}"/>',
                "    <sbol:hasSequence>",
                f'      <sbol:Sequence rdf:about="{seq_uri}">',
                f"        <sbol:displayId>{safe_name}_seq</sbol:displayId>",
                f"        <sbol:elements>{seq_data}</sbol:elements>",
                f'        <sbol:encoding rdf:resource="{encoding}"/>',
                "      </sbol:Sequence>",
                "    </sbol:hasSequence>",
                "  </sbol:Component>",
                "",
            ]
        )

    lines.append("</rdf:RDF>")
    return "\n".join(lines)


async def search_synbiohub(
    query: str,
    limit: int = 10,
    instance_url: str = SYNBIOHUB_PUBLIC,
    part_type: str = "",
) -> dict[str, Any]:
    """Search SynBioHub public registry for biological parts.

    Makes a real HTTP request to the SynBioHub API.
    """
    # Build search URL
    search_path = f"/search/{query}/1"
    if part_type:
        search_path += f"&type={part_type}"

    url = f"{instance_url}{search_path}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                results = resp.json()
                parts: list[dict] = []
                for item in results[:limit]:
                    part = RegistryPart(
                        uri=item.get("uri", ""),
                        name=item.get("name", ""),
                        display_id=item.get("displayId", ""),
                        description=item.get("description", ""),
                        part_type=item.get("type", ""),
                        registry=instance_url,
                    )
                    parts.append(part.model_dump())
                return {"query": query, "results": parts, "total": len(parts)}
            return {
                "query": query,
                "results": [],
                "error": f"HTTP {resp.status_code}",
            }
    except httpx.TimeoutException:
        return {"query": query, "results": [], "error": "Request timed out"}
    except Exception as e:
        logger.warning("SynBioHub search failed: %s", e)
        return {"query": query, "results": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Module class
# ---------------------------------------------------------------------------


class SBOLModule(BioForgeModule):
    """SBOL3 import/export and SynBioHub registry search.

    Capabilities:
    - import_sbol: Parse SBOL3 document and extract component sequences
    - export_sbol: Generate SBOL3 document from BioForge assembly results
    - search_registry: Search SynBioHub for standard biological parts
    """

    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="sbol",
            version="0.1.0",
            description="SBOL3 import/export and SynBioHub registry search",
            author="BioForge",
            tags=["sbol", "synbiohub", "standards", "registry", "igem"],
        )

    def capabilities(self) -> list[ModuleCapability]:
        return [
            ModuleCapability(
                name="import_sbol",
                description=(
                    "Import sequences and components from an SBOL3 document. "
                    "Parses XML/RDF format and extracts component names, sequences, and types."
                ),
                input_schema=SBOLImportRequest.model_json_schema(),
                output_schema={
                    "type": "object",
                    "properties": {
                        "components": {"type": "array"},
                        "count": {"type": "integer"},
                    },
                },
                handler=self._import_sbol,
            ),
            ModuleCapability(
                name="export_sbol",
                description=(
                    "Export BioForge sequences as a minimal valid SBOL3 document. "
                    "Generates RDF/XML with Component and Sequence entities."
                ),
                input_schema=SBOLExportRequest.model_json_schema(),
                output_schema={
                    "type": "object",
                    "properties": {
                        "sbol3_document": {"type": "string"},
                        "num_components": {"type": "integer"},
                    },
                },
                handler=self._export_sbol,
            ),
            ModuleCapability(
                name="search_registry",
                description=(
                    "Search SynBioHub for standard biological parts by keyword. "
                    "Returns part URIs, names, descriptions, and types from the public registry."
                ),
                input_schema=RegistrySearchRequest.model_json_schema(),
                output_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "results": {"type": "array"},
                        "total": {"type": "integer"},
                    },
                },
                handler=self._search_registry,
            ),
        ]

    def pipeline_steps(self) -> list[ModulePipelineStep]:
        return [
            ModulePipelineStep(
                step_type="sbol.export",
                description="Export sequences as SBOL3 document",
                input_ports={"name": "str", "sequences": "list[dict]"},
                output_ports={"document": "str"},
                handler=self._export_sbol_step,
            ),
        ]

    def mcp_tools(self) -> list:
        return [self._import_sbol, self._export_sbol, self._search_registry]

    # ------------------------------------------------------------------
    # Capability handlers
    # ------------------------------------------------------------------

    async def _import_sbol(self, request: dict) -> dict:
        """Import and parse an SBOL3 document."""
        req = SBOLImportRequest(**request)
        components = parse_sbol3_document(req.content)
        return {"components": components, "count": len(components)}

    async def _export_sbol(self, request: dict) -> dict:
        """Export sequences as SBOL3 document."""
        req = SBOLExportRequest(**request)
        doc = generate_sbol3_document(
            name=req.name,
            sequences=req.sequences,
            namespace=req.namespace,
        )
        return {"sbol3_document": doc, "num_components": len(req.sequences)}

    async def _search_registry(self, request: dict) -> dict:
        """Search SynBioHub for parts."""
        req = RegistrySearchRequest(**request)
        return await search_synbiohub(
            query=req.query,
            limit=req.limit,
            instance_url=req.registry_url,
            part_type=req.part_type,
        )

    # ------------------------------------------------------------------
    # Pipeline step handlers
    # ------------------------------------------------------------------

    async def _export_sbol_step(self, inputs: dict, params: dict) -> dict:
        """Pipeline step handler for SBOL export."""
        request = {
            "name": inputs["name"],
            "sequences": inputs["sequences"],
            **params,
        }
        result = await self._export_sbol(request)
        return {"document": result["sbol3_document"]}
