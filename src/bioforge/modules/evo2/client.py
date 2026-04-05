"""Evo 2 client with dual backends: local model and Together AI API.

Provides a unified interface for embedding, variant scoring, and sequence
generation regardless of whether the Evo 2 model runs locally or via API.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

_HAS_EVO2 = False
try:
    import evo2 as _evo2_lib  # type: ignore[import-untyped]

    _HAS_EVO2 = True
except ImportError:
    _evo2_lib = None

_HAS_TOGETHER = False
try:
    import together  # type: ignore[import-untyped]

    _HAS_TOGETHER = True
except ImportError:
    together = None  # type: ignore[assignment]

_HAS_HTTPX = False
try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    httpx = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 1536
TOGETHER_EVO2_MODEL = "togethercomputer/evo-2-7b"
VALID_BASES = set("ATCGN")

# Available Evo 2 model sizes (Arc Institute, published in Nature March 2026)
EVO2_MODELS = {
    "evo2_1b": {"params": "1B", "context": "8K bp", "description": "Smallest, fastest"},
    "evo2_7b": {"params": "7B", "context": "1M bp", "description": "Good balance of speed and quality"},
    "evo2_20b": {"params": "20B", "context": "1M bp", "description": "40B-level quality at 2x speed (recommended)"},
    "evo2_40b": {"params": "40B", "context": "1M bp", "description": "Flagship, highest quality, requires Hopper GPU"},
}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseEvo2Client(ABC):
    """Unified interface for Evo 2 operations."""

    @abstractmethod
    async def embed(self, sequence: str) -> np.ndarray:
        """Return an embedding vector (1536-dim) for the given nucleotide sequence."""
        ...

    @abstractmethod
    async def score_variants(
        self,
        sequence: str,
        mutations: list[tuple[int, str, str]],
    ) -> list[float]:
        """Score variant effects.

        Each mutation is *(position, ref_base, alt_base)*.
        Returns a list of delta log-likelihood scores (one per mutation).
        Negative scores indicate deleterious changes.
        """
        ...

    @abstractmethod
    async def generate(self, prompt_sequence: str, max_length: int = 100) -> str:
        """Continue / generate a nucleotide sequence from *prompt_sequence*."""
        ...


# ---------------------------------------------------------------------------
# Local (GPU) backend
# ---------------------------------------------------------------------------


class LocalEvo2Client(BaseEvo2Client):
    """Run Evo 2 locally via the ``evo2`` Python package."""

    def __init__(self, model_name: str = "evo2_7b", device: str = "cuda") -> None:
        if not _HAS_EVO2:
            raise ImportError(
                "The 'evo2' package is required for local inference. "
                "Install it with: pip install evo2"
            )
        self._model_name = model_name
        self._device = device
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            logger.info("Loading Evo 2 model '%s' on %s ...", self._model_name, self._device)
            self._model = _evo2_lib.Evo2(self._model_name, device=self._device)
            logger.info("Evo 2 model loaded.")
        return self._model

    async def embed(self, sequence: str) -> np.ndarray:
        """Compute an embedding from the local Evo 2 model."""
        model = self._ensure_model()
        # Evo 2's embed API returns per-token embeddings; we mean-pool them.
        raw = model.embed(sequence)
        if hasattr(raw, "numpy"):
            raw = raw.numpy()
        raw = np.asarray(raw, dtype=np.float32)
        if raw.ndim == 2:
            pooled = raw.mean(axis=0)
        else:
            pooled = raw
        # Project / truncate to EMBEDDING_DIM
        if pooled.shape[0] > EMBEDDING_DIM:
            pooled = pooled[:EMBEDDING_DIM]
        elif pooled.shape[0] < EMBEDDING_DIM:
            pooled = np.pad(pooled, (0, EMBEDDING_DIM - pooled.shape[0]))
        return pooled.astype(np.float32)

    async def score_variants(
        self,
        sequence: str,
        mutations: list[tuple[int, str, str]],
    ) -> list[float]:
        """Score variants by computing delta log-likelihoods locally."""
        model = self._ensure_model()
        ref_ll = float(model.score(sequence))

        scores: list[float] = []
        for pos, ref_base, alt_base in mutations:
            mutant = sequence[:pos] + alt_base + sequence[pos + 1 :]
            mut_ll = float(model.score(mutant))
            scores.append(mut_ll - ref_ll)
        return scores

    async def generate(self, prompt_sequence: str, max_length: int = 100) -> str:
        """Generate nucleotide sequence from a prompt using the local model."""
        model = self._ensure_model()
        result = model.generate(prompt_sequence, max_tokens=max_length)
        return str(result)


# ---------------------------------------------------------------------------
# Together AI API backend
# ---------------------------------------------------------------------------


class TogetherEvo2Client(BaseEvo2Client):
    """Call Evo 2 hosted on the Together AI platform."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = TOGETHER_EVO2_MODEL,
        base_url: str = "https://api.together.xyz/v1",
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        if _HAS_TOGETHER and api_key:
            together.api_key = api_key
            self._use_sdk = True
        elif _HAS_HTTPX:
            self._use_sdk = False
            self._api_key = api_key or ""
        else:
            raise ImportError(
                "Either the 'together' SDK or 'httpx' is required for API mode. "
                "Install one with: pip install together  OR  pip install httpx"
            )

    # -- helpers --

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict) -> dict:
        """Make a POST request via httpx."""
        if httpx is None:
            raise RuntimeError("httpx is not installed")
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}{path}",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # -- public API --

    async def embed(self, sequence: str) -> np.ndarray:
        """Get an embedding via Together AI's embedding endpoint."""
        if self._use_sdk:
            resp = together.Embeddings.create(
                model=self._model,
                input=sequence,
            )
            vec = resp.data[0].embedding  # type: ignore[union-attr]
        else:
            data = await self._post(
                "/embeddings",
                {"model": self._model, "input": sequence},
            )
            vec = data["data"][0]["embedding"]

        arr = np.asarray(vec, dtype=np.float32)
        if arr.shape[0] > EMBEDDING_DIM:
            arr = arr[:EMBEDDING_DIM]
        elif arr.shape[0] < EMBEDDING_DIM:
            arr = np.pad(arr, (0, EMBEDDING_DIM - arr.shape[0]))
        return arr

    async def score_variants(
        self,
        sequence: str,
        mutations: list[tuple[int, str, str]],
    ) -> list[float]:
        """Score variants using embedding-space distance as a proxy.

        Without direct log-likelihood access via the embedding API, this
        measures cosine distance between reference and mutant embeddings.
        Larger negative values indicate the variant causes a bigger shift
        in the model's learned representation. This is a proxy metric —
        not equivalent to true log-likelihood ratios from the full model.
        """
        ref_embedding = await self.embed(sequence)
        scores: list[float] = []
        for pos, _ref_base, alt_base in mutations:
            mutant = sequence[:pos] + alt_base + sequence[pos + 1 :]
            mut_embedding = await self.embed(mutant)
            cos_sim = float(
                np.dot(ref_embedding, mut_embedding)
                / (np.linalg.norm(ref_embedding) * np.linalg.norm(mut_embedding) + 1e-9)
            )
            scores.append(cos_sim - 1.0)  # 0 = no change, negative = larger shift
        return scores

    async def generate(self, prompt_sequence: str, max_length: int = 100) -> str:
        """Generate a continuation via the Together completions endpoint."""
        if self._use_sdk:
            resp = together.Complete.create(
                model=self._model,
                prompt=prompt_sequence,
                max_tokens=max_length,
                temperature=0.7,
            )
            return resp.choices[0].text  # type: ignore[union-attr]

        data = await self._post(
            "/completions",
            {
                "model": self._model,
                "prompt": prompt_sequence,
                "max_tokens": max_length,
                "temperature": 0.7,
            },
        )
        return data["choices"][0]["text"]


