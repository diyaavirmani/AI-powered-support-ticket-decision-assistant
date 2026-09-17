"""Policy-only local retrieval with cached Gemini embeddings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np
from google import genai
from google.genai import types

from src.config import Settings, get_settings


CHUNKING_VERSION = "rule-aware-v1"
RULES_PER_CHUNK = 3
RULE_OVERLAP = 1
DEFAULT_POLICY_DIRECTORY = Path(__file__).resolve().parents[1] / "knowledge_base"


class RetrievalError(Exception):
    """Base class for controlled retrieval failures."""


class ProviderConfigurationError(RetrievalError):
    pass


class ProviderServiceError(RetrievalError):
    pass


class EmbeddingValidationError(RetrievalError):
    pass


class PolicyLoadError(RetrievalError):
    pass


@dataclass(frozen=True)
class PolicyDocument:
    source_filename: str
    title: str
    content: str


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    source_filename: str
    title: str
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source_filename: str
    text: str
    similarity: float


class Embedder(Protocol):
    def document_embeddings(self, texts: Sequence[str]) -> np.ndarray:
        """Return one embedding per policy chunk."""

    def query_embedding(self, text: str) -> np.ndarray:
        """Return one embedding for an incoming ticket query."""


class GeminiEmbedder:
    """Production adapter for the maintained Google GenAI SDK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            raise ProviderConfigurationError("Gemini embedding configuration is missing")
        self.client = genai.Client(api_key=api_key)

    def document_embeddings(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed(list(texts), "RETRIEVAL_DOCUMENT")

    def query_embedding(self, text: str) -> np.ndarray:
        embeddings = self._embed(text, "RETRIEVAL_QUERY")
        if embeddings.shape[0] != 1:
            raise EmbeddingValidationError("provider returned an unexpected query count")
        return embeddings[0]

    def _embed(self, contents: str | list[str], task_type: str) -> np.ndarray:
        try:
            response = self.client.models.embed_content(
                model=self.settings.gemini_embedding_model,
                contents=contents,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.settings.embedding_dimension,
                ),
            )
            values = [embedding.values for embedding in response.embeddings or []]
        except Exception as exc:
            raise ProviderServiceError("Gemini embedding request failed") from exc
        try:
            return np.asarray(values, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise EmbeddingValidationError("provider returned malformed embeddings") from exc


def load_policy_documents(policy_directory: Path = DEFAULT_POLICY_DIRECTORY) -> list[PolicyDocument]:
    """Load trusted Markdown policies in deterministic filename order."""

    if not policy_directory.is_dir():
        raise PolicyLoadError("policy directory is unavailable")

    documents: list[PolicyDocument] = []
    for path in sorted(policy_directory.glob("*.md"), key=lambda item: item.name):
        try:
            content = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise PolicyLoadError(f"could not read policy {path.name}") from exc
        if not content.strip():
            raise PolicyLoadError(f"policy {path.name} is empty")

        lines = content.splitlines()
        title = next(
            (line.removeprefix("#").strip() for line in lines if line.startswith("#")),
            path.stem.replace("_", " ").title(),
        )
        documents.append(
            PolicyDocument(
                source_filename=path.name,
                title=title,
                content=content,
            )
        )

    if not documents:
        raise PolicyLoadError("no Markdown policy documents were found")
    return documents


def chunk_policy_documents(documents: Sequence[PolicyDocument]) -> list[PolicyChunk]:
    """Group numbered policy rules with a one-rule overlap for continuity."""

    chunks: list[PolicyChunk] = []
    for document in documents:
        rules: list[str] = []
        preamble: list[str] = []
        for line in document.content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if re.match(r"^\d+[.)]\s+", stripped):
                rules.append(stripped)
            elif rules:
                rules[-1] = f"{rules[-1]}\n{stripped}"
            else:
                preamble.append(stripped)
        if preamble:
            rules.insert(0, "\n".join(preamble))
        if not rules:
            raise PolicyLoadError(f"policy {document.source_filename} has no rules")

        step = RULES_PER_CHUNK - RULE_OVERLAP
        for ordinal, start in enumerate(range(0, len(rules), step)):
            selected_rules = rules[start : start + RULES_PER_CHUNK]
            if not selected_rules:
                continue
            chunk_text = f"# {document.title}\n\n" + "\n".join(selected_rules)
            chunk_digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:12]
            chunks.append(
                PolicyChunk(
                    chunk_id=f"{document.source_filename}:{ordinal}:{chunk_digest}",
                    source_filename=document.source_filename,
                    title=document.title,
                    text=chunk_text,
                )
            )
            if start + RULES_PER_CHUNK >= len(rules):
                break
    if not chunks:
        raise PolicyLoadError("policy chunking produced no chunks")
    return chunks


