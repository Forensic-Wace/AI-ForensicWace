import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API runs on :8080; in production nginx proxies /api.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
      "/healthz": "http://localhost:8080",
    },
  },
});
