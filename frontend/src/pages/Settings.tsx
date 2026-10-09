import { ChangeEvent, FormEvent, useState } from "react";
import { Card, PageHead, State, Table, Badge } from "@/components/ui";
import { api, useAct, useQ } from "@/lib/api";
import { useApp } from "@/store/app";
import { dt } from "@/lib/format";

const ASSUMPTIONS = [
  "All sensor data in this prototype is synthetic. It imitates Indian seasonal patterns (summer heat, monsoon, post-monsoon air quality), working calendars, power cuts and equipment wear.",
  "Air-quality categories use CPCB PM2.5 bands. Values are indicative and are not official AQI or health advice.",
  "Grid emission factor of 0.71 kg CO2/kWh and diesel 0.82 kg CO2/kWh are editable placeholders; use your utility's or CEA's current figure for reporting.",
  "Tariffs are examples (peak and off-peak slabs in INR/kWh). Replace them with your DISCOM tariff order.",
  "Forecasts use recent history only. They do not know about holidays, events, weather forecasts or equipment changes, and ranges are approximate.",
  "Anomaly detection and failure-risk models are trained and evaluated on synthetic faults that were injected on purpose; real-world accuracy will differ and needs local validation.",
  "Scenario results are closed-form estimates with the constants listed on the scenario page, not guarantees.",
  "Recommendations are decision-support. A person should confirm them before acting, especially on safety or health matters.",
];

export default function Settings() {
  const { user, facility } = useApp();
  const cfg = useQ<any>(`/facilities/${facility}`, undefined);
  const dq = useQ<any>("/data-quality");
  const audit = useQ<any>("/audit", undefined, user!.role === "administrator");
  const isAdmin = user!.role === "administrator";
  const [edit, setEdit] = useState<Record<string, Record<string, number>>>({});
  const save = useAct((body: any) => api(`/facilities/${facility}/config`, { method: "PUT", body, facility: false }), [`/facilities/${facility}`, "/overview", "/recommendations", "/scorecard", "/views/air"]);
  const up = useAct((f: File) => { const fd = new FormData(); fd.append("file", f); return api("/ingest/upload", { method: "POST", form: fd }); }, ["/overview", "/data-quality"]);
  const val = (s: string, k: string, base: number) => edit[s]?.[k] ?? base;
  const set = (s: string, k: string, v: string) => setEdit({ ...edit, [s]: { ...edit[s], [k]: Number(v) } });
  async function submit(e: FormEvent) { e.preventDefault(); await save.mutateAsync(edit); setEdit({}); }
  return (
    <>
      <PageHead title="Settings and assumptions" subtitle="What the numbers are based on, what you can change, and how healthy the data feed is." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Assumptions and limits"><ul className="list-disc space-y-1.5 pl-5 text-sm">{ASSUMPTIONS.map((a) => <li key={a}>{a}</li>)}</ul></Card>
        <Card title="Thresholds, tariffs and factors" caption={isAdmin ? "Changes apply to this facility straight away and are recorded in the audit log." : "Only administrators can change these values."}>
          <State q={cfg}>{cfg.data && <form onSubmit={submit} className="space-y-3">
            {(["thresholds", "tariff", "emission"] as const).map((s) => <fieldset key={s} className="grid grid-cols-2 gap-2 sm:grid-cols-3"><legend className="mb-1 text-sm font-medium capitalize">{s}</legend>
              {Object.entries<any>(cfg.data[s]).filter(([, v]) => typeof v === "number").map(([k, v]) => <label key={k} className="text-xs text-muted">{k.replace(/_/g, " ")}<input className="input mt-0.5 w-full" type="number" step="any" disabled={!isAdmin} value={val(s, k, v)} onChange={(e: ChangeEvent<HTMLInputElement>) => set(s, k, e.target.value)} /></label>)}</fieldset>)}
            {isAdmin && <div className="flex items-center gap-3"><button className="btn btn-primary" disabled={!Object.keys(edit).length || save.isPending}>Save changes</button>{save.isSuccess && <span className="text-sm text-ok">Saved. Analysis refreshed.</span>}{save.error && <span role="alert" className="text-sm text-bad">{save.error.message}</span>}</div>}
          </form>}</State>
        </Card>
        {user!.role !== "sustainability" && <Card title="Bring your own data" caption="Upload a CSV with columns ts, module, zone, entity, metric, value. Each row is range-checked and de-duplicated. Modules: air, energy, water, waste, traffic, assets.">
          <input type="file" accept=".csv" aria-label="CSV file" onChange={(e) => e.target.files?.[0] && up.mutate(e.target.files[0])} />
          {up.isPending && <p className="mt-2 text-sm text-muted">Checking and importing...</p>}
          {up.data && <p className="mt-2 text-sm">Accepted {(up.data as any).accepted} rows, rejected {(up.data as any).rejected}.{(up.data as any).errors.slice(0, 3).map((x: any, i: number) => <span key={i} className="block text-muted">Row {x.row}: {x.reason}</span>)}</p>}
          {up.error && <p role="alert" className="mt-2 text-sm text-bad">{up.error.message}</p>}
        </Card>}
        {isAdmin && <Card title="Audit trail" caption="Recommendations, status changes, configuration edits and data imports."><State q={audit}><div className="max-h-64 overflow-auto"><Table head={["When", "Who", "Event", "Detail"]} rows={(audit.data ?? []).slice(0, 25).map((r: any) => [dt(r.ts), r.actor, r.event, <span key={r.ts + r.detail} className="line-clamp-2 break-all text-xs text-muted">{r.detail.slice(0, 140)}</span>])} /></div></State></Card>}
      </div>
      <Card className="mt-4" title="Data quality" caption="Completeness over the last 14 days and the time of the latest reading per sensor.">
        <State q={dq}>{dq.data && <>
          <p className="mb-2 text-sm">{dq.data.summary.sensors} sensors, average completeness {dq.data.summary.avg_completeness_pct}%, {dq.data.summary.faulty} with a stuck-sensor event.</p>
          <div className="max-h-72 overflow-auto"><Table head={["Sensor", "Module", "Metric", "Completeness", "Last reading", "Status"]} rows={dq.data.sensors.map((s: any) => [s.entity, s.module, s.metric, `${s.completeness_pct}%`, dt(s.last_update), s.sensor_faults_14d ? <Badge key={s.entity + s.metric} tone="High">Stuck value seen</Badge> : s.completeness_pct < 95 ? <Badge key={s.entity + s.metric} tone="Medium">Gaps</Badge> : <Badge key={s.entity + s.metric} tone="ok">Healthy</Badge>])} /></div>
        </>}</State>
      </Card>
    </>
  );
}
