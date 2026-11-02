"""Prompt context budgeting for small-context models."""

import pytest

from backend.adapters.llm.prompt_template import build_prompt
from backend.domain.models import Chunk, ChunkMetadata


def _chunk(index: int, text: str) -> Chunk:
    return Chunk(
        text=text,
        metadata=ChunkMetadata(
            paper_id="paper_1",
            section=f"S{index}",
            section_path=[f"S{index}"],
            chunk_index=index,
            type="paragraph",
        ),
    )


@pytest.mark.unit
def test_prompt_keeps_whole_chunks_within_budget():
    chunks = [_chunk(0, "A" * 1000), _chunk(1, "B" * 1000), _chunk(2, "C" * 1000)]

    prompt = build_prompt(chunks, "q", max_context_chars=2200)

    assert "A" * 1000 in prompt
    assert "C" * 1000 not in prompt


@pytest.mark.unit
def test_first_chunk_is_truncated_instead_of_dropped():
    prompt = build_prompt([_chunk(0, "X" * 5000)], "q", max_context_chars=1500)

    assert "Section: S0" in prompt
    assert len(prompt) < 4000
