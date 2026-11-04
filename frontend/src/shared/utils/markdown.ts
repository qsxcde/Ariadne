import MarkdownIt from "markdown-it";
import type StateBlock from "markdown-it/lib/rules_block/state_block.mjs";
import type StateInline from "markdown-it/lib/rules_inline/state_inline.mjs";
import type Token from "markdown-it/lib/token.mjs";

export type MathKind = "inline" | "block";

export type MarkdownNode = {
  id: string;
  tag: MarkdownAllowedTag | null;
  text?: string;
  /** 公式节点：text 是 KaTeX 源串，存在时优先于 tag 渲染。 */
  math?: MathKind;
  children?: MarkdownNode[];
};

export type MarkdownAllowedTag =
  "br" | "blockquote" | "code" | "em" | "h3" | "h4" | "h5" | "li" | "p" | "pre" | "strong" | "ul";

const markdown = new MarkdownIt({
  breaks: true,
  html: false,
  linkify: false,
});

const DOLLAR = 0x24;
const BACKSLASH = 0x5c;

function isWhitespace(code: number): boolean {
  return code === 0x20 || code === 0x09 || code === 0x0a;
}

function isDigit(code: number): boolean {
  return code >= 0x30 && code <= 0x39;
}

/**
 * 行内公式 `$...$`。
 *
 * 刻意保持保守：`$$` 交给块规则、首尾不能是空白、右括号后紧跟数字时不当公式
 * （"$5 和 $10" 这类正文不能变成公式）。
 */
function mathInline(state: StateInline, silent: boolean): boolean {
  const start = state.pos;
  const max = state.posMax;
  if (state.src.charCodeAt(start) !== DOLLAR) {
    return false;
  }
  if (start + 1 >= max || state.src.charCodeAt(start + 1) === DOLLAR) {
    return false;
  }
  if (isWhitespace(state.src.charCodeAt(start + 1))) {
    return false;
  }

  let pos = start + 1;
  while (pos < max) {
    const code = state.src.charCodeAt(pos);
    if (code === BACKSLASH) {
      pos += 2;
      continue;
    }
    if (code === DOLLAR) {
      break;
    }
    pos += 1;
  }

  if (pos >= max || pos === start + 1) {
    return false;
  }
  if (isWhitespace(state.src.charCodeAt(pos - 1))) {
    return false;
  }
  if (pos + 1 < max && isDigit(state.src.charCodeAt(pos + 1))) {
    return false;
  }

  if (!silent) {
    const token = state.push("math_inline", "math", 0);
    token.markup = "$";
    token.content = state.src.slice(start + 1, pos);
  }
  state.pos = pos + 1;
  return true;
}

/** 块级公式 `$$ ... $$`，支持单行与多行两种写法。 */
function mathBlock(
  state: StateBlock,
  startLine: number,
  endLine: number,
  silent: boolean,
): boolean {
  const start = state.bMarks[startLine] + state.tShift[startLine];
  const firstLineEnd = state.eMarks[startLine];
  if (state.src.slice(start, start + 2) !== "$$") {
    return false;
  }

  const firstLineTail = state.src.slice(start + 2, firstLineEnd);
  const singleLineClose = firstLineTail.lastIndexOf("$$");
  let content: string;
  let nextLine = startLine;

  if (singleLineClose >= 0) {
    content = firstLineTail.slice(0, singleLineClose);
  } else {
    const lines = [firstLineTail];
    let closed = false;
    for (nextLine = startLine + 1; nextLine < endLine; nextLine += 1) {
      const lineStart = state.bMarks[nextLine] + state.tShift[nextLine];
      const line = state.src.slice(lineStart, state.eMarks[nextLine]);
      if (line.trim() === "$$") {
        closed = true;
        break;
      }
      if (line.trimEnd().endsWith("$$")) {
        lines.push(line.slice(0, line.lastIndexOf("$$")));
        closed = true;
        break;
      }
      lines.push(line);
    }
    if (!closed) {
      return false;
    }
    content = lines.join("\n");
  }

  if (silent) {
    return true;
  }

  const token = state.push("math_block", "math", 0);
  token.block = true;
  token.markup = "$$";
  token.content = content.trim();
  token.map = [startLine, nextLine + 1];
  state.line = nextLine + 1;
  return true;
}

markdown.inline.ruler.before("escape", "math_inline", mathInline);
markdown.block.ruler.before("fence", "math_block", mathBlock, {
  alt: ["paragraph", "reference", "blockquote", "list"],
});

/** 兼容 MinerU 行间公式自带的 `$$`、`\[ \]`、`\( \)` 包裹。 */
export function stripMathDelimiters(text: string): string {
  const trimmed = text.trim();
  const pairs: [string, string][] = [
    ["$$", "$$"],
    ["\\[", "\\]"],
    ["\\(", "\\)"],
  ];
  for (const [left, right] of pairs) {
    if (trimmed.startsWith(left) && trimmed.endsWith(right)) {
      const body = trimmed.slice(left.length, trimmed.length - right.length);
      if (body.trim()) {
        return body.trim();
      }
    }
  }
  return trimmed;
}

const BLOCK_TAG_MAP: Record<string, MarkdownAllowedTag> = {
  blockquote: "blockquote",
  h1: "h3",
  h2: "h4",
  h3: "h5",
  h4: "h5",
  h5: "h5",
  h6: "h5",
  li: "li",
  p: "p",
  pre: "pre",
  ul: "ul",
  ol: "ul",
};

const INLINE_TAG_MAP: Record<string, MarkdownAllowedTag> = {
  code: "code",
  em: "em",
  strong: "strong",
};

