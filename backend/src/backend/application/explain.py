"""Explain, translate or simplify a selected passage."""

from typing import Any

from backend import composition
from backend.application.papers import get_accessible_paper

_PROMPTS: dict[str, str] = {
    "explain": "请用中文解释这段论文原文，说明它在论文中的作用、关键概念和潜在前提。不要编造原文没有的信息。",
    "translate": "请把这段论文原文翻译成中文，保留公式、术语、数字和引用标记；不要添加解释。",
    "simplify": "请用更简单的中文重述这段论文原文，保留技术含义，必要时给出一个直观例子。",
}


def explain_selection(
    paper_id: str,
    user_id: str | None,
    *,
    text: str,
    mode: str,
    completer: Any | None = None,
) -> str:
    get_accessible_paper(paper_id, user_id)
    if mode not in _PROMPTS:
        raise ValueError(f"Invalid explain mode: {mode}")
    quote = text.strip()
    if not quote:
        raise ValueError("Selected text is empty")
    from backend.application.generation_log import generation_timer

    runner = completer or composition.text_completer()
    prompt = f"{_PROMPTS[mode]}\n\n原文：\n{quote[:2000]}"
    with generation_timer("explain", paper_id=paper_id):
        return str(runner.complete(prompt)).strip()
