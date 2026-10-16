import { describe, expect, it } from "vitest";

import {
  formatDate,
  formatEur,
  formatEurCompact,
  formatMonthTick,
  formatPercent,
  formatSignedEur,
} from "./format";

// Intl uses non-breaking spaces; normalize them so expectations stay readable
const plain = (text: string) => text.replace(/ | /g, " ");

describe("format", () => {
  it("formatEur", () => {
    expect(plain(formatEur(1234.5))).toBe("1234,50 €");
    expect(formatEur(null)).toBe("—");
  });

  it("formatEurCompact", () => {
    expect(plain(formatEurCompact(12500))).toBe("12,5 mil €");
  });

  it("formatSignedEur", () => {
    expect(plain(formatSignedEur(12))).toBe("+12,00 €");
    expect(plain(formatSignedEur(-3))).toBe("−3,00 €");
    expect(plain(formatSignedEur(0))).toBe("0,00 €");
    expect(formatSignedEur(undefined)).toBe("—");
  });

  it("formatPercent", () => {
    expect(plain(formatPercent(0.0532))).toBe("5,3 %");
    expect(plain(formatPercent(0.0532, true))).toBe("+5,3 %");
    expect(plain(formatPercent(-0.1, true))).toBe("−10,0 %");
    expect(plain(formatPercent(-0.1))).toBe("−10,0 %");
    expect(formatPercent(Number.NaN)).toBe("—");
  });

  it("formatDate and formatMonthTick", () => {
    expect(formatDate("2026-10-05")).toBe("5 oct 2026");
    expect(formatMonthTick("2026-01")).toBe("ene 26");
  });
});
