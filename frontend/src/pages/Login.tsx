import { FormEvent, useState } from "react";
import { Gauge } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { useApp } from "@/store/app";

const DEMO = [["admin", "admin123", "Administrator"], ["ops", "ops123", "Operations team"], ["green", "green123", "Sustainability officer"]];

export default function Login() {
  const { t } = useTranslation();
  const login = useApp((s) => s.login);
  const [u, setU] = useState("admin"), [p, setP] = useState("admin123"), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { const r = await api("/auth/login", { method: "POST", body: { username: u, password: p }, facility: false }); login(r.token, r.user); location.assign(r.user.home); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="grid min-h-full place-items-center p-4">
      <div className="w-full max-w-md">
        <div className="mb-5 flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-lg bg-brand text-brandfg"><Gauge /></div>
          <div><h1 className="text-xl font-semibold">EstateIQ</h1><p className="text-sm text-muted">Sustainability and operations intelligence for Indian campuses, hospitals and estates</p></div></div>
        <form onSubmit={submit} className="card space-y-3 p-5">
          <label className="block text-sm">Username<input className="input mt-1 w-full" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" required /></label>
          <label className="block text-sm">Password<input className="input mt-1 w-full" type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required /></label>
          {err && <p role="alert" className="text-sm text-bad">{err}</p>}
          <button className="btn btn-primary w-full justify-center" disabled={busy}>{busy ? "Signing in..." : t("signIn")}</button>
        </form>
        <div className="card mt-3 p-4 text-sm"><p className="mb-2 font-medium">Demo accounts (data is synthetic)</p>
          {DEMO.map(([a, b, r]) => <button key={a} className="mb-1 mr-2 rounded border border-line px-2 py-1 text-xs hover:bg-raised" onClick={() => { setU(a); setP(b); }}>{r}: {a} / {b}</button>)}</div>
      </div>
    </div>
  );
}
