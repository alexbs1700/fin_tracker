import { describe, expect, it } from "vitest";

import { buildQueryString } from "./client";

describe("buildQueryString", () => {
  it("repeats array keys and skips empty values", () => {
    expect(
      buildQueryString({ account: ["bbva", "revolut"], q: "", limit: 50, date_from: undefined, x: null }),
    ).toBe("?account=bbva&account=revolut&limit=50");
  });

  it("returns an empty string without params", () => {
    expect(buildQueryString({})).toBe("");
  });
});
