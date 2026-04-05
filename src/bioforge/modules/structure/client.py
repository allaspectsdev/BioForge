"""Structure prediction client with multiple backends.

Supported backends:
  - Boltz-2: MIT-licensed, structure + binding affinity (recommended)
  - OpenFold3: Apache 2.0, AlphaFold3-equivalent
  - ESMFold: DEPRECATED (API shut down 2024, kept for local-only use)
  - Mock: deterministic, for testing

Provides a unified interface for protein structure prediction regardless of
which backend is used.
"""

from __future__ import annotations

import hashlib
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

_HAS_OPENFOLD = False
try:
    import openfold  # type: ignore[import-untyped]

    _HAS_OPENFOLD = True
except ImportError:
    openfold = None  # type: ignore[assignment]

_HAS_BOLTZ = False
try:
    import boltz  # type: ignore[import-untyped]

    _HAS_BOLTZ = True
except ImportError:
    boltz = None  # type: ignore[assignment]

_HAS_HTTPX = False
try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    httpx = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

# ESMFold API was shut down in 2024 — kept only for reference / local deployments
ESMFOLD_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"


@dataclass
class PDBResult:
    """Container for a structure prediction result."""

    pdb_string: str
    plddt_scores: list[float]
    mean_plddt: float
    num_residues: int


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseStructureClient(ABC):
    """Unified interface for protein structure prediction."""

    @abstractmethod
    async def predict_structure(self, sequence: str) -> PDBResult:
        """Predict the 3-D structure of a single protein chain."""
        ...

    @abstractmethod
    async def predict_complex(self, sequences: list[str]) -> PDBResult:
        """Predict the structure of a multi-chain complex."""
        ...


# ---------------------------------------------------------------------------
# Boltz-2 backend (recommended — MIT licensed, structure + binding affinity)
# ---------------------------------------------------------------------------


class BoltzClient(BaseStructureClient):
    """Structure prediction via the Boltz-2 package.

    Boltz-2 is MIT-licensed and provides:
    - AlphaFold3-level accuracy for protein structure prediction
    - Protein-ligand binding affinity prediction
    - Multi-chain complex prediction
    - 1000x faster than FEP for binding affinity

    Requires: pip install boltz
    """

    def __init__(self, device: str = "cuda") -> None:
        if not _HAS_BOLTZ:
            raise ImportError(
                "The 'boltz' package is required for Boltz-2 structure prediction. "
                "Install with: pip install boltz"
            )
        self._device = device
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            logger.info("Loading Boltz-2 model on %s ...", self._device)
            self._model = boltz.Boltz2.load(device=self._device)
            logger.info("Boltz-2 model loaded.")
        return self._model

    async def predict_structure(self, sequence: str) -> PDBResult:
        """Predict structure using Boltz-2."""
        model = self._ensure_model()
        prediction = model.predict(sequence)

        pdb_string: str = prediction.to_pdb()
        plddt_scores: list[float] = prediction.confidence.tolist()
        mean_plddt = sum(plddt_scores) / len(plddt_scores) if plddt_scores else 0.0

        return PDBResult(
            pdb_string=pdb_string,
            plddt_scores=plddt_scores,
            mean_plddt=round(mean_plddt, 2),
            num_residues=len(sequence),
        )

    async def predict_complex(self, sequences: list[str]) -> PDBResult:
        """Predict multi-chain complex using Boltz-2."""
        model = self._ensure_model()
        prediction = model.predict_complex(sequences)

        pdb_string: str = prediction.to_pdb()
        plddt_scores: list[float] = prediction.confidence.tolist()
        mean_plddt = sum(plddt_scores) / len(plddt_scores) if plddt_scores else 0.0

        return PDBResult(
            pdb_string=pdb_string,
            plddt_scores=plddt_scores,
            mean_plddt=round(mean_plddt, 2),
            num_residues=sum(len(s) for s in sequences),
        )


# ---------------------------------------------------------------------------
# ESMFold API backend (DEPRECATED — API shut down 2024)
# ---------------------------------------------------------------------------


