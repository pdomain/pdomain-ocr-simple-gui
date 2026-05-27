// jsx-dev-runtime.ts — workaround shim
//
// @pdomain/pdomain-ui ships its dist with jsxDEV (development JSX transform).
// React 19's production jsx-dev-runtime stubs jsxDEV as void 0, which crashes
// the app at runtime ("jsxDEV is not a function").  This shim forwards jsxDEV
// → production jsx so library dist code works in production bundles.
//
// Aliased in vite.config.ts: "react/jsx-dev-runtime" → this file.
// Remove once pdomain-ui is rebuilt with the production jsx-runtime
// (jsx/jsxs instead of jsxDEV).
export { jsx as jsxDEV, jsxs, Fragment } from "react/jsx-runtime";
