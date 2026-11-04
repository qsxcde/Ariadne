"""Real arXiv-abstract corpus evaluation with the local model.

Run with the local Ollama env exported (see scripts/run_local_llm_eval.sh).
This uses 10 real arXiv papers (titles/authors/abstracts), not synthetic text.
"""

import json
import os
import re
from collections import Counter
from pathlib import Path

from backend import composition
from backend.application.follow.feed import ArxivFeedSource
from backend.application.synthesis.service import compare_papers
from backend.domain.models import Chunk, ChunkMetadata
from backend.rag.answer import AnswerPolicy, RetrievalOptions, stream_answer
from backend.adapters.vector.faiss_store import FAISSVectorStore
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.schema import init_db

STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
    "our", "using", "based", "paper", "papers", "study", "results", "approach",
    "method", "methods", "which", "these", "their", "have", "has", "into",
}


def _keywords(text: str, start: int, end: int) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z-]{3,}", text.lower())
    counts = Counter(word for word in words if word not in STOP)
    top = [word for word, _ in counts.most_common(12)]
    return top[start:end] or top[:4]


CACHE_PATH = Path(os.getenv("REAL_PAPER_CACHE", "/tmp/scipal_real_papers.json"))


def _fetch_real_items(count: int) -> list[dict]:
    """Reuse a cached arXiv snapshot so evaluation runs are reproducible offline."""
    if CACHE_PATH.exists():
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if len(cached) >= count:
            return cached
    items = ArxivFeedSource().fetch(
        {"value": "retrieval augmented generation", "kind": "keyword"}
    )
    CACHE_PATH.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return items


def _seed_real_papers(count: int = 10, cases_per_paper: int = 5):
    items = _fetch_real_items(count)
    if len(items) < count:
        raise RuntimeError(f"Expected {count} papers, got {len(items)}")
    chunks: list[Chunk] = []
    paper_ids: list[str] = []
    cases: list[tuple[str, list[str], str]] = []
    papers: list[dict[str, str]] = []
    for item in items[:count]:
        title = str(item["title"])
        authors = json.loads(item.get("authors_json") or "[]")
        abstract = str(item.get("abstract") or "")
        url = str(item.get("url") or "")
        arxiv_id = str(item.get("external_id") or "").rsplit("/", 1)[-1]
        session = session_repo.create_session(title, user_id="u1")
        document = document_repo.create_document(
            session_id=session["id"],
            filename=title[:40] + ".pdf",
            file_path="/tmp/real-paper.pdf",
            mime_type="application/pdf",
            file_size=10,
        )
        paper_repo.update_paper_metadata(
            document["paper_id"],
            title=title,
            authors_json=json.dumps(authors, ensure_ascii=False),
            abstract=abstract,
            url=url,
            arxiv_id=arxiv_id,
        )
        text = f"Title: {title}\nAuthors: {', '.join(authors)}\narXiv ID: {arxiv_id}\nAbstract: {abstract}\nURL: {url}"
        chunk_repo.insert_chunks(
            session["id"],
            document["id"],
            [
                Chunk(
                    text=text,
                    metadata=ChunkMetadata(
                        paper_id=document["id"],
                        section="Abstract",
                        section_path=["Abstract"],
                        chunk_index=0,
                        type="abstract",
                    ),
                )
            ],
        )
        chunks.append(
            Chunk(
                text=text,
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="Abstract",
                    section_path=["Abstract"],
                    chunk_index=0,
                    type="abstract",
                ),
            )
        )
        paper_ids.append(document["paper_id"])
        first_author = (authors[0] if authors else "").split()[-1]
        papers.append(
            {
                "document_id": document["id"],
                "arxiv_id": arxiv_id,
                "title": title,
                "author": authors[0] if authors else "",
                # 名字判断题按姓氏判定：本地模型常只答姓，不接受会被误判为错误。
                "author_key": (authors[0].split()[-1] if authors else ""),
            }
        )
        suffix = " Answer with the exact metadata text."
        cases.append((f"Who is the first author of arXiv paper {arxiv_id}?{suffix}", [first_author], document["id"]))
        cases.append((f"What is the arXiv id of the paper authored by {first_author}?{suffix}", [arxiv_id], document["id"]))
        cases.append((f"Which arXiv id belongs to the paper whose first author is {first_author}?{suffix}", [arxiv_id], document["id"]))
        if cases_per_paper >= 4:
            cases.append((f"Who is the first author of the paper titled {title[:80]}?{suffix}", [first_author], document["id"]))
        if cases_per_paper >= 5:
            cases.append((f"Return the arXiv id for the paper with first author {first_author}.{suffix}", [arxiv_id], document["id"]))
    return chunks, paper_ids, cases, papers


