"""Wrap pure session tools as LangChain StructuredTools.

This module is the only bridge between the framework and the business tools.
"""

import json
from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool

from backend.application.agent.tool_specs import (
    PAPER_TOOL,
    READ_TOOL,
    SEARCH_TOOL,
    GetPaperArgs,
    ReadChunkArgs,
    SearchSessionChunksArgs,
)
from backend.application.agent.tools.session_tools import SessionTools
from backend.domain.agent import ToolResult


def _dump(result: ToolResult) -> str:
    return json.dumps(
        {
            "ok": result.ok,
            "content": result.content,
            "summary": result.summary,
            "sources": [source.model_dump() for source in result.sources],
            "error": result.error,
        },
        ensure_ascii=False,
    )


def _safe(call: Callable[[], ToolResult]) -> str:
    try:
        return _dump(call())
    except Exception as exc:  # tool errors go back to the model as data
        return _dump(ToolResult.failure(f"工具执行失败：{exc}"))


def build_langchain_tools(session_tools: SessionTools) -> list[StructuredTool]:
    def search_session_chunks(
        query: str,
        paper_ids: list[str] | None = None,
        section: str | None = None,
        top_k: int = 5,
    ) -> str:
        return _safe(
            lambda: session_tools.search_session_chunks(
                query=query,
                paper_ids=paper_ids,
                section=section,
                top_k=top_k,
            )
        )

    def read_chunk(paper_id: str, section: str, chunk_index: int) -> str:
        return _safe(
            lambda: session_tools.read_chunk(
                paper_id=paper_id,
                section=section,
                chunk_index=chunk_index,
            )
        )

    def get_paper(paper_id: str | None = None) -> str:
        return _safe(lambda: session_tools.get_paper(paper_id=paper_id))

    return [
        StructuredTool.from_function(
            func=search_session_chunks,
            name=SEARCH_TOOL,
            description="在当前会话的论文全文中做检索，返回片段预览、章节与来源。",
            args_schema=SearchSessionChunksArgs,
        ),
        StructuredTool.from_function(
            func=read_chunk,
            name=READ_TOOL,
            description="读取指定片段的全文，参数来自检索结果的 Section 与 Chunk。",
            args_schema=ReadChunkArgs,
        ),
        StructuredTool.from_function(
            func=get_paper,
            name=PAPER_TOOL,
            description="获取当前会话中论文的元数据（标题、作者、年份、摘要）。",
            args_schema=GetPaperArgs,
        ),
    ]
