import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";

import ExtractsPanel from "./components/ExtractsPanel";
import Overview from "./pages/Overview";
import Portfolio from "./pages/Portfolio";
import Spending from "./pages/Spending";
import "./styles.css";

// Data only changes when new extracts are loaded, so avoid refetching on focus
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, refetchOnWindowFocus: false, retry: 1 } },
});

function ReloadButton() {
  const reload = async () => {
    await fetch("/api/reload", { method: "POST" });
    await queryClient.invalidateQueries();
  };
  return (
    <button className="button" onClick={reload} title="Volver a leer los extractos de data/raw">
      Recargar datos
    </button>
  );
}

function App() {
  const [isExtractsPanelOpen, setIsExtractsPanelOpen] = useState(false);
  return (
    <div className="app-shell">
      <nav className="top-nav">
        <span className="brand">fin_tracker</span>
        <div className="nav-links">
          <NavLink to="/" end>Resumen</NavLink>
          <NavLink to="/gastos">Gastos</NavLink>
          <NavLink to="/cartera">Cartera</NavLink>
        </div>
        <span className="nav-spacer" />
        <div className="nav-actions">
          <button className="button" onClick={() => setIsExtractsPanelOpen(true)}>
            Cargar extractos
          </button>
          <ReloadButton />
        </div>
      </nav>
      {isExtractsPanelOpen && <ExtractsPanel onClose={() => setIsExtractsPanelOpen(false)} />}
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/gastos" element={<Spending />} />
        <Route path="/cartera" element={<Portfolio />} />
      </Routes>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
