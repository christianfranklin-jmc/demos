/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Legacy /api/chat proxy from DSA's claude.ts (deleted in T007).
      // Kept harmless; remove once no reference remains.
      "/api/chat": {
        target: "https://api.anthropic.com",
        changeOrigin: true,
        rewrite: () => "/v1/messages",
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq) => {
            const apiKey = process.env.VITE_ANTHROPIC_API_KEY;
            if (apiKey) {
              proxyReq.setHeader("x-api-key", apiKey);
              proxyReq.setHeader("anthropic-version", "2023-06-01");
            }
          });
        },
      },
    },
  },
  // Allow importing .md files as raw strings for system prompts
  assetsInclude: ["**/*.md"],
  test: {
    environment: "jsdom",
    globals: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
