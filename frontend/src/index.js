import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// Emergent's preview logger (forwards console/network data to the preview
// panel). Development only — never ship it to the hosted site.
if (process.env.NODE_ENV !== "production") {
  const s = document.createElement("script");
  s.src = "https://assets.emergent.sh/scripts/emergent-main.js";
  document.head.appendChild(s);
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
