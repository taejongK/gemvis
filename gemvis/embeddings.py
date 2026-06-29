"""Local sentence embeddings for semantic re-ranking in search.

Uses a multilingual sentence-transformer to embed file summaries/tags and
store them alongside the knowledge graph. Embeddings live in a single
numpy .npz file keyed by node ID.
"""

import logging
import threading
from pathlib import Path

import numpy as np

from gemvis.config import EMBEDDINGS_PATH, EMBEDDING_MODEL

logger = logging.getLogger(__name__)


class EmbeddingStore:
    """File node → vector mapping with lazy model load + disk persistence."""

    def __init__(self, path: str | Path | None = None, model_name: str | None = None):
        self.path = Path(path) if path else EMBEDDINGS_PATH
        self.model_name = model_name or EMBEDDING_MODEL
        self._model = None
        self._model_lock = threading.Lock()
        self._ids: list[str] = []
        self._vectors: np.ndarray | None = None  # shape (N, dim)
        self.load()

    # ── model ──────────────────────────────────────────────────────

    def _get_model(self):
        """Lazy-load sentence-transformer (first call blocks ~5s)."""
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading embedding model: %s", self.model_name)
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, text: str) -> np.ndarray:
        """Encode a single text into a normalized vector."""
        model = self._get_model()
        vec = model.encode(text, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32)

    # ── storage ────────────────────────────────────────────────────

    def load(self):
        """Load existing embeddings from disk."""
        if not self.path.exists():
            logger.info("No existing embeddings found at %s", self.path)
            return
        try:
            data = np.load(self.path, allow_pickle=False)
            # Convert numpy strings back to plain str for consistent comparisons
            self._ids = [str(x) for x in data["ids"]]
            self._vectors = data["vectors"].astype(np.float32)
            logger.info("Loaded %d embeddings", len(self._ids))
        except Exception as e:
            logger.error("Failed to load embeddings: %s", e)
            self._ids = []
            self._vectors = None

    def save(self):
        """Persist embeddings to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._ids or self._vectors is None:
            # Remove file if nothing to save
            if self.path.exists():
                self.path.unlink()
            return
        # Use auto-detected unicode dtype (no object arrays → safe to load)
        np.savez(
            self.path,
            ids=np.array(self._ids),
            vectors=self._vectors,
        )

    # ── operations ─────────────────────────────────────────────────

    def add(self, node_id: str, text: str):
        """Add or update an embedding for a node."""
        if not text or not text.strip():
            return
        try:
            vec = self.encode(text)
        except Exception as e:
            logger.error("Failed to encode text for %s: %s", node_id, e)
            return

        if node_id in self._ids:
            idx = self._ids.index(node_id)
            assert self._vectors is not None
            self._vectors[idx] = vec
        else:
            self._ids.append(node_id)
            if self._vectors is None:
                self._vectors = vec.reshape(1, -1)
            else:
                self._vectors = np.vstack([self._vectors, vec.reshape(1, -1)])
        self.save()

    def remove(self, node_id: str):
        """Remove an embedding. Silent no-op if not present."""
        if node_id not in self._ids:
            return
        idx = self._ids.index(node_id)
        self._ids.pop(idx)
        if self._vectors is not None:
            self._vectors = np.delete(self._vectors, idx, axis=0)
            if self._vectors.shape[0] == 0:
                self._vectors = None
        self.save()

    def clear(self):
        """Drop all embeddings."""
        self._ids = []
        self._vectors = None
        self.save()

    def has(self, node_id: str) -> bool:
        return node_id in self._ids

    def count(self) -> int:
        return len(self._ids)

    # ── search ─────────────────────────────────────────────────────

    def score(self, query: str, node_ids: list[str] | None = None) -> dict[str, float]:
        """Return cosine similarity of `query` vs each node's embedding.

        If `node_ids` is provided, only score those IDs (others get 0).
        Returns dict of node_id → score in [-1, 1]. Missing IDs omitted.
        """
        if self._vectors is None or not self._ids or not query.strip():
            return {}
        try:
            qvec = self.encode(query)
        except Exception as e:
            logger.error("Query encode failed: %s", e)
            return {}

        # Normalized vectors → dot product == cosine similarity
        sims = self._vectors @ qvec  # (N,)

        if node_ids is None:
            return {self._ids[i]: float(sims[i]) for i in range(len(self._ids))}

        wanted = set(node_ids)
        return {
            self._ids[i]: float(sims[i])
            for i in range(len(self._ids))
            if self._ids[i] in wanted
        }

    def score_pair(self, source_id: str, target_ids: list[str]) -> dict[str, float]:
        """Return cosine similarity between a stored node and other stored nodes."""
        if self._vectors is None or source_id not in self._ids:
            return {}
        src_idx = self._ids.index(source_id)
        src_vec = self._vectors[src_idx]
        wanted = set(target_ids)
        return {
            self._ids[i]: float(self._vectors[i] @ src_vec)
            for i in range(len(self._ids))
            if self._ids[i] in wanted
        }

    def top_k(self, query: str, k: int = 10, node_ids: list[str] | None = None) -> list[tuple[str, float]]:
        """Return top-k (node_id, score) pairs for the query, highest first."""
        scores = self.score(query, node_ids=node_ids)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:k]
