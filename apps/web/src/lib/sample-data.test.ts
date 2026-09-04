import { describe, expect, it } from "vitest";
import { snapshots } from "./sample-data";

describe("sample snapshots", () => {
  it("contains all four agreed geographies", () => {
    expect(Object.keys(snapshots).sort()).toEqual(["CN", "GLOBAL", "JP", "US"]);
  });

  it("keeps scenario probabilities at 100 percent for every horizon", () => {
    for (const snapshot of Object.values(snapshots)) {
      expect(snapshot.scenarios.reduce((sum, item) => sum + item.oneYear, 0)).toBe(100);
      expect(snapshot.scenarios.reduce((sum, item) => sum + item.threeYear, 0)).toBe(100);
      expect(snapshot.scenarios.reduce((sum, item) => sum + item.longTerm, 0)).toBe(100);
    }
  });

  it("marks every initial snapshot as sample data", () => {
    expect(Object.values(snapshots).every((snapshot) => snapshot.isSample)).toBe(true);
  });
});
