import re
from io import BytesIO

from backend.config import settings
from backend.domain.parsing import RawParserResult

FALLBACK_BLOCK_WORDS = 180
# ``estimate_tokens`` counts roughly one token per three English words, so a
# block meant to fill a third of the chunk budget needs about that many words.
WORDS_PER_TOKEN = 3
MIN_BLOCK_WORDS = 80

# 标题恢复的保守阈值：纯文本没有版面信息，宁缺毋滥
MAX_HEADING_WORDS = 14
MAX_HEADING_CHARS = 120
MAX_HEADER_LINE_CHARS = 80
HEADER_REPEAT_PAGES = 3

_NUMBERED_HEADING_RE = re.compile(r"^(?P<number>\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(?P<title>\S.*)$")
_ROMAN_HEADING_RE = re.compile(r"^(?P<number>[IVXLC]{1,6})\.\s+(?P<title>\S.*)$")
_PAGE_NUMBER_RE = re.compile(r"^(?:[-–—]\s*)?\d{1,4}(?:\s*[-–—])?$")
_SENTENCE_ENDINGS = (".", ",", ";", ":")
_MATH_CHARS = frozenset("=+^_\\{}−×÷≤≥±")
# 全大写标题必须整行都是 ASCII 大写，避免把图注/公式行（∇、∆、Λ、% 等）当成标题
_ASCII_CAPS_RE = re.compile(r"^[A-Z][A-Z\s&.,'\-]*$")
_TITLE_TOKEN_EXTRA = frozenset("-'’")

# 只在整行匹配时才算标题；正文里出现这些词不会被误判
_HEADING_KEYWORDS = frozenset(
    {
        "abstract",
        "introduction",
        "related work",
        "background",
        "references",
        "bibliography",
        "appendix",
        "contents",
        "conclusion",
        "conclusions",
        "acknowledgment",
        "acknowledgments",
        "acknowledgement",
        "acknowledgements",
    }
)


class TextPDFBackend:
    name = "pypdf-text"
    version = "unknown"

    def parse(self, pdf_bytes: bytes, filename: str | None = None) -> RawParserResult:
        from pypdf import PdfReader
        from pypdf.errors import FileNotDecryptedError, PdfReadError

        try:
            reader = PdfReader(BytesIO(pdf_bytes))
        except FileNotDecryptedError as exc:
            raise RuntimeError("PDF is encrypted and cannot be parsed") from exc
        except PdfReadError as exc:
            raise RuntimeError(f"PDF cannot be parsed: {exc}") from exc
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:  # 空密码也不可用时视为加密文件
                raise RuntimeError("PDF is encrypted and cannot be parsed") from exc

        raw_pages: list[tuple[int, str, float, float, int]] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            raw_pages.append(
                (
                    index,
                    text,
                    float(page.mediabox.width or 0),
                    float(page.mediabox.height or 0),
                    int(page.rotation or 0),
                )
            )

        repeated_lines = _repeated_header_lines([text for _, text, *_ in raw_pages])
        page_texts: list[str] = []
        pages: list[dict] = []
        for number, text, width, height, rotation in raw_pages:
            page_texts.append(text.strip())
            pages.append(
                {
                    "page_number": number,
                    "width": width,
                    "height": height,
                    "rotation": rotation,
                    "blocks": _blocks_for_page_text(
                        text=text,
                        page_number=number,
                        width=width,
                        height=height,
                        drop_lines=repeated_lines,
                    ),
                }
            )
        markdown = "\n\n".join(page_texts)
        return RawParserResult(
            markdown=markdown,
            page_count=len(reader.pages),
            pages=pages,
            metadata={"filename": filename or ""},
            source_parser=self.name,
            bbox_unit="points",
        )


