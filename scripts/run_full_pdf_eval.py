"""Experimental full-PDF evaluation on real arXiv papers (local model).

Status (2026-11-03): exploratory only. On the local 3B model with a 4k context,
metadata questions over body chunks score 1/9: the first page is often not
retrieved and long contexts are silently truncated. Keep this script for the
DeepSeek / annotated-corpus baseline; it is not a phase gate.
"""

import json
import os
from pathlib import Path

import httpx

from backend import composition
from backend.domain.models import Chunk
from backend.rag.answer import AnswerPolicy, RetrievalOptions, stream_answer
from backend.rag.indexing.vector_store import FAISSVectorStore
from backend.rag.ingestion.chunking import build_chunks
from backend.rag.ingestion.normalizer import normalize_parser_output
from backend.rag.ingestion.text_pdf_backend import TextPDFBackend

CACHE = Path(os.getenv("REAL_PAPER_CACHE", "/tmp/scipal_real_papers.json"))
PDF_DIR = Path(os.getenv("REAL_PDF_DIR", "/tmp/scipal_pdfs"))
PAPERS = int(os.getenv("REAL_PDF_PAPERS", "3"))


def _download(arxiv_id: str) -> bytes:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    target = PDF_DIR / f"{arxiv_id}.pdf"
    if target.exists():
        return target.read_bytes()
    response = httpx.get(
        f"https://arxiv.org/pdf/{arxiv_id}",
        timeout=60,
        follow_redirects=True,
        headers={"User-Agent": "SciPal/0.1 (full pdf eval)"},
    )
    response.raise_for_status()
    target.write_bytes(response.content)
    return response.content


def _seed_paper(item: dict) -> tuple[list[Chunk], dict[str, str]]:
    arxiv_id = str(item["external_id"]).rsplit("/", 1)[-1]
    base_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
    pdf = _download(base_id)
    backend = TextPDFBackend()
    raw = backend.parse(pdf, filename=f"{base_id}.pdf")
    paper_id = f"paper_{base_id}"
    ir = normalize_parser_output(raw, paper_id=paper_id, filename=f"{base_id}.pdf", parser_backend=backend)
    chunks = build_chunks(ir, raw.markdown, paper_id)
    authors = json.loads(item.get("authors_json") or "[]")
    first = authors[0].split()[-1] if authors else ""
    second = authors[1].split()[-1] if len(authors) > 1 else ""
    title_phrase = " ".join(str(item["title"]).split()[:5])
    meta = {
        "arxiv_id": base_id,
        "first": first,
        "second": second,
        "title": title_phrase,
        "year": str(item.get("published_at") or "")[:4],
        "pages": str(raw.page_count),
        "chunks": str(len(chunks)),
    }
    return chunks, meta


def main() -> None:
    items = json.loads(CACHE.read_text(encoding="utf-8"))[:PAPERS]
    all_chunks: list[Chunk] = []
    cases: list[tuple[str, str, str]] = []
    for item in items:
        chunks, meta = _seed_paper(item)
        all_chunks.extend(chunks)
        print(f"parsed {meta['arxiv_id']} pages={meta['pages']} chunks={meta['chunks']}", flush=True)
        paper_scope = meta["arxiv_id"]
        cases.extend([
            ("Who is the first author of this paper? Answer with the name only.", meta["first"], paper_scope),
            ("What is the last name of the second author of this paper? Answer with the name only.", meta["second"], paper_scope),
            ("What is the title of this paper? Answer with the title only.", meta["title"], paper_scope),
        ])

    store = FAISSVectorStore(embed_fn=composition.embedder(), embedding_dim=768)
    store.add_chunks(all_chunks)
    policy = AnswerPolicy(empty_retrieval_message="没有相关信息", invalid_citation_message="引用无效")
    correct = 0
    cited = 0
    for question, expected, scope in cases:
        options = RetrievalOptions(
            strategy="hybrid",
            bm25_top_k=1,
            dense_top_k=1,
            seed_top_k=1,
            max_expanded_chunks=1,
            same_section_window=0,
            adjacent_window=0,
            include_linked_blocks=False,
            enable_reranker=False,
            history_rewrite_enabled=False,
            term_expand_enabled=False,
            document_ids=[f"paper_{scope}"],
        )
        answer = ""
        for event in stream_answer(store, question, policy=policy, options=options):
            if event["type"] == "token":
                answer += event["value"]
        if expected and expected.lower() in answer.lower():
            correct += 1
        else:
            print(f"MISS expected={expected!r} A={answer[:160]!r}", flush=True)
        if "[Section:" in answer:
            cited += 1
    print(f"REAL_PDF correct={correct}/{len(cases)} cited={cited}/{len(cases)}", flush=True)


if __name__ == "__main__":
    main()
