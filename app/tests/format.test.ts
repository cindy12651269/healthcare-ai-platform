import { describe, expect, it } from "vitest";
import { formatStaffDateTime, intakeRef } from "../services/format";

// #84: readable intake references must stay distinct for seeded (non-hash) ids
describe("intakeRef", () => {
  it.each([
    ["demo-intake-a1", "#demo-intake-a1"],
    ["demo-intake-b2", "#demo-intake-b2"],
    ["2f005d14d0fc4de1acc4879d586481a3", "#2f005d14"], // 32-hex record id
    ["2F005D14D0FC4DE1ACC4879D586481A3", "#2F005D14"],
    ["cbb5b0d0-78a0-477d-b00e-1ca6d4e28a42", "#cbb5b0d0"], // hyphenated UUID
  ])("%s -> %s", (id, ref) => {
    expect(intakeRef(id)).toBe(ref);
  });

  it("gives every seeded intake a distinct reference", () => {
    const seeded = ["a1", "a2", "a3", "a4", "b1", "b2", "b3", "b4"].map((s) => `demo-intake-${s}`);
    expect(new Set(seeded.map(intakeRef)).size).toBe(seeded.length);
  });

  it("does not shorten ids that only look partly like hashes", () => {
    expect(intakeRef("2f005d14")).toBe("#2f005d14"); // too short to be a hash: shown in full
    expect(intakeRef("2f005d14d0fc4de1acc4879d586481a3x")).toBe("#2f005d14d0fc4de1acc4879d586481a3x");
  });
});

describe("formatStaffDateTime", () => {
  it("is explicit UTC en-US and passes through missing or unparseable values", () => {
    expect(formatStaffDateTime("2026-10-15T12:29:37.508070Z")).toBe("Oct 15, 2026, 12:29 UTC");
    expect(formatStaffDateTime(null)).toBe("—");
    expect(formatStaffDateTime("not a date")).toBe("not a date");
  });
});
