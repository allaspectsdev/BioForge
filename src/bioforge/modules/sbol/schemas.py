"""Schemas for the SBOL module."""

from pydantic import BaseModel, Field


class SBOLImportRequest(BaseModel):
    """Request to import an SBOL3 document."""

    content: str = Field(description="SBOL3 document content (XML or JSON-LD)")
    format: str = Field(
        default="xml",
        description="Document format: xml or jsonld",
    )
    create_sequences: bool = Field(
        default=True,
        description="Whether to create BioForge sequence records from imported components",
    )


class SBOLExportRequest(BaseModel):
    """Request to export sequences as SBOL3."""

    name: str = Field(description="Name for the SBOL3 document / collection")
    sequences: list[dict] = Field(
        description=(
            "List of sequences to export. Each dict should have: "
            "'name' (str), 'sequence' (str), 'type' (str: DNA, RNA, or protein)"
        ),
    )
    namespace: str = Field(
        default="https://bioforge.local",
        description="Namespace URI for the exported components",
    )
    include_annotations: bool = Field(
        default=True,
        description="Whether to include feature annotations in export",
    )


class RegistrySearchRequest(BaseModel):
    """Request to search a biological parts registry."""

    query: str = Field(description="Search query (keyword, part name, or description)")
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    registry_url: str = Field(
        default="https://synbiohub.org",
        description="SynBioHub instance URL",
    )
    part_type: str = Field(
        default="",
        description=(
            "Optional part type filter: promoter, rbs, cds, terminator, reporter, etc."
        ),
    )


class RegistryPart(BaseModel):
    """A biological part from a registry search."""

    uri: str = Field(description="Unique URI for the part")
    name: str = Field(default="", description="Display name")
    display_id: str = Field(default="", description="Short identifier")
    description: str = Field(default="", description="Part description")
    part_type: str = Field(default="", description="Part type / role")
    sequence: str = Field(default="", description="Sequence if available")
    registry: str = Field(default="", description="Source registry")
