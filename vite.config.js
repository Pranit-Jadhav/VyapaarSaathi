import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  root: "frontend",
  base: mode === "development" ? "/" : "/web/",
  build: {
    outDir: "../web",
    emptyOutDir: true
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/record": "http://127.0.0.1:8000",
      "/entries": "http://127.0.0.1:8000",
      "/insights": "http://127.0.0.1:8000",
      "/suggestions": "http://127.0.0.1:8000",
      "/score": "http://127.0.0.1:8000",
      "/pdf": "http://127.0.0.1:8000",
      "/confirm": "http://127.0.0.1:8000"
    }
  }
}));
