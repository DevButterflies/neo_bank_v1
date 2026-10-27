import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // Served by the orchestrator under /app/ so client routes (/bilan, /governance)
  // never collide with the API paths of the same name.
  base: "/app/",
  plugins: [react()],
  server: { port: 5173 },
});
