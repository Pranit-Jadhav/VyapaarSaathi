import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API paths that should be proxied to the FastAPI backend.
// Some of these (/record, /insights) also exist as frontend page routes.
// The bypass function ensures browser page navigations (Accept: text/html)
// are served by Vite (SPA), while API calls (fetch/XHR) are proxied.
const apiPaths = ["/health", "/record", "/entries", "/insights", "/suggestions", "/score", "/pdf", "/confirm", "/inventory", "/webhook", "/api/report", "/ai-insights"];

function makeProxyEntry(target) {
  return {
    target,
    // Skip proxy for browser navigations — let Vite serve the SPA instead.
    // This prevents "405 Method Not Allowed" when navigating to /record or /insights.
    bypass(req) {
      const accept = req.headers.accept || "";
      if (accept.includes("text/html")) {
        // Return the URL unchanged so Vite serves index.html (SPA fallback)
        return req.url;
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const proxy = {};
  for (const path of apiPaths) {
    proxy[path] = makeProxyEntry("http://127.0.0.1:8000");
  }

  return {
    plugins: [react()],
    root: "frontend",
    base: mode === "development" ? "/" : "/web/",
    build: {
      outDir: "../web",
      emptyOutDir: true,
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy,
    },
  };
});
