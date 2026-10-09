import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Served from https://<user>.github.io/game-garden/
export default defineConfig({
  base: "/game-garden/",
  plugins: [react()],
});
