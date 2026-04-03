"""Embedding storage, similarity search, and clustering powered by Evo 2 + pgvector."""

from __future__ import annotations

import logging
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.modules.evo2.client import BaseEvo2Client, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional sklearn / UMAP imports
# ---------------------------------------------------------------------------

_HAS_SKLEARN = False
try:
    from sklearn.cluster import KMeans  # type: ignore[import-untyped]

    _HAS_SKLEARN = True
except ImportError:
    KMeans = None  # type: ignore[assignment,misc]

_HAS_UMAP = False
try:
    import umap  # type: ignore[import-untyped]

    _HAS_UMAP = True
except ImportError:
    umap = None  # type: ignore[assignment]


class EmbeddingService:
    """High-level operations that combine Evo 2 embeddings with the database.

    Parameters
    ----------
    client : BaseEvo2Client
        An Evo 2 client instance (local, API, or mock).
    """

    def __init__(self, client: BaseEvo2Client) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Embed & store
    # ------------------------------------------------------------------

    async def embed_and_store(
        self,
        sequence_id: UUID,
        sequence: str,
        session: AsyncSession,
    ) -> np.ndarray:
        """Compute the Evo 2 embedding for *sequence* and persist it.

        The embedding is stored in the ``sequences.embedding`` column which
        should be a ``pgvector.vector(1536)`` type.  If the column does not
        exist yet (e.g. before the migration runs), the operation is skipped
        with a warning.

        Returns the embedding vector.
        """
        embedding = await self._client.embed(sequence)

        # Store as a pgvector literal: '[0.1, 0.2, ...]'
        vec_literal = "[" + ",".join(f"{float(v):.8f}" for v in embedding) + "]"
        try:
            await session.execute(
                text(
                    "UPDATE sequences SET embedding = :vec WHERE id = :sid"
                ),
                {"vec": vec_literal, "sid": str(sequence_id)},
            )
            await session.flush()
            logger.debug("Stored embedding for sequence %s", sequence_id)
        except Exception:
            logger.warning(
                "Could not store embedding for sequence %s. "
                "Ensure the 'embedding' column (vector(1536)) exists.",
                sequence_id,
                exc_info=True,
            )

        return embedding

    # ------------------------------------------------------------------
    # Similarity search (pgvector cosine distance)
    # ------------------------------------------------------------------

    async def similarity_search(
        self,
        query_embedding: np.ndarray,
        project_id: UUID,
        top_k: int,
        session: AsyncSession,
    ) -> list[dict]:
        """Find the *top_k* most similar sequences using pgvector ``<=>`` (cosine distance).

        Returns a list of dicts with keys: ``sequence_id``, ``name``, ``distance``, ``score``.
        """
        vec_literal = "[" + ",".join(f"{float(v):.8f}" for v in query_embedding) + "]"

        query = text(
            """
            SELECT id, name, embedding <=> :query_vec AS distance
            FROM sequences
            WHERE project_id = :pid
              AND embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT :topk
            """
        )

        result = await session.execute(
            query,
            {"query_vec": vec_literal, "pid": str(project_id), "topk": top_k},
        )
        rows = result.fetchall()

        return [
            {
                "sequence_id": row[0],
                "name": row[1],
                "distance": float(row[2]),
                "score": 1.0 - float(row[2]),  # cosine distance -> similarity
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    async def cluster_sequences(
        self,
        sequence_ids: list[UUID],
        n_clusters: int,
        session: AsyncSession,
    ) -> dict:
        """Cluster sequences by their embeddings using KMeans.

        Returns a dict with:
        - ``clusters``: mapping of sequence_id (str) -> cluster label (int)
        - ``coordinates``: mapping of sequence_id (str) -> [x, y] (UMAP 2-D projection)
        - ``n_clusters``: actual number of clusters used
        """
        if not _HAS_SKLEARN:
            raise ImportError(
                "scikit-learn is required for clustering. Install with: pip install scikit-learn"
            )

        # Fetch embeddings for the requested sequences
        placeholders = ", ".join(f":id{i}" for i in range(len(sequence_ids)))
        params = {f"id{i}": str(sid) for i, sid in enumerate(sequence_ids)}

        result = await session.execute(
            text(
                f"SELECT id, embedding FROM sequences WHERE id IN ({placeholders}) AND embedding IS NOT NULL"
            ),
            params,
        )
        rows = result.fetchall()

        if len(rows) < 2:
            raise ValueError("Need at least 2 sequences with embeddings to cluster.")

        ids = [str(row[0]) for row in rows]
        # pgvector returns the vector as a string or list depending on driver
        embeddings: list[np.ndarray] = []
        for row in rows:
            raw = row[1]
            if isinstance(raw, str):
                raw = raw.strip("[]")
                vec = np.fromstring(raw, sep=",", dtype=np.float32)
            elif isinstance(raw, (list, tuple)):
                vec = np.asarray(raw, dtype=np.float32)
            else:
                vec = np.asarray(raw, dtype=np.float32)
            embeddings.append(vec)

        X = np.vstack(embeddings)
        actual_k = min(n_clusters, len(ids))

        km = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
        labels = km.fit_predict(X)

        clusters = {sid: int(label) for sid, label in zip(ids, labels)}

        # 2-D projection via UMAP (or fallback to PCA)
        coordinates: dict[str, list[float]] = {}
        if _HAS_UMAP and X.shape[0] >= 4:
            reducer = umap.UMAP(n_components=2, random_state=42)
            coords_2d = reducer.fit_transform(X)
        else:
            # Simple PCA fallback
            mean = X.mean(axis=0)
            X_centered = X - mean
            _, _, Vt = np.linalg.svd(X_centered, full_matrices=False)
            coords_2d = X_centered @ Vt[:2].T

        for i, sid in enumerate(ids):
            coordinates[sid] = [float(coords_2d[i, 0]), float(coords_2d[i, 1])]

        return {
            "clusters": clusters,
            "coordinates": coordinates,
            "n_clusters": actual_k,
        }
