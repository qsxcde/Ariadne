"""Tool definitions: names, descriptions and validated arguments."""

from pydantic import BaseModel, Field

from backend.domain.agent import ToolSpec


class SearchSessionChunksArgs(BaseModel):
    query: str = Field(description="用于检索的自然语言问题或关键词")
    paper_ids: list[str] | None = Field(
        default=None,
        description="可选，只在这些论文 ID 内检索；ID 来自来源的 paper_id",
    )
    section: str | None = Field(
        default=None,
        description="可选，只在指定章节内检索，例如 Introduction",
    )
    top_k: int = Field(default=5, ge=1, le=10, description="返回的片段数量，1-10")


class ReadChunkArgs(BaseModel):
    paper_id: str = Field(description="论文 ID；可来自检索结果的来源 paper_id")
    section: str = Field(description="片段所在章节")
    chunk_index: int = Field(description="片段序号，来自检索结果的 Chunk")


class GetPaperArgs(BaseModel):
    paper_id: str | None = Field(
        default=None,
        description="论文 ID；省略时返回当前会话论文的元数据",
    )


SEARCH_TOOL = "search_session_chunks"
READ_TOOL = "read_chunk"
PAPER_TOOL = "get_paper"

TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name=SEARCH_TOOL,
        description=(
            "在当前会话的论文全文中做检索。需要定位证据、补充上下文或核对数字时调用。"
            "返回片段预览、章节与来源。"
        ),
        parameters=SearchSessionChunksArgs.model_json_schema(),
    ),
    ToolSpec(
        name=READ_TOOL,
        description=(
            "读取指定片段的全文。只在检索预览不足以回答时调用；"
            "参数来自检索结果的 Section 与 Chunk。"
        ),
        parameters=ReadChunkArgs.model_json_schema(),
    ),
    ToolSpec(
        name=PAPER_TOOL,
        description=(
            "获取当前会话中论文的元数据（标题、作者、年份、摘要）。"
            "用于确认论文身份或补充背景信息。"
        ),
        parameters=GetPaperArgs.model_json_schema(),
    ),
)
