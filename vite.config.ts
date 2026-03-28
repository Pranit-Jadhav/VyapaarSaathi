import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "frontend",
  base: "/web/",
  plugins: [react()],
  build: {
    outDir: "../web",
    emptyOutDir: true,
  },
});
