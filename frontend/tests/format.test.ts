import { describe, it, expect } from "vitest";
import { inr, num, hour, compact } from "../src/lib/format";

describe("formatters", () => {
  it("formats rupees with Indian digit grouping", () => expect(inr(1234567)).toBe("₹12,34,567"));
  it("handles missing numbers", () => { expect(num(null)).toBe("-"); expect(inr(undefined)).toBe("-"); });
  it("pads hours", () => expect(hour(7)).toBe("07:00"));
  it("compacts large values", () => expect(compact(250000)).toBe("2.5 lakh"));
});