def _block_word_budget() -> int:
    """Words per block, kept proportional to the chunk budget (which is in tokens)."""
    return min(
        max(settings.max_chunk_tokens // WORDS_PER_TOKEN, MIN_BLOCK_WORDS),
        FALLBACK_BLOCK_WORDS,
    )


def _blocks_for_page_text(
    *,
    text: str,
    page_number: int,
    width: float,
    height: float,
    max_words: int | None = None,
    drop_lines: frozenset[str] | set[str] = frozenset(),
) -> list[dict]:
    """Split page text into heading and paragraph blocks.

    pypdf only gives us a flat text layer, so headings are recovered with
    conservative line heuristics: numbered / Roman-numeral / keyword / all-caps
    short lines that start a new line block. Everything else stays a paragraph.
    """
    lines = text.splitlines()
    budget = max_words or _block_word_budget()
    blocks: list[dict] = []
    body: list[str] = []

    def flush_body() -> None:
        nonlocal body
        body_text = " ".join(part.strip() for part in body).strip()
        body = []
        if not body_text:
            return
        for piece in _split_words(body_text, budget):
            blocks.append(
                {
                    "text": piece,
                    "bbox": (0.0, 0.0, width, height),
                    "type": "paragraph",
                    "confidence": 0.5,
                }
            )

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            flush_body()
            continue
        if line in drop_lines or _PAGE_NUMBER_RE.match(line):
            continue
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        level = _heading_level(line, next_line)
        if level is not None:
            flush_body()
            blocks.append(
                {
                    "text": line,
                    "bbox": (0.0, 0.0, width, height),
                    "type": "title",
                    "heading_level": level,
                    "confidence": 0.6,
                }
            )
            continue
        body.append(line)

    flush_body()
    return blocks


def _split_words(text: str, budget: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [" ".join(words[offset : offset + budget]) for offset in range(0, len(words), budget)]


def _heading_level(line: str, next_line: str) -> int | None:
    """Return the recovered heading depth, or ``None`` when the line is body text."""
    text = line.strip()
    if not text or len(text) > MAX_HEADING_CHARS:
        return None
    if len(text.split()) > MAX_HEADING_WORDS:
        return None
    if _PAGE_NUMBER_RE.match(text):
        return None
    if text[-1].isdigit():
        # 目录行形如 "4.1.2 Covariant-theory approach 19"
        return None
    if text[-1] in _SENTENCE_ENDINGS:
        return None
    if not _starts_new_block(next_line):
        return None

    if _is_keyword_heading(text):
        return 1

    numbered = _NUMBERED_HEADING_RE.match(text)
    if numbered and _starts_with_title_char(numbered.group("title")):
        return len(numbered.group("number").split("."))

    roman = _ROMAN_HEADING_RE.match(text)
    if roman and _starts_with_title_char(roman.group("title")):
        return 1

    if _is_all_caps_heading(text):
        return 1
    return None


def _starts_new_block(next_line: str) -> bool:
    """A heading is never followed by a lower-case continuation of the same sentence."""
    stripped = next_line.strip()
    if not stripped:
        return True
    return not stripped[0].islower()


def _is_keyword_heading(text: str) -> bool:
    normalized = text.rstrip(".").strip().lower()
    return normalized in _HEADING_KEYWORDS


def _starts_with_title_char(title: str) -> bool:
    """Heading titles start with a real word, not a symbol or a formula token."""
    stripped = title.strip()
    if not stripped:
        return False
    if any(char in _MATH_CHARS for char in stripped):
        return False
    first_token = stripped.split(maxsplit=1)[0]
    if not first_token[0].isupper():
        return False
    letters = sum(1 for char in first_token if char.isalpha())
    if letters < 3:
        return False
    return all(char.isalpha() or char in _TITLE_TOKEN_EXTRA for char in first_token)


def _is_all_caps_heading(text: str) -> bool:
    if not _ASCII_CAPS_RE.match(text):
        return False
    letters = sum(1 for char in text if char.isalpha())
    return letters >= 4 and len(text.split()) <= 8


def _repeated_header_lines(page_texts: list[str]) -> set[str]:
    """Lines repeated on many pages are running headers/footers, not content."""
    pages_per_line: dict[str, set[int]] = {}
    for page_index, text in enumerate(page_texts):
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or len(line) > MAX_HEADER_LINE_CHARS:
                continue
            if _PAGE_NUMBER_RE.match(line):
                continue
            pages_per_line.setdefault(line, set()).add(page_index)
    return {line for line, pages in pages_per_line.items() if len(pages) >= HEADER_REPEAT_PAGES}
