import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: { port: 5173, proxy: { "/api": { target: process.env.VITE_API_TARGET || "http://localhost:8000", changeOrigin: true, ws: true } } },
  build: { chunkSizeWarningLimit: 900, rollupOptions: { output: { manualChunks: { echarts: ["echarts/core", "echarts/charts", "echarts/components", "echarts/renderers"], react: ["react", "react-dom", "react-router-dom"] } } } },
  test: { environment: "jsdom", globals: true, exclude: ["e2e/**", "node_modules/**"] },
});
