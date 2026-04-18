import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/__tests__/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html", "lcov"],
      reportsDirectory: "./coverage",
      include: [
        "components/**/*.{ts,tsx}",
        "lib/**/*.{ts,tsx}",
        "app/**/*.{ts,tsx}",
        "!**/*.d.ts",
        "!**/index.ts",
        "!**/__tests__/**",
        "!**/node_modules/**",
      ],
      exclude: [
        "components/ui/**",
        "**/*.stories.{ts,tsx}",
        "**/*.config.{ts,tsx}",
        "**/types.ts",
      ],
      thresholds: {
        branches: 60,
        functions: 60,
        lines: 60,
        statements: 60,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