# ---------------------------------------------------------------------------
# Mock client (deterministic, for testing)
# ---------------------------------------------------------------------------


class MockEvo2Client(BaseEvo2Client):
    """Deterministic mock client for unit testing.

    Produces repeatable embeddings and scores derived from hashing the input
    sequences so that tests are fully deterministic without a GPU or API key.
    """

    def _hash_seed(self, text: str) -> int:
        return int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**31)

    async def embed(self, sequence: str) -> np.ndarray:
        """Return a deterministic 1536-dim embedding based on the sequence hash."""
        rng = np.random.RandomState(self._hash_seed(sequence))
        vec = rng.randn(EMBEDDING_DIM).astype(np.float32)
        # L2-normalize
        vec /= np.linalg.norm(vec) + 1e-9
        return vec

    async def score_variants(
        self,
        sequence: str,
        mutations: list[tuple[int, str, str]],
    ) -> list[float]:
        """Return deterministic delta-LL scores for each mutation."""
        scores: list[float] = []
        for pos, ref_base, alt_base in mutations:
            key = f"{sequence}:{pos}:{ref_base}>{alt_base}"
            rng = np.random.RandomState(self._hash_seed(key))
            # Scores in [-2, 2] range (most near zero)
            scores.append(float(rng.normal(0.0, 0.5)))
        return scores

    async def generate(self, prompt_sequence: str, max_length: int = 100) -> str:
        """Return a deterministic pseudo-random nucleotide continuation."""
        rng = np.random.RandomState(self._hash_seed(prompt_sequence))
        bases = list("ATCG")
        return "".join(bases[i] for i in rng.randint(0, 4, size=max_length))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_evo2_client(
    *,
    mode: str = "auto",
    api_key: str | None = None,
    model: str = TOGETHER_EVO2_MODEL,
    device: str = "cuda",
) -> BaseEvo2Client:
    """Create the appropriate Evo 2 client.

    Parameters
    ----------
    mode : str
        One of ``"local"``, ``"api"``, ``"mock"``, or ``"auto"`` (default).
        In *auto* mode the factory tries local first, then API, and finally
        falls back to the mock client.
    api_key : str, optional
        Together AI API key (only used in api mode).
    model : str
        Model identifier for Together AI.
    device : str
        PyTorch device string for local mode.
    """
    if mode == "mock":
        return MockEvo2Client()

    if mode == "local":
        return LocalEvo2Client(model_name=model.split("/")[-1], device=device)

    if mode == "api":
        return TogetherEvo2Client(api_key=api_key, model=model)

    # auto
    if _HAS_EVO2:
        try:
            return LocalEvo2Client(device=device)
        except Exception:
            logger.warning("Local Evo 2 unavailable, trying API mode.")

    if api_key and (_HAS_TOGETHER or _HAS_HTTPX):
        try:
            return TogetherEvo2Client(api_key=api_key, model=model)
        except Exception:
            logger.warning("Together API unavailable, falling back to mock.")

    logger.info("No Evo 2 backend available; using MockEvo2Client.")
    return MockEvo2Client()
