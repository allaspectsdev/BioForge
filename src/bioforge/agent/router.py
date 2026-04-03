"""RouterAgent that classifies user intent and delegates to domain sub-agents."""

from __future__ import annotations

import logging
import re
from typing import Any

from bioforge.modules.base import ModuleCapability
from bioforge.modules.registry import ModuleRegistry

logger = logging.getLogger(__name__)


# Mapping from domain -> list of capability name prefixes that belong to it
DOMAIN_CAPABILITY_MAP: dict[str, list[str]] = {
    "assembly": [
        "design_assembly",
        "calculate_tm",
        "check_overhang_quality",
        "reverse_complement",
    ],
    "sequence": [
        "blast_search",
        "pairwise_align",
        "multiple_align",
        "import_sbol",
        "export_sbol",
        "search_registry",
    ],
    "pipeline": [],
    "structure": [],
    "variant": [
        "annotate_variants",
        "predict_effects",
        "load_vcf",
    ],
    "experiment": [
        "create_experiment",
        "list_protocols",
        "generate_primer_order",
    ],
}


class RouterAgent:
    """Routes user queries to the appropriate domain sub-agent.

    Uses keyword-based intent classification to determine which domain
    a user query belongs to, then filters the available tool set to
    only those relevant to the classified domain.
    """

    DOMAINS: dict[str, list[str]] = {
        "assembly": [
            "design",
            "gibson",
            "golden gate",
            "codon",
            "fragment",
            "overhang",
            "assembly",
            "clone",
            "cloning",
        ],
        "sequence": [
            "sequence",
            "blast",
            "align",
            "alignment",
            "search",
            "similar",
            "import",
            "fasta",
            "genbank",
        ],
        "pipeline": [
            "pipeline",
            "workflow",
            "run",
            "execute",
            "step",
            "dag",
            "nextflow",
        ],
        "structure": [
            "structure",
            "fold",
            "protein",
            "pdb",
            "alphafold",
            "plddt",
            "3d",
            "tertiary",
        ],
        "variant": [
            "variant",
            "mutation",
            "snp",
            "effect",
            "score",
            "vcf",
            "mutant",
            "substitution",
        ],
        "experiment": [
            "experiment",
            "protocol",
            "primer order",
            "order primers",
            "idt",
            "plate",
            "colony pcr",
        ],
    }

    def __init__(self, registry: ModuleRegistry) -> None:
        self.registry = registry
        self._capabilities: dict[str, ModuleCapability] = {
            cap.name: cap for cap in registry.all_capabilities()
        }

    def classify_intent(self, prompt: str) -> str:
        """Simple keyword-based intent classification.

        Scores each domain by counting keyword matches in the prompt,
        returning the highest-scoring domain. Falls back to "general"
        when no keywords match.
        """
        prompt_lower = prompt.lower()
        scores: dict[str, int] = {}

        for domain, keywords in self.DOMAINS.items():
            score = 0
            for keyword in keywords:
                # Use word boundary matching for single words, substring for multi-word
                if " " in keyword:
                    if keyword in prompt_lower:
                        score += 2  # multi-word matches are stronger signals
                else:
                    if re.search(rf"\b{re.escape(keyword)}\b", prompt_lower):
                        score += 1
            if score > 0:
                scores[domain] = score

        if not scores:
            return "general"

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def get_tools_for_domain(self, domain: str) -> list[dict]:
        """Return only the Anthropic API tool definitions relevant to the classified domain.

        If domain is 'general', returns all tools.
        """
        if domain == "general":
            return self._all_tools()

        # Get the capability names associated with this domain
        cap_names = DOMAIN_CAPABILITY_MAP.get(domain, [])

        tools: list[dict] = []
        for name in cap_names:
            cap = self._capabilities.get(name)
            if cap is not None:
                tools.append(
                    {
                        "name": cap.name,
                        "description": cap.description,
                        "input_schema": cap.input_schema,
                    }
                )

        # If no specific tools found for this domain, return all tools
        if not tools:
            return self._all_tools()

        return tools

    def get_capabilities_for_domain(self, domain: str) -> dict[str, ModuleCapability]:
        """Return capability objects for the domain, suitable for tool execution."""
        if domain == "general":
            return dict(self._capabilities)

        cap_names = DOMAIN_CAPABILITY_MAP.get(domain, [])
        return {
            name: cap
            for name, cap in self._capabilities.items()
            if name in cap_names
        }

    def _all_tools(self) -> list[dict]:
        """Return all available tools as Anthropic API tool defs."""
        return [
            {
                "name": cap.name,
                "description": cap.description,
                "input_schema": cap.input_schema,
            }
            for cap in self._capabilities.values()
        ]
