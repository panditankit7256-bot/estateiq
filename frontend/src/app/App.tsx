import { lazy, Suspense, useEffect, ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useApp } from "@/store/app";
import { Layout, NAV } from "@/components/Layout";
import Login from "@/pages/Login";

const pages: Record<string, ReturnType<typeof lazy>> = {
  "/": lazy(() => import("@/pages/CommandCenter")), "/air": lazy(() => import("@/pages/Air")), "/energy": lazy(() => import("@/pages/Energy")),
  "/water": lazy(() => import("@/pages/Water")), "/waste": lazy(() => import("@/pages/Waste")), "/traffic": lazy(() => import("@/pages/Traffic")),
  "/assets": lazy(() => import("@/pages/Assets")), "/safety": lazy(() => import("@/pages/Safety")), "/emissions": lazy(() => import("@/pages/Emissions")),
  "/scorecard": lazy(() => import("@/pages/Scorecard")), "/scenarios": lazy(() => import("@/pages/Scenarios")), "/insights": lazy(() => import("@/pages/Insights")),
  "/settings": lazy(() => import("@/pages/Settings")),
};
const qc = new QueryClient();

function Shell() {
  const { user, theme, lang } = useApp();
  const { i18n } = useTranslation();
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => { i18n.changeLanguage(lang); document.documentElement.lang = lang; }, [lang, i18n]);
  useEffect(() => { const f = new URL(location.href).searchParams.get("f"); if (f) useApp.getState().setFacility(f); }, []);
  if (!user) return <Routes><Route path="*" element={<Login />} /></Routes>;
  const allowed = NAV.filter((n) => n.roles.includes(user.role));
  const guard = (to: string, el: ReactNode) => (allowed.some((n) => n.to === to) ? el : <Navigate to={user.home} replace />);
  return (
    <Layout>
      <Suspense fallback={<div className="p-6 text-muted" role="status">Loading page...</div>}>
        <Routes>
          {Object.entries(pages).map(([to, P]) => <Route key={to} path={to} element={guard(to, <P />)} />)}
          <Route path="*" element={<Navigate to={user.home} replace />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}

export default function App() {
  return <QueryClientProvider client={qc}><BrowserRouter><Shell /></BrowserRouter></QueryClientProvider>;
}
