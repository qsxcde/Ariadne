import { describe, expect, it } from "vitest";
import { formatDuration } from "../format";

describe("formatDuration", () => {
  it("renders minutes under an hour", () => {
    expect(formatDuration(0)).toBe("0 分钟");
    expect(formatDuration(90)).toBe("2 分钟");
    expect(formatDuration(59 * 60 + 40)).toBe("1 小时");
  });

  it("splits hours and minutes", () => {
    expect(formatDuration(3600)).toBe("1 小时");
    expect(formatDuration(3660)).toBe("1 小时 1 分");
    expect(formatDuration(7325)).toBe("2 小时 2 分");
  });
});
