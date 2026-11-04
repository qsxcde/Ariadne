"""Selection explain service."""

import pytest

from backend.application.reading.explain import explain_selection
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo


class FakeCompleter:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "解释结果"


def _seed() -> str:
    session = session_repo.create_session("Explain", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="explain.pdf",
        file_path="/tmp/explain.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    return document["paper_id"]


@pytest.mark.unit
def test_explain_modes_use_selected_text():
    paper_id = _seed()
    fake = FakeCompleter()

    result = explain_selection(
        paper_id,
        "u1",
        text="sparse attention",
        mode="translate",
        completer=fake,
    )

    assert result == "解释结果"
    assert "翻译成中文" in fake.prompts[0]
    assert "sparse attention" in fake.prompts[0]


@pytest.mark.unit
def test_explain_rejects_empty_text_and_unknown_mode():
    paper_id = _seed()
    fake = FakeCompleter()

    with pytest.raises(ValueError):
        explain_selection(paper_id, "u1", text="  ", mode="explain", completer=fake)
    with pytest.raises(ValueError):
        explain_selection(paper_id, "u1", text="x", mode="unknown", completer=fake)
