"""Deterministic tests for the policy-only retrieval index."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.retrieval import (
    EmbeddingValidationError,
    PolicyRetriever,
    PolicyDocument,
    chunk_policy_documents,
    load_policy_documents,
)


POLICY_DIRECTORY = Path(__file__).resolve().parents[1] / "knowledge_base"
SOURCES = [
    "cancellations.md",
    "damaged_goods.md",
    "defective_products.md",
    "returns.md",
    "shipping.md",
    "wrong_item.md",
]


class SourceEmbedder:
    def __init__(self, dimension: int = 6) -> None:
        self.dimension = dimension
        self.document_calls = 0
        self.query_calls: list[str] = []

    def document_embeddings(self, texts: list[str]) -> np.ndarray:
        self.document_calls += 1
        vectors = []
        for text in texts:
            vector = np.zeros(self.dimension, dtype=np.float32)
            source_index = next(
                index
                for index, name in enumerate(
                    [
                        "Cancellation",
                        "Damaged Goods",
                        "Defective Product",
                        "Returns",
                        "Shipping and Delivery",
                        "Wrong Item",
                    ]
                )
                if name in text
            )
            vector[source_index] = 1
            vectors.append(vector)
        return np.asarray(vectors, dtype=np.float32)

    def query_embedding(self, text: str) -> np.ndarray:
        self.query_calls.append(text)
        vector = np.zeros(self.dimension, dtype=np.float32)
        lowered = text.lower()
        if "damage" in lowered:
            vector[1] = 1
        elif "defect" in lowered:
            vector[2] = 1
        elif "return" in lowered:
            vector[3] = 1
        elif "dispatch" in lowered or "arrive" in lowered:
            vector[4] = 1
        elif "wrong" in lowered or "flavour" in lowered:
            vector[5] = 1
        else:
            vector[0] = 1
        return vector


def build_retriever(tmp_path: Path, embedder: SourceEmbedder, **kwargs) -> PolicyRetriever:
    options = {
        "policy_directory": POLICY_DIRECTORY,
        "cache_path": tmp_path / "policy_index.npz",
        "embedding_model": "test-embedding",
        "embedding_dimension": embedder.dimension,
        "top_k": 2,
    }
    options.update(kwargs)
    return PolicyRetriever(embedder, **options)


def test_all_six_policy_files_load_with_provenance() -> None:
    documents = load_policy_documents(POLICY_DIRECTORY)

    assert [document.source_filename for document in documents] == SOURCES
    assert all(document.title and document.content for document in documents)


def test_rule_aware_chunking_is_deterministic_and_retains_provenance() -> None:
    documents = load_policy_documents(POLICY_DIRECTORY)

    first = chunk_policy_documents(documents)
    second = chunk_policy_documents(documents)

    assert first == second
    assert len(first) == 12
    assert all(chunk.source_filename in SOURCES for chunk in first)
    assert all(chunk.text.startswith("# ") for chunk in first)
    damaged_chunks = [chunk for chunk in first if chunk.source_filename == "damaged_goods.md"]
    assert "₹2,000 or less" in damaged_chunks[0].text
    assert "above ₹2,000" in damaged_chunks[0].text


def test_wrapped_conditions_remain_with_their_numbered_rule() -> None:
    document = PolicyDocument(
        source_filename="example.md",
        title="Example Policy",
        content="# Example Policy\n1. If the parcel is damaged\n   and reported in 7 days, request photos.\n2. Otherwise, wait.",
    )

    chunks = chunk_policy_documents([document])

    assert "If the parcel is damaged\nand reported in 7 days" in chunks[0].text


def test_retrieval_orders_expected_sources_and_uses_stable_ties(tmp_path: Path) -> None:
    embedder = SourceEmbedder()
    retriever = build_retriever(tmp_path, embedder)

    results = retriever.retrieve("My product arrived with damage", top_k=2)

    assert [result.source_filename for result in results] == [
        "damaged_goods.md",
        "damaged_goods.md",
    ]
    assert [result.chunk_id for result in results] == sorted(
        result.chunk_id for result in results
    )
    assert all(result.similarity == pytest.approx(1.0) for result in results)


@pytest.mark.parametrize(
    "query, expected_source",
    [
        ("cancel my order", "cancellations.md"),
        ("damage on arrival", "damaged_goods.md"),
        ("functional defect", "defective_products.md"),
        ("return this item", "returns.md"),
        ("parcel not arrived after dispatch", "shipping.md"),
        ("wrong flavour received", "wrong_item.md"),
    ],
)
def test_controlled_queries_retrieve_expected_policy(
    tmp_path: Path, query: str, expected_source: str
) -> None:
    retriever = build_retriever(tmp_path, SourceEmbedder(), top_k=1)

    assert retriever.retrieve(query)[0].source_filename == expected_source


def test_cache_hit_avoids_reembedding_policy_documents(tmp_path: Path) -> None:
    first_embedder = SourceEmbedder()
    first = build_retriever(tmp_path, first_embedder)
    first.retrieve("damage")

    second_embedder = SourceEmbedder()
    second = build_retriever(tmp_path, second_embedder)
    second.retrieve("damage")

    assert first_embedder.document_calls == 1
    assert second_embedder.document_calls == 0
    assert second_embedder.query_calls == ["damage"]


def test_policy_content_model_and_dimension_changes_invalidate_cache(tmp_path: Path) -> None:
    initial_embedder = SourceEmbedder()
    initial = build_retriever(tmp_path, initial_embedder)
    initial.retrieve("damage")

    model_embedder = SourceEmbedder()
    changed_model = build_retriever(
        tmp_path, model_embedder, embedding_model="another-test-embedding"
    )
    changed_model.retrieve("damage")

    dimension_embedder = SourceEmbedder(dimension=7)
    changed_dimension = build_retriever(tmp_path, dimension_embedder)
    changed_dimension.retrieve("damage")

    changed_policy_directory = tmp_path / "policies"
    changed_policy_directory.mkdir()
    for source in POLICY_DIRECTORY.glob("*.md"):
        content = source.read_text(encoding="utf-8")
        if source.name == "shipping.md":
            content += "\n6. Updated local test policy text.\n"
        (changed_policy_directory / source.name).write_text(content, encoding="utf-8")
    changed_content_embedder = SourceEmbedder()
    changed_content = PolicyRetriever(
        changed_content_embedder,
        policy_directory=changed_policy_directory,
        cache_path=tmp_path / "policy_index.npz",
        embedding_model="test-embedding",
        embedding_dimension=6,
        top_k=2,
    )
    changed_content.retrieve("damage")

    assert model_embedder.document_calls == 1
    assert dimension_embedder.document_calls == 1
    assert changed_content_embedder.document_calls == 1


def test_malformed_cache_rebuilds_and_invalid_embeddings_fail(tmp_path: Path) -> None:
    cache_path = tmp_path / "policy_index.npz"
    cache_path.write_bytes(b"not a NumPy archive")
    embedder = SourceEmbedder()
    retriever = PolicyRetriever(
        embedder,
        policy_directory=POLICY_DIRECTORY,
        cache_path=cache_path,
        embedding_model="test-embedding",
        embedding_dimension=6,
    )
    retriever.retrieve("damage")
    assert embedder.document_calls == 1

    class ZeroEmbedder(SourceEmbedder):
        def document_embeddings(self, texts: list[str]) -> np.ndarray:
            return np.zeros((len(texts), 6), dtype=np.float32)

    with pytest.raises(EmbeddingValidationError):
        build_retriever(tmp_path / "zeros", ZeroEmbedder()).retrieve("damage")

    class WrongDimensionEmbedder(SourceEmbedder):
        def document_embeddings(self, texts: list[str]) -> np.ndarray:
            return np.ones((len(texts), 5), dtype=np.float32)

    with pytest.raises(EmbeddingValidationError):
        build_retriever(tmp_path / "wrong", WrongDimensionEmbedder()).retrieve("damage")