class ESMFoldClient(BaseStructureClient):
    """Call the ESM Metagenomic Atlas API for structure prediction.

    DEPRECATED: The public ESMFold API (api.esmatlas.com) was shut down in 2024.
    This client is kept for local ESMFold deployments only. Do not use with
    the default URL in production.
    """

    def __init__(
        self,
        url: str = ESMFOLD_URL,
        timeout: float = 300.0,
    ) -> None:
        if not _HAS_HTTPX:
            raise ImportError(
                "httpx is required for ESMFold API mode. Install with: pip install httpx"
            )
        self._url = url
        self._timeout = timeout

    async def predict_structure(self, sequence: str) -> PDBResult:
        """Predict structure via ESMFold API."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url,
                content=sequence,
                headers={"Content-Type": "text/plain"},
            )
            resp.raise_for_status()

        pdb_string = resp.text
        plddt_scores = self._parse_plddt(pdb_string)
        mean_plddt = sum(plddt_scores) / len(plddt_scores) if plddt_scores else 0.0

        return PDBResult(
            pdb_string=pdb_string,
            plddt_scores=plddt_scores,
            mean_plddt=round(mean_plddt, 2),
            num_residues=len(sequence),
        )

    async def predict_complex(self, sequences: list[str]) -> PDBResult:
        """Predict a complex by submitting chains joined with ':' separator."""
        joined = ":".join(sequences)
        result = await self.predict_structure(joined)
        result.num_residues = sum(len(s) for s in sequences)
        return result

    @staticmethod
    def _parse_plddt(pdb_string: str) -> list[float]:
        """Extract per-residue pLDDT from the B-factor column of CA atoms."""
        seen_residues: dict[tuple[str, int], float] = {}
        for line in pdb_string.splitlines():
            if not line.startswith("ATOM"):
                continue
            atom_name = line[12:16].strip()
            if atom_name != "CA":
                continue
            chain = line[21]
            try:
                res_seq = int(line[22:26].strip())
                bfactor = float(line[60:66].strip())
            except (ValueError, IndexError):
                continue
            key = (chain, res_seq)
            if key not in seen_residues:
                seen_residues[key] = bfactor

        return list(seen_residues.values())


# ---------------------------------------------------------------------------
# Local OpenFold3 backend
# ---------------------------------------------------------------------------


class OpenFoldClient(BaseStructureClient):
    """Run structure prediction locally via the ``openfold`` package."""

    def __init__(self, device: str = "cuda") -> None:
        if not _HAS_OPENFOLD:
            raise ImportError(
                "The 'openfold' package is required for local structure prediction. "
                "Install from: https://github.com/aqlaboratory/openfold"
            )
        self._device = device
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            logger.info("Loading OpenFold3 model on %s ...", self._device)
            self._model = openfold.load_model(device=self._device)
            logger.info("OpenFold3 model loaded.")
        return self._model

    async def predict_structure(self, sequence: str) -> PDBResult:
        """Predict structure locally with OpenFold."""
        model = self._ensure_model()
        prediction = model.predict(sequence)

        pdb_string: str = prediction.to_pdb()
        plddt_scores: list[float] = prediction.plddt.tolist()
        mean_plddt = sum(plddt_scores) / len(plddt_scores) if plddt_scores else 0.0

        return PDBResult(
            pdb_string=pdb_string,
            plddt_scores=plddt_scores,
            mean_plddt=round(mean_plddt, 2),
            num_residues=len(sequence),
        )

    async def predict_complex(self, sequences: list[str]) -> PDBResult:
        """Predict complex locally with OpenFold multi-chain mode."""
        model = self._ensure_model()
        prediction = model.predict_complex(sequences)

        pdb_string: str = prediction.to_pdb()
        plddt_scores: list[float] = prediction.plddt.tolist()
        mean_plddt = sum(plddt_scores) / len(plddt_scores) if plddt_scores else 0.0

        return PDBResult(
            pdb_string=pdb_string,
            plddt_scores=plddt_scores,
            mean_plddt=round(mean_plddt, 2),
            num_residues=sum(len(s) for s in sequences),
        )


# ---------------------------------------------------------------------------
# Mock client (deterministic, for testing)
# ---------------------------------------------------------------------------

_AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


class MockStructureClient(BaseStructureClient):
    """Deterministic mock client for unit testing.

    Generates a synthetic PDB string and fake pLDDT scores derived from the
    sequence hash so that tests are fully deterministic without any external
    service or GPU.
    """

    def _hash_seed(self, text: str) -> int:
        return int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**31)

    def _make_pdb(self, sequence: str, chain_id: str = "A", res_offset: int = 0) -> tuple[str, list[float]]:
        """Build a minimal synthetic PDB string and pLDDT list."""
        rng = random.Random(self._hash_seed(sequence))
        lines: list[str] = []
        plddt_scores: list[float] = []
        atom_serial = 1

        for i, aa in enumerate(sequence, start=1):
            plddt = round(rng.uniform(40.0, 98.0), 2)
            plddt_scores.append(plddt)

            # Simplified: only emit a CA atom per residue
            x = round(rng.uniform(-50.0, 50.0), 3)
            y = round(rng.uniform(-50.0, 50.0), 3)
            z = round(rng.uniform(-50.0, 50.0), 3)
            res_num = i + res_offset

            line = (
                f"ATOM  {atom_serial:>5d}  CA  "
                f"{'ALA':>3s} {chain_id}{res_num:>4d}    "
                f"{x:>8.3f}{y:>8.3f}{z:>8.3f}"
                f"  1.00{plddt:>6.2f}           C  "
            )
            lines.append(line)
            atom_serial += 1

        lines.append("END")
        return "\n".join(lines), plddt_scores

    async def predict_structure(self, sequence: str) -> PDBResult:
        """Return a deterministic mock PDB prediction for a single chain."""
        pdb_string, plddt_scores = self._make_pdb(sequence)
        mean_plddt = sum(plddt_scores) / len(plddt_scores) if plddt_scores else 0.0

        return PDBResult(
            pdb_string=pdb_string,
            plddt_scores=plddt_scores,
            mean_plddt=round(mean_plddt, 2),
            num_residues=len(sequence),
        )

    async def predict_complex(self, sequences: list[str]) -> PDBResult:
        """Return a deterministic mock PDB prediction for a multi-chain complex."""
        all_lines: list[str] = []
        all_plddt: list[float] = []
        chain_labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        res_offset = 0

        for idx, seq in enumerate(sequences):
            chain_id = chain_labels[idx % len(chain_labels)]
            pdb_part, plddt_scores = self._make_pdb(seq, chain_id=chain_id, res_offset=res_offset)
            for line in pdb_part.splitlines():
                if line != "END":
                    all_lines.append(line)
            all_plddt.extend(plddt_scores)
            all_lines.append("TER")
            res_offset += len(seq)

        all_lines.append("END")
        pdb_string = "\n".join(all_lines)
        mean_plddt = sum(all_plddt) / len(all_plddt) if all_plddt else 0.0

        return PDBResult(
            pdb_string=pdb_string,
            plddt_scores=all_plddt,
            mean_plddt=round(mean_plddt, 2),
            num_residues=sum(len(s) for s in sequences),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_structure_client(
    *,
    mode: str = "auto",
    device: str = "cuda",
    esmfold_url: str = ESMFOLD_URL,
    timeout: float = 300.0,
) -> BaseStructureClient:
    """Create the appropriate structure prediction client.

    Parameters
    ----------
    mode : str
        One of ``"boltz"``, ``"openfold"``, ``"esmfold"``, ``"mock"``, or
        ``"auto"`` (default). In *auto* mode the factory tries Boltz-2 first,
        then OpenFold3, and finally the mock client. ESMFold is skipped in
        auto mode since the public API was shut down.
    device : str
        PyTorch device for local backends.
    esmfold_url : str
        Override URL for ESMFold API (for local deployments only).
    timeout : float
        HTTP timeout in seconds.
    """
    if mode == "mock":
        return MockStructureClient()

    if mode == "boltz":
        return BoltzClient(device=device)

    if mode == "esmfold":
        return ESMFoldClient(url=esmfold_url, timeout=timeout)

    if mode == "openfold":
        return OpenFoldClient(device=device)

    # auto: try Boltz-2 first (MIT, best accuracy), then OpenFold3, then mock
    if _HAS_BOLTZ:
        try:
            return BoltzClient(device=device)
        except Exception:
            logger.warning("Boltz-2 client creation failed, trying OpenFold.")

    if _HAS_OPENFOLD:
        try:
            return OpenFoldClient(device=device)
        except Exception:
            logger.warning("OpenFold client creation failed, falling back to mock.")

    logger.info("No structure prediction backend available; using MockStructureClient.")
    return MockStructureClient()
