import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initApi } from "./api";
import "./index.css";

initApi();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
