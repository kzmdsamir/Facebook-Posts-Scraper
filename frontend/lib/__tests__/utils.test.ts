import { describe, expect, it } from "vitest";
import { cn, formatCompact, formatDateTime, pluralize } from "@/lib/utils";

describe("cn", () => {
  it("merges tailwind classes and keeps the last conflicting one", () => {
    expect(cn("px-2 py-1", "px-4", false && "hidden")).toBe("py-1 px-4");
  });
});

describe("formatCompact", () => {
  it("formats thousands compactly and renders a dash for missing values", () => {
    expect(formatCompact(2500)).toContain("2.5");
    expect(formatCompact(null)).toBe("–");
    expect(formatCompact(123)).toBe("123");
  });
});

describe("formatDateTime", () => {
  it("renders ISO timestamps into a readable local string", () => {
    const out = formatDateTime("2026-09-13T16:22:35Z");
    expect(out).toBeTruthy();
    expect(out).not.toContain("NaN");
  });
});

describe("pluralize", () => {
  it("picks singular and plural forms", () => {
    expect(pluralize(1, "post")).toBe("1 post");
    expect(pluralize(2, "post")).toBe("2 posts");
  });
});