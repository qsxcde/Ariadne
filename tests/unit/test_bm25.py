"""BM25 ranking contract: tokenisation, IDF smoothing and deterministic ties."""

import pytest

from backend.domain.models import Chunk, ChunkMetadata
from backend.rag.retrieval.bm25 import BM25Retriever, tokenize_for_bm25


def _chunk(
    text: str,
    *,
    paper_id: str = "p1",
    index: int = 0,
    is_reference: bool = False,
    section: str = "1",
) -> Chunk:
    return Chunk(
        text=text,
        metadata=ChunkMetadata(
            paper_id=paper_id,
            section=section,
            chunk_index=index,
            type="paragraph",
            is_reference=is_reference,
        ),
    )


@pytest.mark.unit
def test_tokenizer_keeps_latin_words_numbers_and_cjk_unigrams():
    tokens = tokenize_for_bm25("Sparse attention 2023 版")

    assert "sparse" in tokens
    assert "attention" in tokens
    assert "2023" in tokens
    assert "版" in tokens


@pytest.mark.unit
def test_tokenizer_emits_cjk_bigrams():
    tokens = tokenize_for_bm25("稀疏注意力")

    assert "稀" in tokens
    assert "稀疏" in tokens
    assert "注意" in tokens
    assert "意力" in tokens


@pytest.mark.unit
def test_rare_term_outranks_a_repeated_common_term():
    chunks = [
        _chunk("transformer transformer transformer transformer", index=0),
        _chunk("transformer uses sparse attention", index=1),
        _chunk("unrelated content about graphs", index=2),
    ]

    hits = BM25Retriever(chunks).search("sparse", k=5)

    assert hits[0].chunk.metadata.chunk_index == 1
    assert hits[0].rank == 1


@pytest.mark.unit
def test_reference_chunks_are_excluded_from_default_retrieval():
    chunks = [
        _chunk("sparse attention", index=0),
        _chunk("sparse attention", index=1, is_reference=True),
    ]

    hits = BM25Retriever(chunks).search("sparse", k=5)

    assert [hit.chunk.metadata.chunk_index for hit in hits] == [0]


@pytest.mark.unit
def test_duplicate_paper_chunk_pairs_collapse_to_one_entry():
    chunks = [
        _chunk("sparse attention", index=0),
        _chunk("sparse attention", index=0),
    ]

    assert len(BM25Retriever(chunks).search("sparse", k=5)) == 1


@pytest.mark.unit
def test_ties_break_on_paper_id_then_chunk_index():
    chunks = [
        _chunk("same text", paper_id="p2", index=0),
        _chunk("same text", paper_id="p1", index=3),
        _chunk("same text", paper_id="p1", index=1),
    ]

    hits = BM25Retriever(chunks).search("same", k=5)

    assert [
        (hit.chunk.metadata.paper_id, hit.chunk.metadata.chunk_index) for hit in hits
    ] == [("p1", 1), ("p1", 3), ("p2", 0)]


@pytest.mark.unit
def test_idf_stays_positive_for_terms_present_in_every_document():
    """The ``log(1 + ...)`` smoothing is why this scorer is not BM25Okapi.

    ``rank_bm25.BM25Okapi`` uses ``log(N - df + 0.5) - log(df + 0.5)``, which is
    negative here and gets patched with an epsilon, inverting the contribution
    of very common terms. Swapping implementations would silently reorder
    results, so this test pins the current semantics.
    """
    chunks = [_chunk(f"common term document {index}", index=index) for index in range(5)]

    hits = BM25Retriever(chunks).search("common", k=5)

    assert len(hits) == 5
    assert all(hit.score > 0 for hit in hits)


@pytest.mark.unit
def test_empty_query_or_corpus_returns_nothing():
    assert BM25Retriever([]).search("anything", k=5) == []
    assert BM25Retriever([_chunk("text", index=0)]).search("   ", k=5) == []
    assert BM25Retriever([_chunk("text", index=0)]).search("text", k=0) == []
