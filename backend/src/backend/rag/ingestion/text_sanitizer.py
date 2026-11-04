"""Repair text extracted from PDFs whose math fonts lack a usable ToUnicode map.

数学字体没有 ToUnicode（或编码私有）时，取到的码位会落到 CJK 区，公式里因此
冒出「覂」这类孤立汉字。这里只做两类低风险修正：

1. 把常见的错误数学码位映射回 ASCII（∗ → *、− → -、′ → '）；
2. 删除「被拉丁字符或运算符夹住」的**罕见**汉字：坏码位几乎都是 GB2312 之外的
   生僻字，而正常中文（含中文段落里的常用字）可以正常编码。再叠加「整段汉字
   占比 < 30%」与「至少有一个数学标记」两道前置条件，中文正文不会被改写。
"""

from __future__ import annotations

import re
from functools import lru_cache

# 坏字体最常见的替代码位：直接映射回 ASCII，避免污染索引与 LLM 上下文
_CHARACTER_FIXES: dict[str, str] = {
    "\u2217": "*",  # ∗ ASTERISK OPERATOR
    "\u2212": "-",  # − MINUS SIGN
    "\u2032": "'",  # ′ PRIME
    "\u2033": "''",  # ″ DOUBLE PRIME
    "\u00a0": " ",  # NBSP
    "\ufeff": "",  # BOM
    "\ufffd": "",  # REPLACEMENT CHARACTER
}

_CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_ASCII_CONTEXT = r"\sA-Za-z0-9()\[\]{}+\-=<>|,;:._^/'\"×·"

_ISOLATED_CJK_RE = re.compile(rf"(?<=[{_ASCII_CONTEXT}])[{_CJK}](?=[{_ASCII_CONTEXT}])")
_CJK_RE = re.compile(rf"[{_CJK}]")
_MATH_MARKER_RE = re.compile(r"[=^_\\{}$<>≤≥±×÷∑∫+*\-]")
_DOUBLE_SPACE_RE = re.compile(r"[ \t]{2,}")

# 行内公式允许出现在 $...$ 之外的非字母字符（不包含字母，靠字母结束一段公式）
_LATEX_RUN_ALLOWED = frozenset(" \t0123456789+-=<>,.;:|*/()[]'_^&%!?~")
_LATEX_PATH_PREFIX = frozenset(":\\/")

# 整段汉字占比的阈值；超过它说明是中文正文，不做孤立 CJK 删除
_MAX_CJK_RATIO_FOR_REPAIR = 0.3


def cjk_ratio(text: str) -> float:
    """Share of CJK characters among visible characters."""
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return 0.0
    return len(_CJK_RE.findall(text)) / len(visible)


@lru_cache(maxsize=4096)
def _is_common_chinese(char: str) -> bool:
    """True when the character belongs to the common (GB2312) Chinese set."""
    try:
        char.encode("gb2312")
    except UnicodeEncodeError:
        return False
    return True


def _replace_isolated_cjk(match: re.Match[str]) -> str:
    char = match.group(0)
    return char if _is_common_chinese(char) else " "


def sanitize_extracted_text(text: str) -> str:
    """Normalise broken math glyphs while leaving normal prose untouched."""
    if not text:
        return text
    cleaned = "".join(_CHARACTER_FIXES.get(char, char) for char in text)
    if not _MATH_MARKER_RE.search(cleaned):
        return cleaned
    if cjk_ratio(cleaned) > _MAX_CJK_RATIO_FOR_REPAIR:
        return cleaned

    repaired = _ISOLATED_CJK_RE.sub(_replace_isolated_cjk, cleaned)
    if repaired == cleaned:
        return cleaned
    return _DOUBLE_SPACE_RE.sub(" ", repaired).strip()


def wrap_bare_latex(text: str) -> str:
    """Wrap inline LaTeX that lost its ``$`` delimiters.

    MinerU 的 inline 公式碎片有时只给裸 LaTeX，拼进段落就变成
    ``Let \\mathbf{...} denote``，Markdown 会把反斜杠原样显示出来。
    这里把「看起来像公式」的连续片段补回 ``$...$``；已有 ``$`` 的区域不动，
    因此对已修复的文本是幂等的。
    """
    if "\\" not in text:
        return text

    out: list[str] = []
    index = 0
    length = len(text)
    in_math = False

    while index < length:
        char = text[index]
        if char == "\\" and index + 1 < length and text[index + 1] == "$":
            out.append(text[index : index + 2])
            index += 2
            continue
        if char == "$":
            in_math = not in_math
            out.append(char)
            index += 1
            continue
        if not in_math and char == "\\" and index + 1 < length and text[index + 1].isalpha():
            end = _latex_run_end(text, index)
            body = text[index:end].rstrip()
            trailing = text[index + len(body) : end]
            if _looks_like_latex_run(body) and not _preceded_by_path(text, index):
                if out and out[-1][-1:].isalnum():
                    out.append(" ")
                out.append(f"${body}$")
                if end < length and text[end].isalnum() and not trailing.strip():
                    # MinerU 拼接碎片时会丢掉公式与后文之间的空格
                    trailing = " "
            else:
                out.append(body)
            out.append(trailing)
            index = end
            continue
        out.append(char)
        index += 1

    return "".join(out)


def _latex_run_end(text: str, start: int) -> int:
    """End offset of a contiguous LaTeX run starting at ``start``."""
    index = start
    depth = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            if index + 1 < length and text[index + 1].isalpha():
                index += 1
                while index < length and text[index].isalpha():
                    index += 1
                continue
            index += 2
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            if depth == 0:
                break
            depth -= 1
            index += 1
            continue
        if depth > 0 or char in _LATEX_RUN_ALLOWED:
            index += 1
            continue
        break
    return index


def _looks_like_latex_run(body: str) -> bool:
    if not body.startswith("\\"):
        return False
    if "{" in body:
        return True
    return "_" in body or "^" in body


def _preceded_by_path(text: str, start: int) -> bool:
    """``C:\\Users`` 这类路径里的反斜杠不能当公式起点。"""
    if start == 0:
        return False
    previous = text[start - 1]
    return previous.isalnum() or previous in _LATEX_PATH_PREFIX
