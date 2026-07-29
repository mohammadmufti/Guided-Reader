import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // GitHub Pages serves from /<repo>/, so the app must know its prefix. The
  // data layer already reads import.meta.env.BASE_URL, so setting it here is
  // the only change a subpath deploy needs.
  base: process.env["BASE_PATH"] ?? "/",
  plugins: [react(), tailwindcss()],
  resolve: {
    // Must mirror `paths` in tsconfig.app.json. tsc resolves the alias on its
    // own, so a mismatch here typechecks cleanly and fails only at runtime.
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    // The pipeline writes into public/data/. Vite serves it as static files, so
    // the app fetches its corpus exactly the way it will in production.
    host: true,
  },
  build: {
    target: "es2022",
    sourcemap: true,
  },
});
