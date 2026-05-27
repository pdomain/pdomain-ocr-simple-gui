import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Workaround: @pdomain/pdomain-ui ships its dist with jsxDEV (development
  // JSX transform).  React 19's production jsx-dev-runtime stubs jsxDEV as
  // void 0, which crashes the app at runtime ("jsxDEV is not a function").
  // This shim forwards jsxDEV → production jsx so library dist code works in
  // production bundles.  Remove once pdomain-ui is rebuilt with the production
  // jsx-runtime (jsx/jsxs instead of jsxDEV).
  resolve: {
    alias: {
      "react/jsx-dev-runtime": resolve(__dirname, "shims/jsx-dev-runtime.ts"),
    },
  },
  build: {
    outDir: resolve(__dirname, "../src/pdomain_ocr_simple_gui/frontend"),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8004",
        changeOrigin: true,
      },
    },
  },
});
