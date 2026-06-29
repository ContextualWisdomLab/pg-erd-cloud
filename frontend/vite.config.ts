import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { type UserConfig } from "vitest/node";

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true
  },
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
    },
  },
} as UserConfig);
