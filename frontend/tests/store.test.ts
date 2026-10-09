import { describe, it, expect } from "vitest";
import { useApp } from "../src/store/app";

describe("app store", () => {
  it("logs in and out", () => {
    useApp.getState().login("t", { username: "a", name: "A", role: "administrator", permissions: [], home: "/" });
    expect(useApp.getState().user?.role).toBe("administrator");
    useApp.getState().logout();
    expect(useApp.getState().token).toBeNull();
  });
  it("switches facility", () => { useApp.getState().setFacility("government_hospital"); expect(useApp.getState().facility).toBe("government_hospital"); });
});
