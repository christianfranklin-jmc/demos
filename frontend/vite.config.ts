import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Proxy /api/chat to Anthropic API — keeps the key server-side
      "/api/chat": {
        target: "https://api.anthropic.com",
        changeOrigin: true,
        rewrite: (path) => "/v1/messages",
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
});
