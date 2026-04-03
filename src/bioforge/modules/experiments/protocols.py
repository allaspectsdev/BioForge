"""Protocol library with wet-lab protocol templates."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProtocolStep:
    """A single step in a laboratory protocol."""

    step_number: int
    action: str
    details: str
    duration_min: float = 0.0
    temperature_c: float | None = None
    notes: str = ""


@dataclass
class Protocol:
    """A complete laboratory protocol template."""

    id: str
    name: str
    description: str
    steps: list[ProtocolStep]
    references: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [
                {
                    "step": s.step_number,
                    "action": s.action,
                    "details": s.details,
                    "duration_min": s.duration_min,
                    "temperature_c": s.temperature_c,
                    "notes": s.notes,
                }
                for s in self.steps
            ],
            "references": self.references,
            "tags": self.tags,
        }


class ProtocolLibrary:
    """Library of standard molecular biology protocol templates.

    Provides pre-built protocols for common cloning and screening
    workflows, with accurate reagent volumes, temperatures, and times.
    """

    def __init__(self) -> None:
        self._protocols: dict[str, Protocol] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load built-in protocol templates."""
        self._protocols["gibson_assembly_neb_hifi"] = Protocol(
            id="gibson_assembly_neb_hifi",
            name="Gibson Assembly (NEB HiFi)",
            description=(
                "Isothermal assembly using NEB HiFi DNA Assembly Master Mix. "
                "Joins 2-6 overlapping DNA fragments in a single reaction."
            ),
            steps=[
                ProtocolStep(
                    step_number=1,
                    action="Linearize backbone",
                    details=(
                        "Digest destination vector with restriction enzyme or PCR amplify "
                        "with primers that exclude the insert region. Gel verify linearization."
                    ),
                    duration_min=60,
                    temperature_c=37.0,
                ),
                ProtocolStep(
                    step_number=2,
                    action="Purify fragments",
                    details=(
                        "Gel extract backbone (if digested) or PCR cleanup all fragments. "
                        "Use Monarch PCR & DNA Cleanup Kit. Elute in 20 uL water. "
                        "Quantify by Nanodrop (aim for >20 ng/uL)."
                    ),
                    duration_min=30,
                ),
                ProtocolStep(
                    step_number=3,
                    action="Set up HiFi reaction",
                    details=(
                        "On ice: combine fragments at 1:2 insert:vector molar ratio "
                        "(50-100 ng vector, 2-3x molar excess of each insert). "
                        "Add 10 uL NEB HiFi DNA Assembly Master Mix (2X). "
                        "Bring total volume to 20 uL with nuclease-free water."
                    ),
                    temperature_c=0.0,
                    duration_min=5,
                ),
                ProtocolStep(
                    step_number=4,
                    action="Incubate at 50C for 15 min",
                    details=(
                        "Place reaction in thermocycler at 50C. "
                        "Use 15 min for 2-3 fragments, 60 min for 4-6 fragments. "
                        "Do not exceed 60 min."
                    ),
                    temperature_c=50.0,
                    duration_min=15,
                ),
                ProtocolStep(
                    step_number=5,
                    action="Transform DH5-alpha competent cells",
                    details=(
                        "Add 2 uL assembly reaction to 50 uL NEB 5-alpha competent cells "
                        "(thawed on ice). Flick tube gently to mix. "
                        "Incubate on ice 30 min. Heat shock at 42C for exactly 30 seconds. "
                        "Return to ice for 2 minutes."
                    ),
                    duration_min=35,
                ),
                ProtocolStep(
                    step_number=6,
                    action="Plate on selective media",
                    details=(
                        "Add 950 uL SOC medium. Shake at 37C, 250 rpm for 60 min. "
                        "Spread 100 uL on pre-warmed LB + antibiotic plates. "
                        "Incubate at 37C overnight (16-18 hours)."
                    ),
                    temperature_c=37.0,
                    duration_min=60,
                ),
                ProtocolStep(
                    step_number=7,
                    action="Colony PCR verification",
                    details=(
                        "Pick 8-12 colonies with sterile tips. Resuspend each in 20 uL "
                        "water. Use 1 uL as template for colony PCR with verification "
                        "primers spanning at least one junction."
                    ),
                    duration_min=90,
                ),
            ],
            references=[
                "Gibson et al., Nature Methods 6:343-345 (2009)",
                "NEB HiFi DNA Assembly Protocol (E2621)",
            ],
            tags=["gibson", "assembly", "cloning", "isothermal"],
        )

        self._protocols["golden_gate_bsai"] = Protocol(
            id="golden_gate_bsai",
            name="Golden Gate Assembly (BsaI)",
            description=(
                "Type IIS restriction enzyme-based assembly using BsaI-HFv2. "
                "Highly efficient for multi-part assemblies with 4-bp overhangs."
            ),
            steps=[
                ProtocolStep(
                    step_number=1,
                    action="Mix parts with BsaI and T4 ligase",
                    details=(
                        "On ice: 75 ng each part + 75 ng destination vector + "
                        "1 uL BsaI-HFv2 (20 U/uL) + 1 uL T4 DNA Ligase (400 U/uL) + "
                        "2 uL 10X T4 DNA Ligase Buffer. Bring to 20 uL with water."
                    ),
                    temperature_c=0.0,
                    duration_min=5,
                ),
                ProtocolStep(
                    step_number=2,
                    action="Thermocycle (37C/5min, 16C/5min) x 30 cycles",
                    details=(
                        "Run thermocycler program: (37C 5 min, 16C 5 min) x 30 cycles. "
                        "The cycling alternates between cutting (37C) and ligation (16C). "
                        "Total time: approximately 5 hours."
                    ),
                    duration_min=300,
                ),
                ProtocolStep(
                    step_number=3,
                    action="Final digest at 60C for 5 min",
                    details=(
                        "After cycling, incubate at 60C for 5 min to heat-inactivate "
                        "enzymes and ensure all BsaI sites are fully cleaved."
                    ),
                    temperature_c=60.0,
                    duration_min=5,
                ),
                ProtocolStep(
                    step_number=4,
                    action="Transform competent cells",
                    details=(
                        "Add 5 uL reaction to 50 uL chemically competent cells. "
                        "Standard heat shock transformation protocol."
                    ),
                    duration_min=35,
                ),
                ProtocolStep(
                    step_number=5,
                    action="Plate on selective media",
                    details=(
                        "Plate on LB + appropriate antibiotic. If destination vector "
                        "has lacZ for blue/white screening, add X-gal and IPTG."
                    ),
                    temperature_c=37.0,
                    duration_min=5,
                ),
                ProtocolStep(
                    step_number=6,
                    action="Screen positive clones",
                    details=(
                        "Pick white colonies (if blue/white screening available). "
                        "Verify by colony PCR with primers flanking the assembly region, "
                        "or by restriction digest of miniprepped DNA."
                    ),
                    duration_min=120,
                ),
            ],
            references=[
                "Engler et al., PLoS ONE 3:e3647 (2008)",
                "NEB Golden Gate Assembly Protocol (E1601)",
            ],
            tags=["golden_gate", "assembly", "bsai", "type_iis", "cloning"],
        )

        self._protocols["colony_pcr"] = Protocol(
            id="colony_pcr",
            name="Colony PCR Verification",
            description=(
                "Rapid PCR-based screening of bacterial colonies to verify "
                "successful cloning without miniprep."
            ),
            steps=[
                ProtocolStep(
                    step_number=1,
                    action="Pick colonies and resuspend in water",
                    details=(
                        "Using sterile pipette tips, touch individual colonies and "
                        "resuspend each in 20 uL nuclease-free water in PCR strip tubes. "
                        "Also streak the same tip on a numbered grid plate for later use."
                    ),
                    duration_min=10,
                ),
                ProtocolStep(
                    step_number=2,
                    action="Set up PCR with verification primers",
                    details=(
                        "Per reaction: 1 uL colony suspension + 12.5 uL 2X OneTaq Master Mix + "
                        "0.5 uL forward primer (10 uM) + 0.5 uL reverse primer (10 uM) + "
                        "10.5 uL water = 25 uL total. Use primers spanning at least one "
                        "cloning junction."
                    ),
                    duration_min=10,
                ),
                ProtocolStep(
                    step_number=3,
                    action="Run PCR thermocycler program",
                    details=(
                        "95C 5 min initial denaturation (also lyses cells), then "
                        "30 cycles of (95C 30s, 55C 30s, 72C 1 min per kb expected product), "
                        "then 72C 5 min final extension. Hold at 4C."
                    ),
                    duration_min=90,
                ),
                ProtocolStep(
                    step_number=4,
                    action="Run gel electrophoresis",
                    details=(
                        "Load 5 uL of each reaction + 1 uL 6X loading dye on 1% agarose gel "
                        "with 1X TAE buffer. Include DNA ladder. Run at 120V for 30 min."
                    ),
                    duration_min=35,
                ),
                ProtocolStep(
                    step_number=5,
                    action="Image gel and analyze results",
                    details=(
                        "Image gel under UV or blue light. Compare band sizes to expected "
                        "product length. Positive clones show a band at the expected size. "
                        "Send positive clones for Sanger sequencing to confirm."
                    ),
                    duration_min=10,
                ),
            ],
            references=["Sambrook & Russell, Molecular Cloning, 4th Ed."],
            tags=["pcr", "screening", "verification", "colony"],
        )

    def list_protocols(self) -> list[dict]:
        """Return summary info for all available protocols."""
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "num_steps": len(p.steps),
                "tags": p.tags,
            }
            for p in self._protocols.values()
        ]

    def get_protocol(self, protocol_id: str) -> Protocol | None:
        """Get a protocol by its ID."""
        return self._protocols.get(protocol_id)

    def get_protocol_dict(self, protocol_id: str) -> dict | None:
        """Get a protocol as a plain dict, or None if not found."""
        p = self._protocols.get(protocol_id)
        return p.to_dict() if p else None

    def add_protocol(self, protocol: Protocol) -> None:
        """Add or replace a protocol in the library."""
        self._protocols[protocol.id] = protocol

    def available_ids(self) -> list[str]:
        """Return all available protocol IDs."""
        return list(self._protocols.keys())
