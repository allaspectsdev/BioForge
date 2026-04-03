"""Gibson Assembly simulation using pydna."""

from dataclasses import dataclass


@dataclass
class SimulationResult:
    success: bool
    product_length: int = 0
    product_sequence: str = ""
    num_products: int = 0
    error: str = ""


def simulate_gibson(
    fragment_sequences: list[str],
    circular: bool = False,
    min_overlap: int = 15,
) -> SimulationResult:
    """Simulate Gibson Assembly of fragments.

    Uses pydna if available, otherwise performs a simple overlap-based join.
    """
    try:
        from pydna.assembly import Assembly
        from pydna.dseqrecord import Dseqrecord

        fragments = [Dseqrecord(seq) for seq in fragment_sequences]
        asm = Assembly(fragments, limit=min_overlap)

        if circular:
            products = asm.assemble_circular()
        else:
            products = asm.assemble_linear()

        if not products:
            return SimulationResult(success=False, error="No assembly products formed")

        product = products[0]
        return SimulationResult(
            success=True,
            product_length=len(product),
            product_sequence=str(product.seq),
            num_products=len(products),
        )
    except ImportError:
        return _fallback_assembly(fragment_sequences, circular)
    except Exception as e:
        return SimulationResult(success=False, error=str(e))


def _fallback_assembly(
    fragment_sequences: list[str], circular: bool
) -> SimulationResult:
    """Simple overlap-based assembly when pydna is not available."""
    if not fragment_sequences:
        return SimulationResult(success=False, error="No fragments provided")

    assembled = fragment_sequences[0]
    for i in range(1, len(fragment_sequences)):
        frag = fragment_sequences[i]
        # Find the overlap
        best_overlap = 0
        for ol in range(min(len(assembled), len(frag)), 14, -1):
            if assembled[-ol:] == frag[:ol]:
                best_overlap = ol
                break
        if best_overlap < 15:
            return SimulationResult(
                success=False,
                error=f"No sufficient overlap between fragments {i - 1} and {i}",
            )
        assembled = assembled + frag[best_overlap:]

    return SimulationResult(
        success=True,
        product_length=len(assembled),
        product_sequence=assembled,
        num_products=1,
    )
