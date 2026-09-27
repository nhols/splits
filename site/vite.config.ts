import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Set BASE_PATH when serving from a sub-path, e.g. BASE_PATH=/splits/ for GitHub Pages.
export default defineConfig({
  base: process.env.BASE_PATH ?? "/",
  plugins: [react()],
});
