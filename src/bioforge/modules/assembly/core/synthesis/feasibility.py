"""Synthesis feasibility checker that aggregates results across providers.

Runs feasibility checks against multiple synthesis providers (IDT, Twist,
GenScript) and returns per-fragment results with specific failure reasons
and provider recommendations.
"""

import logging
from dataclasses import dataclass, field

from bioforge.modules.assembly.core.synthesis.providers import (
    FeasibilityResult,
    FeasibilityStatus,
    IDTProvider,
    GenScriptProvider,
    SynthesisProvider,
    TwistProvider,
)

logger = logging.getLogger(__name__)


@dataclass
class FragmentFeasibility:
    """Feasibility results for a single DNA fragment across all providers.

    Attributes:
        fragment_index: Index of the fragment in the assembly.
        fragment_name: Optional name or identifier.
        sequence_length: Length of the fragment in bp.
        gc_content: GC content (fraction 0.0-1.0).
        provider_results: Feasibility result from each provider.
        recommended_provider: The best provider for this fragment.
        is_synthesizable: Whether at least one provider can synthesize it.
    """

    fragment_index: int
    fragment_name: str
    sequence_length: int
    gc_content: float
    provider_results: dict[str, FeasibilityResult] = field(default_factory=dict)
    recommended_provider: str | None = None
    is_synthesizable: bool = False


@dataclass
class BatchFeasibilityResult:
    """Aggregated feasibility results for a batch of fragments.

    Attributes:
        fragments: Per-fragment feasibility results.
        all_feasible: Whether all fragments can be synthesized.
        feasible_count: Number of fragments that can be synthesized.
        infeasible_count: Number of fragments that cannot be synthesized.
        total_estimated_cost_usd: Total estimated cost across recommended
            providers.
    """

    fragments: list[FragmentFeasibility] = field(default_factory=list)
    all_feasible: bool = False
    feasible_count: int = 0
    infeasible_count: int = 0
    total_estimated_cost_usd: float | None = None


class SynthesisFeasibilityChecker:
    """Checks synthesis feasibility across multiple providers.

    Runs all configured providers against each input fragment and
    recommends the best provider based on feasibility, cost, and
    turnaround time.

    Args:
        providers: List of SynthesisProvider instances. If None, uses
            the default set (IDT, Twist, GenScript).
    """

    def __init__(
        self,
        providers: list[SynthesisProvider] | None = None,
    ):
        if providers is None:
            self.providers: list[SynthesisProvider] = [
                IDTProvider(),
                TwistProvider(),
                GenScriptProvider(),
            ]
        else:
            self.providers = providers

    def check_fragment(
        self,
        sequence: str,
        fragment_index: int = 0,
        fragment_name: str = "",
    ) -> FragmentFeasibility:
        """Check a single fragment against all providers.

        Args:
            sequence: DNA sequence to check.
            fragment_index: Index of the fragment.
            fragment_name: Optional name for the fragment.

        Returns:
            FragmentFeasibility with results from all providers.
        """
        from bioforge.modules.assembly.core.models import gc_content as calc_gc

        seq = sequence.upper().replace(" ", "").replace("\n", "")
        provider_results: dict[str, FeasibilityResult] = {}

        for provider in self.providers:
            try:
                result = provider.check_feasibility(seq)
                provider_results[provider.name] = result
            except Exception as e:
                logger.error(
                    "Provider %s failed for fragment %d: %s",
                    provider.name, fragment_index, e,
                )

        # Find recommended provider (cheapest feasible option)
        recommended = None
        best_cost = float("inf")
        is_synthesizable = False

        for name, result in provider_results.items():
            if result.status == FeasibilityStatus.FEASIBLE:
                is_synthesizable = True
                cost = result.estimated_cost_usd or float("inf")
                if cost < best_cost:
                    best_cost = cost
                    recommended = name
            elif result.status == FeasibilityStatus.MARGINAL and not is_synthesizable:
                # Marginal is better than nothing
                cost = result.estimated_cost_usd or float("inf")
                if cost < best_cost:
                    best_cost = cost
                    recommended = name

        return FragmentFeasibility(
            fragment_index=fragment_index,
            fragment_name=fragment_name or f"fragment_{fragment_index}",
            sequence_length=len(seq),
            gc_content=round(calc_gc(seq), 4),
            provider_results=provider_results,
            recommended_provider=recommended,
            is_synthesizable=is_synthesizable,
        )

    def check_batch(
        self,
        sequences: list[str],
        names: list[str] | None = None,
    ) -> BatchFeasibilityResult:
        """Check a batch of fragments against all providers.

        Args:
            sequences: List of DNA sequences to check.
            names: Optional list of fragment names (must match length
                of sequences if provided).

        Returns:
            BatchFeasibilityResult with per-fragment and aggregate results.
        """
        if names and len(names) != len(sequences):
            raise ValueError(
                f"Names list length ({len(names)}) does not match "
                f"sequences list length ({len(sequences)})"
            )

        fragments: list[FragmentFeasibility] = []
        total_cost = 0.0
        feasible_count = 0
        infeasible_count = 0

        for i, seq in enumerate(sequences):
            name = names[i] if names else f"fragment_{i}"
            frag_result = self.check_fragment(seq, fragment_index=i, fragment_name=name)
            fragments.append(frag_result)

            if frag_result.is_synthesizable:
                feasible_count += 1
                # Add cost from recommended provider
                if frag_result.recommended_provider:
                    provider_result = frag_result.provider_results.get(
                        frag_result.recommended_provider
                    )
                    if provider_result and provider_result.estimated_cost_usd:
                        total_cost += provider_result.estimated_cost_usd
            else:
                infeasible_count += 1

        return BatchFeasibilityResult(
            fragments=fragments,
            all_feasible=(infeasible_count == 0),
            feasible_count=feasible_count,
            infeasible_count=infeasible_count,
            total_estimated_cost_usd=round(total_cost, 2) if total_cost > 0 else None,
        )
