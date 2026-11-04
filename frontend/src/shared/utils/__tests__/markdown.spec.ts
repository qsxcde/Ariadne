import { describe, expect, it } from "vitest";

import { parseMarkdown, stripMathDelimiters } from "@/shared/utils/markdown";
import type { MarkdownNode } from "@/shared/utils/markdown";

function collect(nodes: MarkdownNode[]): MarkdownNode[] {
  return nodes.flatMap((node) => [node, ...collect(node.children ?? [])]);
}

describe("parseMarkdown math", () => {
  it("识别行内公式并保留 LaTeX 源串", () => {
    const blocks = parseMarkdown("能量满足 $E = mc^2$ 的关系。");
    const math = collect(blocks).find((node) => node.math === "inline");

    expect(math?.text).toBe("E = mc^2");
    const plainText = collect(blocks).filter((node) => node.tag === null && !node.math);
    expect(plainText.some((node) => node.text?.includes("$"))).toBe(false);
  });

  it("识别多行块级公式", () => {
    const blocks = parseMarkdown("$$\nH^2 M_*^2 = 2\\phi' a\n$$");
    const math = collect(blocks).find((node) => node.math === "block");

    expect(blocks).toHaveLength(1);
    expect(math?.text).toBe("H^2 M_*^2 = 2\\phi' a");
  });

  it("识别单行块级公式", () => {
    const blocks = parseMarkdown("$$x_{i}^{2}$$");
    expect(collect(blocks).find((node) => node.math === "block")?.text).toBe("x_{i}^{2}");
  });

  it("解析带空格的花体命令（MinerU 行内公式形态）", () => {
    const blocks = parseMarkdown(
      "Let $\\mathbf { \\boldsymbol { \\mathsf { \\mathbf { \\theta } } } }$ denote the gate vector.",
    );
    const math = collect(blocks).find((node) => node.math === "inline");

    expect(math?.text?.startsWith("\\mathbf")).toBe(true);
    const plainText = collect(blocks).filter((node) => node.tag === null && !node.math);
    expect(plainText.some((node) => node.text?.includes("denote the gate vector"))).toBe(true);
  });

  it("不把价格当公式", () => {
    const blocks = parseMarkdown("价格 $5 和 $10 差距明显");
    expect(collect(blocks).some((node) => node.math)).toBe(false);
    expect(collect(blocks).some((node) => node.text?.includes("$5"))).toBe(true);
  });

  it("转义美元符号不开启公式", () => {
    const blocks = parseMarkdown("成本 \\$5, 收益 \\$10");
    expect(collect(blocks).some((node) => node.math)).toBe(false);
  });
});

describe("stripMathDelimiters", () => {
  it("剥掉 MinerU 的 $$ 包裹", () => {
    expect(stripMathDelimiters("$$\na + b\n$$")).toBe("a + b");
  });

  it("剥掉 \\[ \\] 包裹", () => {
    expect(stripMathDelimiters("\\[a + b\\]")).toBe("a + b");
  });

  it("无包裹时原样返回", () => {
    expect(stripMathDelimiters(" a + b ")).toBe("a + b");
  });
});
