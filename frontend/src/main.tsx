import React from "react";
import ReactDOM from "react-dom/client";
import "@concavetrillion/pd-ui/theme/tokens.css";
import "@concavetrillion/pd-ui/theme/primitives.css";
import "./app.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
