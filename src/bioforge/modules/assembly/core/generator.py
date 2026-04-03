"""Generate initial partition candidates."""

import random

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import Partition


def generate_partition(
    sequence_length: int,
    config: AssemblyConfig,
    rng: random.Random | None = None,
) -> Partition:
    """Generate a random valid partition.

    Strategy: place boundaries at approximately equal intervals within
    [min_fragment_bp, max_fragment_bp], then add random jitter.
    """
    if rng is None:
        rng = random.Random()

    min_frag = config.min_fragment_bp
    max_frag = config.max_fragment_bp
    target_frag = (min_frag + max_frag) // 2  # ~2250

    # Estimate number of fragments — need enough to keep each within max_frag
    num_fragments = max(1, -(-sequence_length // max_frag))  # ceil division
    if sequence_length <= max_frag:
        return Partition(
            sequence_length=sequence_length,
            boundaries=[],
            overhang_lengths=[],
        )

    # Place boundaries with jitter
    boundaries = []
    for i in range(1, num_fragments):
        ideal = i * sequence_length // num_fragments
        jitter = rng.randint(-100, 100)
        boundary = max(min_frag, min(sequence_length - min_frag, ideal + jitter))
        boundaries.append(boundary)

    # Remove duplicates and sort
    boundaries = sorted(set(boundaries))

    # Validate fragment lengths, remove boundaries that create invalid fragments
    boundaries = _validate_boundaries(boundaries, sequence_length, config)

    # Generate overhang lengths
    oh_min = config.min_overhang_bp
    oh_max = config.max_overhang_bp
    overhang_lengths = [rng.randint(oh_min, oh_max) for _ in boundaries]

    return Partition(
        sequence_length=sequence_length,
        boundaries=boundaries,
        overhang_lengths=overhang_lengths,
    )


def _validate_boundaries(
    boundaries: list[int],
    sequence_length: int,
    config: AssemblyConfig,
) -> list[int]:
    """Remove boundaries that create fragments outside the valid range."""
    min_frag = config.min_fragment_bp
    max_frag = config.max_fragment_bp

    valid = []
    prev = 0
    for b in boundaries:
        frag_len = b - prev
        remaining = sequence_length - b
        if frag_len >= min_frag and remaining >= min_frag:
            valid.append(b)
            prev = b

    # Check last fragment — only remove if it's too short (too long is fixable by optimizer)
    if valid:
        last_frag = sequence_length - valid[-1]
        if last_frag < min_frag:
            valid.pop()

    return valid
