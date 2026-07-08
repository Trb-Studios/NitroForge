import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { initApi } from "./api";
import "./index.css";

initApi();

// Report uncaught JS errors outside React's render tree too.
window.addEventListener("error", (e) => {
  import("./api").then(({ api }) =>
    api("/report/crash", {
      title: e.message,
      detail: `${e.filename}:${e.lineno}\n${e.error?.stack ?? ""}`,
      send: false,
    }).catch(() => {}),
  );
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
