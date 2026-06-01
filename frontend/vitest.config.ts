// Vitest config kept separate from vite.config.ts — vitest 2.x bundles its
// own Vite which collides with the project's Vite 7 typings if we put a
// `test` block on the shared config. Runtime behaviour is identical to
// inlining; this just keeps tsc -b happy.
//
// We intentionally do NOT load `@vitejs/plugin-react` here: the plugin is
// typed against the project's Vite 7 and re-introduces the type-collision
// we're avoiding. Vitest's esbuild transform handles `.tsx` JSX out of the
// box, which is sufficient for unit + Testing-Library tests.
import path from "path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "react/jsx-runtime": path.resolve(
        __dirname,
        "./node_modules/react/jsx-runtime.js",
      ),
      "react/jsx-dev-runtime": path.resolve(
        __dirname,
        "./src/jsx-dev-runtime-shim.ts",
      ),
      react: path.resolve(__dirname, "./node_modules/react"),
      "react-dom": path.resolve(__dirname, "./node_modules/react-dom"),
      "react-konva": path.resolve(__dirname, "./node_modules/react-konva"),
    },
    dedupe: ["react", "react-dom", "react-konva"],
  },
  test: {
    deps: {
      inline: [/@pdomain\/pdomain-ui/],
    },
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
  esbuild: {
    // React 19's automatic JSX runtime — no `import React` needed in tests.
    jsx: "automatic",
  },
});
