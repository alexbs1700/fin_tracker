import { describe, expect, it } from "vitest";

import { labelAccount, labelAssetBucket, labelWallet } from "./labels";

describe("labels", () => {
  it("labelAccount falls back to the identifier", () => {
    expect(labelAccount("trade_republic")).toBe("Trade Republic");
    expect(labelAccount("other")).toBe("other");
  });

  it("labelWallet", () => {
    expect(labelWallet("bbva", null)).toBe("BBVA");
    expect(labelWallet("trade_republic", "cash")).toBe("Trade Republic · Efectivo");
    expect(labelWallet("revolut", "Cuenta personal (EUR)")).toBe("Revolut · Cuenta personal (EUR)");
  });

  it("labelAssetBucket", () => {
    expect(labelAssetBucket("fixed_income")).toBe("Renta fija");
    expect(labelAssetBucket("crypto")).toBe("crypto");
  });
});
