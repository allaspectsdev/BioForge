"""Agent memory for storing and recalling facts across sessions."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single remembered fact."""

    fact: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""  # e.g. "user", "tool_result", "observation"
    keywords: list[str] = field(default_factory=list)


class AgentMemory:
    """In-memory fact store for agent long-term memory.

    Stores facts per session and supports keyword-based recall.
    A future version will use pgvector for semantic similarity search.
    """

    def __init__(self) -> None:
        self._store: dict[UUID, list[MemoryEntry]] = {}

    def remember(
        self,
        session_id: UUID,
        fact: str,
        source: str = "",
    ) -> MemoryEntry:
        """Store a fact in memory for a given session.

        Automatically extracts keywords from the fact for later recall.
        """
        keywords = self._extract_keywords(fact)
        entry = MemoryEntry(fact=fact, source=source, keywords=keywords)

        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append(entry)

        logger.debug(
            "Remembered fact for session %s: %s (keywords: %s)",
            session_id,
            fact[:80],
            keywords,
        )
        return entry

    def recall(
        self,
        query: str,
        top_k: int = 5,
        session_id: UUID | None = None,
    ) -> list[str]:
        """Recall facts matching the query using keyword overlap scoring.

        If session_id is provided, only search that session's memories.
        Otherwise search all sessions.
        """
        query_keywords = set(self._extract_keywords(query))
        if not query_keywords:
            return []

        candidates: list[tuple[float, MemoryEntry]] = []

        sessions_to_search = (
            [self._store[session_id]]
            if session_id and session_id in self._store
            else self._store.values()
        )

        for entries in sessions_to_search:
            for entry in entries:
                entry_kw = set(entry.keywords)
                if not entry_kw:
                    continue
                # Jaccard-like overlap score
                overlap = len(query_keywords & entry_kw)
                if overlap > 0:
                    score = overlap / len(query_keywords | entry_kw)
                    candidates.append((score, entry))

        # Sort by score descending, take top_k
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [entry.fact for _, entry in candidates[:top_k]]

    def get_all(self, session_id: UUID) -> list[MemoryEntry]:
        """Return all memory entries for a session."""
        return list(self._store.get(session_id, []))

    def clear(self, session_id: UUID) -> None:
        """Clear all memories for a session."""
        self._store.pop(session_id, None)

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract keywords from text by lowercasing, splitting, and filtering stopwords."""
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "need", "dare", "ought",
            "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above", "below",
            "between", "out", "off", "over", "under", "again", "further", "then",
            "once", "here", "there", "when", "where", "why", "how", "all", "each",
            "every", "both", "few", "more", "most", "other", "some", "such", "no",
            "nor", "not", "only", "own", "same", "so", "than", "too", "very",
            "just", "because", "but", "and", "or", "if", "while", "that", "this",
            "it", "its", "i", "my", "me", "we", "our", "you", "your", "he", "she",
            "they", "them", "their", "what", "which", "who", "whom",
        }
        # Split on non-alphanumeric, lowercase, filter short words and stopwords
        words = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return [w for w in words if len(w) > 2 and w not in stopwords]
