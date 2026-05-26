import React from "react";
import ReactDOM from "react-dom/client";
import "@pdomain/pdomain-ui/theme/tokens.css";
import "@pdomain/pdomain-ui/theme/primitives.css";
import "./app.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
