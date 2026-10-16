import { describe, expect, it } from "vitest";

import {
  firstDatePerMonth,
  matchingRange,
  rangeFrequency,
  rangeStartDate,
  rangeStartMonth,
  toIsoDate,
} from "./ranges";

const TODAY = new Date(2026, 9, 15); // 15 Oct 2026, local time

describe("ranges", () => {
  it("toIsoDate pads month and day", () => {
    expect(toIsoDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });

  it("rangeStartDate", () => {
    expect(rangeStartDate("3M", TODAY)).toBe("2026-07-15");
    expect(rangeStartDate("1A", TODAY)).toBe("2025-10-15");
    expect(rangeStartDate("YTD", TODAY)).toBe("2026-01-01");
    expect(rangeStartDate("TODO", TODAY)).toBeUndefined();
  });

  it("rangeFrequency", () => {
    expect(rangeFrequency("6M")).toBe("D");
    expect(rangeFrequency("1A")).toBe("W");
  });
});

describe("firstDatePerMonth", () => {
  it("keeps one date per month", () => {
    expect(firstDatePerMonth(["2026-03-02", "2026-03-09", "2026-04-06", "2026-04-13"])).toEqual([
      "2026-03-02",
      "2026-04-06",
    ]);
  });
});

describe("rangeStartMonth", () => {
  it("snaps to the first day of the month", () => {
    expect(rangeStartMonth("1A", TODAY)).toBe("2025-10-01");
    expect(rangeStartMonth("TODO", TODAY)).toBeUndefined();
  });
});

describe("matchingRange", () => {
  it("recognizes presets and custom periods", () => {
    expect(matchingRange("2026-07-15", "", TODAY)).toBe("3M");
    expect(matchingRange("", "", TODAY)).toBe("TODO");
    expect(matchingRange("2026-07-15", "2026-08-01", TODAY)).toBeNull();
    expect(matchingRange("2026-07-10", "", TODAY)).toBeNull();
  });
});