def build_index_fingerprint(
    documents: Sequence[PolicyDocument], *, model: str, dimension: int
) -> str:
    payload = {
        "documents": [
            {"filename": document.source_filename, "content": document.content}
            for document in documents
        ],
        "chunking": {
            "version": CHUNKING_VERSION,
            "rules_per_chunk": RULES_PER_CHUNK,
            "rule_overlap": RULE_OVERLAP,
        },
        "embedding_model": model,
        "embedding_dimension": dimension,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_embeddings(values: np.ndarray, dimension: int) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise EmbeddingValidationError("embedding values are malformed") from exc
    if array.ndim != 2 or array.shape[1] != dimension or array.shape[0] == 0:
        raise EmbeddingValidationError("embedding shape does not match configuration")
    if not np.isfinite(array).all():
        raise EmbeddingValidationError("embeddings contain non-finite values")
    norms = np.linalg.norm(array, axis=1)
    if np.any(norms == 0):
        raise EmbeddingValidationError("embeddings contain zero vectors")
    return array / norms[:, np.newaxis]


class PolicyRetriever:
    """Build or load a trusted policy index and rank it with cosine similarity."""

    def __init__(
        self,
        embedder: Embedder,
        *,
        policy_directory: Path = DEFAULT_POLICY_DIRECTORY,
        cache_path: Path | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
        top_k: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        active_settings = settings or get_settings()
        self.embedder = embedder
        self.policy_directory = policy_directory
        self.cache_path = cache_path or active_settings.rag_index_path
        self.embedding_model = embedding_model or active_settings.gemini_embedding_model
        self.embedding_dimension = embedding_dimension or active_settings.embedding_dimension
        self.top_k = top_k or active_settings.retrieval_top_k
        self._chunks: list[PolicyChunk] | None = None
        self._embeddings: np.ndarray | None = None

    @property
    def chunk_count(self) -> int:
        self._ensure_index()
        return len(self._chunks or [])

    def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        self._ensure_index()
        if not query.strip():
            raise RetrievalError("retrieval query must not be blank")
        query_vector = np.asarray(self.embedder.query_embedding(query), dtype=np.float32)
        if query_vector.ndim != 1:
            raise EmbeddingValidationError("query embedding must be one-dimensional")
        normalized_query = _normalize_embeddings(
            query_vector[np.newaxis, :], self.embedding_dimension
        )[0]
        assert self._embeddings is not None
        assert self._chunks is not None
        scores = self._embeddings @ normalized_query
        count = min(top_k or self.top_k, len(self._chunks))
        ranked_indices = np.argsort(-scores, kind="stable")[:count]
        return [
            RetrievedChunk(
                chunk_id=self._chunks[index].chunk_id,
                source_filename=self._chunks[index].source_filename,
                text=self._chunks[index].text,
                similarity=float(scores[index]),
            )
            for index in ranked_indices
        ]

    def _ensure_index(self) -> None:
        if self._chunks is not None and self._embeddings is not None:
            return
        documents = load_policy_documents(self.policy_directory)
        chunks = chunk_policy_documents(documents)
        fingerprint = build_index_fingerprint(
            documents,
            model=self.embedding_model,
            dimension=self.embedding_dimension,
        )
        cached = self._load_cache(fingerprint, chunks)
        if cached is None:
            raw_embeddings = self.embedder.document_embeddings([chunk.text for chunk in chunks])
            embeddings = _normalize_embeddings(raw_embeddings, self.embedding_dimension)
            self._write_cache(fingerprint, chunks, embeddings)
        else:
            embeddings = cached
        self._chunks = chunks
        self._embeddings = embeddings

    def _load_cache(
        self, fingerprint: str, chunks: Sequence[PolicyChunk]
    ) -> np.ndarray | None:
        if not self.cache_path.is_file():
            return None
        try:
            with np.load(self.cache_path, allow_pickle=False) as cached:
                metadata = json.loads(str(cached["metadata"].item()))
                if metadata != {
                    "fingerprint": fingerprint,
                    "chunk_count": len(chunks),
                    "dimension": self.embedding_dimension,
                }:
                    return None
                chunk_ids = [str(value) for value in cached["chunk_ids"]]
                sources = [str(value) for value in cached["sources"]]
                texts = [str(value) for value in cached["texts"]]
                if chunk_ids != [chunk.chunk_id for chunk in chunks]:
                    return None
                if sources != [chunk.source_filename for chunk in chunks]:
                    return None
                if texts != [chunk.text for chunk in chunks]:
                    return None
                return _normalize_embeddings(cached["embeddings"], self.embedding_dimension)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_cache(
        self, fingerprint: str, chunks: Sequence[PolicyChunk], embeddings: np.ndarray
    ) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = json.dumps(
            {
                "fingerprint": fingerprint,
                "chunk_count": len(chunks),
                "dimension": self.embedding_dimension,
            },
            sort_keys=True,
        )
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".npz", dir=self.cache_path.parent, delete=False
            ) as temporary:
                temporary_path = temporary.name
                np.savez_compressed(
                    temporary,
                    metadata=np.array(metadata),
                    embeddings=embeddings,
                    chunk_ids=np.array([chunk.chunk_id for chunk in chunks]),
                    sources=np.array([chunk.source_filename for chunk in chunks]),
                    texts=np.array([chunk.text for chunk in chunks]),
                )
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.cache_path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
