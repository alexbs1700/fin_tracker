import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";

import { reloadData, useSession } from "./api/client";
import ExtractsPanel from "./components/ExtractsPanel";
import { LoadingState } from "./components/ui";
import { AuthRequiredError, getBrowserStorage, saveAccessKey } from "./lib/auth";
import Movements from "./pages/Movements";
import Overview from "./pages/Overview";
import Portfolio from "./pages/Portfolio";
import Projections from "./pages/Projections";

import "./styles.css";

// Data only changes when new extracts are loaded, so avoid refetching on focus.
// A missing access key is not retried: it needs the user.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => !(error instanceof AuthRequiredError) && failureCount < 1,
    },
  },
});

const NAV_ITEMS = [
  { to: "/", label: "Resumen", icon: "◎", end: true },
  { to: "/movimientos", label: "Movimientos", icon: "⇅", end: false },
  { to: "/cartera", label: "Cartera", icon: "◔", end: false },
  { to: "/proyecciones", label: "Proyecciones", icon: "↗", end: false },
];

function ReloadButton() {
  const reload = async () => {
    await reloadData();
    await queryClient.invalidateQueries();
  };
  return (
    <button className="button" onClick={reload} title="Volver a leer los extractos de data/raw">
      <span className="desktop-only">Recargar datos</span>
      <span className="mobile-only" aria-label="Recargar datos">↻</span>
    </button>
  );
}

/** Shown on another device until the right access key is entered. */
function AccessKeyScreen() {
  const client = useQueryClient();
  const [accessKey, setAccessKey] = useState("");
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setIsChecking(true);
    saveAccessKey(getBrowserStorage(), accessKey);
    await client.resetQueries({ queryKey: ["session"] });
    const session = client.getQueryState(["session"]);
    setIsChecking(false);
    if (session?.status === "error") setError("Clave incorrecta");
  };

  return (
    <div className="access-screen">
      <form className="card access-card" onSubmit={submit}>
        <p className="brand">fin_tracker</p>
        <p className="secondary">Introduce la clave de acceso de tu Mac para ver tus datos.</p>
        <input
          type="password"
          autoComplete="current-password"
          placeholder="Clave de acceso"
          value={accessKey}
          onChange={(event) => setAccessKey(event.target.value)}
          autoFocus
        />
        {error && <p className="status-text critical">✕ {error}</p>}
        <button className="button button-primary" type="submit" disabled={!accessKey || isChecking}>
          {isChecking ? "Comprobando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}

function App() {
  const session = useSession();
  const [isExtractsPanelOpen, setIsExtractsPanelOpen] = useState(false);

  if (session.isLoading) return <LoadingState />;
  if (session.error instanceof AuthRequiredError) return <AccessKeyScreen />;

  return (
    <div className="app-shell">
      <nav className="top-nav">
        <span className="brand">fin_tracker</span>
        <div className="nav-links desktop-only">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>{item.label}</NavLink>
          ))}
        </div>
        <span className="nav-spacer" />
        <div className="nav-actions">
          <button className="button" onClick={() => setIsExtractsPanelOpen(true)}>
            <span className="desktop-only">Cargar extractos</span>
            <span className="mobile-only" aria-label="Cargar extractos">⇪</span>
          </button>
          <ReloadButton />
        </div>
      </nav>
      {isExtractsPanelOpen && <ExtractsPanel onClose={() => setIsExtractsPanelOpen(false)} />}
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/movimientos" element={<Movements />} />
        <Route path="/gastos" element={<Navigate to="/movimientos" replace />} />
        <Route path="/cartera" element={<Portfolio />} />
        <Route path="/proyecciones" element={<Projections />} />
      </Routes>
      <nav className="tab-bar mobile-only" aria-label="Secciones">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end}>
            <span className="tab-icon" aria-hidden="true">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
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