function createNodeId(prefix: string, index: number): string {
  return `${prefix}-${index}`;
}

function createTextNode(text: string, index: number): MarkdownNode | null {
  if (!text) {
    return null;
  }
  return {
    id: createNodeId("text", index),
    tag: null,
    text,
  };
}

function collectInlineTokens(tokens: Token[], startIndex: number): MarkdownNode[] {
  const nodes: MarkdownNode[] = [];

  for (const [offset, token] of tokens.entries()) {
    const nodeIndex = startIndex + offset;
    if (token.type === "text") {
      const textNode = createTextNode(token.content, nodeIndex);
      if (textNode) {
        nodes.push(textNode);
      }
      continue;
    }

    if (token.type === "math_inline") {
      nodes.push({
        id: createNodeId("math-inline", nodeIndex),
        tag: null,
        text: token.content,
        math: "inline",
      });
      continue;
    }

    if (token.type === "softbreak" || token.type === "hardbreak") {
      nodes.push({
        id: createNodeId("break", nodeIndex),
        tag: "br",
      });
      continue;
    }

    if (token.type === "code_inline") {
      nodes.push({
        id: createNodeId("inline-code", nodeIndex),
        tag: "code",
        children: [
          {
            id: createNodeId("inline-code-text", nodeIndex),
            tag: null,
            text: token.content,
          },
        ],
      });
      continue;
    }

    if (token.type === "image") {
      const textNode = createTextNode(`[${token.content || "图片"}]`, nodeIndex);
      if (textNode) {
        nodes.push(textNode);
      }
      continue;
    }

    const normalizedTag = INLINE_TAG_MAP[token.tag];
    if (!normalizedTag || !token.children) {
      continue;
    }

    nodes.push({
      id: createNodeId(normalizedTag, nodeIndex),
      tag: normalizedTag,
      children: collectInlineTokens(token.children, nodeIndex * 10 + 1),
    });
  }

  return nodes;
}

function readList(tokens: Token[], startIndex: number): { nextIndex: number; node: MarkdownNode } {
  const children: MarkdownNode[] = [];
  let cursor = startIndex + 1;

  while (
    cursor < tokens.length &&
    tokens[cursor].type !== "bullet_list_close" &&
    tokens[cursor].type !== "ordered_list_close"
  ) {
    if (tokens[cursor].type === "list_item_open") {
      const inlineToken = tokens[cursor + 2];
      children.push({
        id: createNodeId("list-item", cursor),
        tag: "li",
        children: collectInlineTokens(inlineToken?.children ?? [], cursor * 10 + 1),
      });
      cursor += 4;
      continue;
    }
    cursor += 1;
  }

  return {
    nextIndex: cursor + 1,
    node: {
      id: createNodeId("list", startIndex),
      tag: "ul",
      children,
    },
  };
}

function readBlockquote(
  tokens: Token[],
  startIndex: number,
): { nextIndex: number; node: MarkdownNode } {
  const inlineToken = tokens[startIndex + 2];
  return {
    nextIndex: startIndex + 4,
    node: {
      id: createNodeId("blockquote", startIndex),
      tag: "blockquote",
      children: collectInlineTokens(inlineToken?.children ?? [], startIndex * 10 + 1),
    },
  };
}

function readHeading(
  tokens: Token[],
  startIndex: number,
): { nextIndex: number; node: MarkdownNode } {
  const headingOpenToken = tokens[startIndex];
  const inlineToken = tokens[startIndex + 1];
  return {
    nextIndex: startIndex + 3,
    node: {
      id: createNodeId("heading", startIndex),
      tag: BLOCK_TAG_MAP[headingOpenToken.tag] ?? "h5",
      children: collectInlineTokens(inlineToken?.children ?? [], startIndex * 10 + 1),
    },
  };
}

/**
 * Parses markdown into a constrained node tree so the UI can render rich text
 * without using v-html or exposing arbitrary HTML.
 */
export function parseMarkdown(text: string): MarkdownNode[] {
  const normalizedText = text.trim();
  if (!normalizedText) {
    return [];
  }

  const tokens = markdown.parse(normalizedText, {});
  const nodes: MarkdownNode[] = [];
  let index = 0;

  while (index < tokens.length) {
    const token = tokens[index];

    if (token.type === "inline") {
      nodes.push({
        id: createNodeId("paragraph", index),
        tag: "p",
        children: collectInlineTokens(token.children ?? [], index * 10 + 1),
      });
      index += 1;
      continue;
    }

    if (token.type === "math_block") {
      nodes.push({
        id: createNodeId("math-block", index),
        tag: null,
        text: token.content,
        math: "block",
      });
      index += 1;
      continue;
    }

    if (token.type === "fence" || token.type === "code_block") {
      nodes.push({
        id: createNodeId("code-block", index),
        tag: "pre",
        children: [
          {
            id: createNodeId("code-block-code", index),
            tag: "code",
            children: [
              {
                id: createNodeId("code-block-text", index),
                tag: null,
                text: token.content,
              },
            ],
          },
        ],
      });
      index += 1;
      continue;
    }

    if (token.type === "bullet_list_open" || token.type === "ordered_list_open") {
      const result = readList(tokens, index);
      nodes.push(result.node);
      index = result.nextIndex;
      continue;
    }

    if (token.type === "blockquote_open") {
      const result = readBlockquote(tokens, index);
      nodes.push(result.node);
      index = result.nextIndex;
      continue;
    }

    if (token.type === "heading_open") {
      const result = readHeading(tokens, index);
      nodes.push(result.node);
      index = result.nextIndex;
      continue;
    }

    index += 1;
  }

  return nodes;
}