def main() -> None:
    db_path = "/tmp/scipal_real_paper_eval.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    from backend import config
    config.settings.scipal_db_path = db_path
    init_db()

    cases_per_paper = int(os.getenv("REAL_CASES_PER_PAPER", "5"))
    chunks, paper_ids, cases, papers = _seed_real_papers(10, cases_per_paper)
    store = FAISSVectorStore(embed_fn=composition.embedder(), embedding_dim=768)
    store.add_chunks(chunks)
    policy = AnswerPolicy(empty_retrieval_message="没有相关信息", invalid_citation_message="引用无效")
    base_options = dict(
        strategy="hybrid",
        bm25_top_k=8,
        dense_top_k=8,
        seed_top_k=8,
        max_expanded_chunks=8,
        same_section_window=0,
        adjacent_window=0,
        include_linked_blocks=False,
        enable_reranker=False,
        history_rewrite_enabled=False,
        term_expand_enabled=False,
    )

    correct = 0
    cited = 0
    skip_qa = os.getenv("REAL_SKIP_QA") == "1"
    for index, (question, expected_terms, document_id) in enumerate(cases, start=1):
        if skip_qa:
            break
        options = RetrievalOptions(document_ids=[document_id], **base_options)
        answer = ""
        for event in stream_answer(store, question, policy=policy, options=options):
            if event["type"] == "token":
                answer += event["value"]
        lowered = answer.lower()
        hit = any(term.lower() in lowered for term in expected_terms if term)
        if hit:
            correct += 1
        else:
            print(f"MISS Q={question!r} EXPECT={expected_terms!r} A={answer[:160]!r}", flush=True)
        if "[Section:" in answer:
            cited += 1
        if index % 5 == 0:
            print(f"progress {index}/{len(cases)}", flush=True)
    if skip_qa:
        print("REAL_CORPUS_QA skipped", flush=True)
    else:
        print(
            f"REAL_CORPUS_QA correct={correct}/{len(cases)} cited={cited}/{len(cases)}",
            flush=True,
        )

    def answer(
        question: str,
        history: list[dict[str, str]] | None = None,
        document_id: str | None = None,
    ) -> str:
        options = RetrievalOptions(**base_options)
        if document_id:
            options.document_ids = [document_id]
        text = ""
        for event in stream_answer(
            store,
            question,
            policy=policy,
            options=options,
            history=history,
        ):
            if event["type"] == "token":
                text += event["value"]
        return text

    if os.getenv("REAL_SKIP_EXTRA") != "1":
        multi_correct = 0
        multi_total = 0
        for paper in papers:
            scenarios = [
                (
                    f"Who is the first author of arXiv paper {paper['arxiv_id']}? "
                    "Answer with the name only.",
                    "What is the arXiv ID of the paper written by that author? "
                    "Answer with the ID only.",
                    paper["arxiv_id"],
                ),
                (
                    f"What is the arXiv ID of the paper titled {paper['title'][:60]}? "
                    "Answer with the ID only.",
                    "Who is the first author of that paper? Answer with the name only.",
                    paper["author_key"],
                ),
            ]
            for first_q, follow_q, expected in scenarios:
                multi_total += 1
                first_a = answer(first_q, document_id=paper["document_id"])
                follow_a = answer(
                    follow_q,
                    document_id=paper["document_id"],
                    history=[
                        {"role": "user", "content": first_q},
                        {"role": "assistant", "content": first_a},
                    ],
                )
                if expected.lower() in follow_a.lower():
                    multi_correct += 1
                else:
                    print(
                        f"MULTITURN MISS expected={expected!r} A={follow_a[:160]!r}",
                        flush=True,
                    )
                if multi_total % 5 == 0:
                    print(
                        f"multiturn progress {multi_total}", flush=True
                    )
        print(
            f"REAL_CORPUS_MULTITURN correct={multi_correct}/{multi_total}",
            flush=True,
        )

        cross_correct = 0
        cross_total = 0
        for paper in papers:
            probes = [
                (
                    f"Which paper was written by {paper['author']}? "
                    "Answer with its arXiv ID.",
                    paper["arxiv_id"],
                ),
                (
                    f"What is the arXiv ID of the paper titled {paper['title'][:70]}? "
                    "Answer with the ID only.",
                    paper["arxiv_id"],
                ),
                (
                    f"Who is the first author of arXiv paper {paper['arxiv_id']}? "
                    "Answer with the name only.",
                    paper["author_key"],
                ),
            ]
            for question, expected in probes:
                cross_total += 1
                reply = answer(question)
                if expected.lower() in reply.lower():
                    cross_correct += 1
                else:
                    print(
                        f"CROSS MISS expected={expected!r} A={reply[:160]!r}",
                        flush=True,
                    )
                if cross_total % 5 == 0:
                    print(f"cross progress {cross_total}", flush=True)
        print(f"REAL_CORPUS_CROSS correct={cross_correct}/{cross_total}", flush=True)

    if os.getenv("REAL_SKIP_COMPARE") != "1":
        collection = collection_repo.create_collection(user_id="u1", name="Real papers")
        for paper_id in paper_ids:
            collection_repo.add_paper_to_collection(collection["id"], paper_id)
        rows = compare_papers(
            collection["id"], "u1", paper_ids, completer=composition.text_completer()
        )
        cited_rows = sum(
            1 for row in rows if "[Section:" in (row["method"] + row["metrics"])
        )
        print(f"REAL_CORPUS_COMPARE rows={len(rows)} cited={cited_rows}/{len(rows)}")


if __name__ == "__main__":
    main()
