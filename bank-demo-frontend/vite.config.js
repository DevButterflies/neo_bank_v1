import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The bank orchestrator (bank.orchestrator.main) serves everything on :8000.
// Point BANK_API_TARGET at it (defaults to localhost:8000, per the API doc).
const target = process.env.BANK_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['.trycloudflare.com'],
    port: 5173,
    proxy: {
      "/health": target,
      "/ready": target,
      "/governance": target,
      "/p1": target,
      "/p2": target,
      "/p3": target,
      "/p4": target,
      "/bilan": target,
    },
  },
});
