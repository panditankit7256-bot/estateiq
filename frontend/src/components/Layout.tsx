import { ReactNode, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Gauge, Wind, Zap, Droplets, Trash2, Car, Wrench, ShieldAlert, Leaf, Award, SlidersHorizontal, Lightbulb, Settings, Menu, Moon, Sun, LogOut, Bell, Radio } from "lucide-react";
import { useApp, Role } from "@/store/app";
import { useQ } from "@/lib/api";

interface Item { to: string; key: string; icon: ReactNode; roles: Role[] }
const A: Role = "administrator", O: Role = "operations", S: Role = "sustainability";
export const NAV: Item[] = [
  { to: "/", key: "command", icon: <Gauge size={16} />, roles: [A, O, S] },
  { to: "/air", key: "air", icon: <Wind size={16} />, roles: [A, O, S] },
  { to: "/energy", key: "energy", icon: <Zap size={16} />, roles: [A, S] },
  { to: "/water", key: "water", icon: <Droplets size={16} />, roles: [A, O, S] },
  { to: "/waste", key: "waste", icon: <Trash2 size={16} />, roles: [A, O] },
  { to: "/traffic", key: "traffic", icon: <Car size={16} />, roles: [A, O] },
  { to: "/assets", key: "assets", icon: <Wrench size={16} />, roles: [A, O] },
  { to: "/safety", key: "safety", icon: <ShieldAlert size={16} />, roles: [A, O] },
  { to: "/emissions", key: "emissions", icon: <Leaf size={16} />, roles: [A, S] },
  { to: "/scorecard", key: "scorecard", icon: <Award size={16} />, roles: [A, S] },
  { to: "/scenarios", key: "scenarios", icon: <SlidersHorizontal size={16} />, roles: [A, S, O] },
  { to: "/insights", key: "insights", icon: <Lightbulb size={16} />, roles: [A, O, S] },
  { to: "/settings", key: "settings", icon: <Settings size={16} />, roles: [A, O, S] },
];

function useLive() {
  const token = useApp((s) => s.token);
  const qc = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);
  const [online, setOnline] = useState(false);
  useEffect(() => {
    if (!token) return;
    let ws: WebSocket | null = null, stop = false, retry: number;
    const open = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v1/ws/live?token=${token}`);
      ws.onopen = () => setOnline(true);
      ws.onclose = () => { setOnline(false); if (!stop) retry = window.setTimeout(open, 4000); };
      ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.type === "data_update") { setMsg(m.message); qc.invalidateQueries(); window.setTimeout(() => setMsg(null), 9000); } };
    };
    open();
    return () => { stop = true; clearTimeout(retry); ws?.close(); };
  }, [token, qc]);
  return { msg, online };
}

export function Layout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { user, facility, setFacility, days, setDays, theme, setTheme, lang, setLang, logout } = useApp();
  const [menu, setMenu] = useState(false);
  const loc = useLocation();
  const live = useLive();
  const facs = useQ<{ id: string; name: string }[]>("/facilities");
  const ov = useQ<any>("/overview");
  useEffect(() => setMenu(false), [loc.pathname]);
  useEffect(() => { const u = new URL(location.href); u.searchParams.set("f", facility); history.replaceState(null, "", u); }, [facility, loc.pathname]);
  const alerts = ov.data?.kpis.active_alerts ?? 0;
  const items = NAV.filter((n) => n.roles.includes(user!.role));
  return (
    <div className="flex min-h-full">
      <aside className={`${menu ? "fixed inset-0 z-30 flex" : "hidden"} w-64 shrink-0 flex-col bg-rail p-3 text-railfg lg:sticky lg:top-0 lg:flex lg:h-screen`} aria-label="Main navigation">
        <div className="mb-4 flex items-center gap-2 px-2 pt-1"><div className="grid h-8 w-8 place-items-center rounded-md bg-brand text-brandfg"><Gauge size={18} /></div><div><div className="font-semibold leading-tight text-white">EstateIQ</div><div className="text-xs opacity-70">Facility intelligence, India</div></div></div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} className={({ isActive }) => `flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm ${isActive ? "bg-white/12 font-medium text-white" : "hover:bg-white/8"}`}>
              {n.icon}{t(`nav.${n.key}`)}
            </NavLink>))}
        </nav>
        <div className="mt-2 rounded-md bg-white/8 p-2.5 text-xs"><div className="font-medium text-white">{user!.name}</div><div className="opacity-70">{user!.role === "administrator" ? "Administrator" : user!.role === "operations" ? "Operations team" : "Sustainability officer"}</div></div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-line bg-surface/95 px-4 py-2 backdrop-blur">
          <button className="btn lg:hidden" onClick={() => setMenu(!menu)} aria-label="Open menu"><Menu size={16} /></button>
          <label className="flex items-center gap-2 text-sm"><span className="text-muted">{t("facility")}</span>
            <select className="input max-w-[16rem]" value={facility} onChange={(e) => setFacility(e.target.value)}>{facs.data?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
          <label className="flex items-center gap-2 text-sm"><span className="text-muted">{t("window")}</span>
            <select className="input" value={days} onChange={(e) => setDays(Number(e.target.value))}>{[3, 7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>{d} {t("days")}</option>)}</select></label>
          <div className="ml-auto flex items-center gap-1.5">
            <span className={`mr-1 inline-flex items-center gap-1 text-xs ${live.online ? "text-ok" : "text-muted"}`} title="Live feed"><Radio size={12} />{live.online ? "Live" : "Offline"}</span>
            <NavLink to="/insights" className="btn relative" aria-label={`${alerts} active alerts`}><Bell size={15} />{alerts > 0 && <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-bad px-1 text-[10px] text-white">{alerts}</span>}</NavLink>
            <button className="btn" onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label="Switch language">{lang === "en" ? "हिन्दी" : "English"}</button>
            <button className="btn" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label="Toggle dark mode">{theme === "light" ? <Moon size={15} /> : <Sun size={15} />}</button>
            <button className="btn" onClick={logout}><LogOut size={15} />{t("signOut")}</button>
          </div>
        </header>
        {live.msg && <div role="status" className="border-b border-line bg-brand/10 px-4 py-2 text-sm">New simulated data arrived: {live.msg}. Charts and recommendations are refreshing.</div>}
        <main className="mx-auto max-w-[1280px] p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
