import { defineConfig } from "@playwright/test";
export default defineConfig({ testDir: "e2e", use: { baseURL: process.env.E2E_URL || "http://localhost:3000" }, timeout: 60000 });
