import { describe, expect, it } from "vitest";

import { ACCESS_KEY_HEADER, AuthRequiredError, buildAuthHeaders, getAccessKey, saveAccessKey } from "./auth";

describe("auth", () => {
  it("stores the trimmed key and reads it back", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (key: string) => store.get(key) ?? null, setItem: (key: string, value: string) => void store.set(key, value) };
    saveAccessKey(storage, "  my-key  ");
    expect(getAccessKey(storage)).toBe("my-key");
  });

  it("survives missing or broken storage", () => {
    expect(getAccessKey(undefined)).toBeNull();
    expect(getAccessKey({ getItem: () => { throw new Error("blocked"); } })).toBeNull();
    expect(() => saveAccessKey({ setItem: () => { throw new Error("full"); } }, "k")).not.toThrow();
  });

  it("builds the header only with a key", () => {
    expect(buildAuthHeaders("k")).toEqual({ [ACCESS_KEY_HEADER]: "k" });
    expect(buildAuthHeaders(null)).toEqual({});
  });

  it("AuthRequiredError is recognisable", () => {
    expect(new AuthRequiredError()).toBeInstanceOf(Error);
    expect(new AuthRequiredError().name).toBe("AuthRequiredError");
  });
});
