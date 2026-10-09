import { useEffect, useState } from "react";
import { Card, Kpi, PageHead, Table } from "@/components/ui";
import { api, useAct } from "@/lib/api";
import { inr, num } from "@/lib/format";
import { useApp } from "@/store/app";

const INIT = { add_solar_kw: 0, ac_setpoint_delta_c: 0, shift_peak_pct: 0, extra_collections_per_week: 0, fix_leak: false, occupancy_change_pct: 0 };
const SL: [keyof typeof INIT, string, number, number, number, string][] = [
  ["add_solar_kw", "Add rooftop solar", 0, 500, 25, "kW"], ["ac_setpoint_delta_c", "Raise AC setpoint", 0, 4, 0.5, "°C"], ["shift_peak_pct", "Move peak-hour load off-peak", 0, 50, 5, "%"],
  ["extra_collections_per_week", "Extra waste collections", 0, 7, 1, "per week"], ["occupancy_change_pct", "Change in occupancy", -30, 50, 5, "%"]];

export default function Scenarios() {
  const facility = useApp((s) => s.facility);
  const [p, setP] = useState({ ...INIT });
  const sim = useAct((body: typeof INIT) => api("/scenarios/simulate", { method: "POST", body }));
  useEffect(() => { const t = setTimeout(() => sim.mutate(p), 250); return () => clearTimeout(t); /* eslint-disable-next-line */ }, [p, facility]);
  const r: any = sim.data;
  const rows = r ? [["Energy per day (kWh)", r.baseline.kwh_day, r.scenario.kwh_day], ["Grid cost per day (₹)", r.baseline.cost_inr_day, r.scenario.cost_inr_day], ["CO2 per day (kg)", r.baseline.co2_kg_day, r.scenario.co2_kg_day],
    ["Water per day (kL)", r.baseline.water_kl_day, r.scenario.water_kl_day], ["Overflow bin-hours per week", r.baseline.overflow_bin_hours_week, r.scenario.overflow_bin_hours_week]] : [];
  return (
    <>
      <PageHead title="Scenario simulator" subtitle="Try a change and see the estimated effect on cost, energy, emissions, water and waste before committing money." right={<button className="btn" onClick={() => setP({ ...INIT })}>Reset</button>} />
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-2" title="Your changes">
          <div className="space-y-4">{SL.map(([k, label, min, max, step, unit]) => (
            <label key={k} className="block text-sm"><div className="flex justify-between"><span>{label}</span><b className="tabular-nums">{p[k] as number} {unit}</b></div>
              <input className="w-full accent-[rgb(var(--brand))]" type="range" min={min} max={max} step={step} value={p[k] as number} onChange={(e) => setP({ ...p, [k]: Number(e.target.value) })} /></label>))}
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={p.fix_leak} onChange={(e) => setP({ ...p, fix_leak: e.target.checked })} />Fix the leak detected on the Water page</label>
          </div>
        </Card>
        <div className="space-y-4 lg:col-span-3">
          {sim.error && <p role="alert" className="text-bad">{sim.error.message}</p>}
          {r && <>
            <div className="grid gap-3 sm:grid-cols-4">
              <Kpi label="Money saved per month" value={inr(r.monthly.cost_saving_inr)} tone={r.monthly.cost_saving_inr > 0 ? "ok" : undefined} />
              <Kpi label="Energy saved per month" value={num(r.monthly.kwh_saving)} unit="kWh" />
              <Kpi label="CO2 avoided per month" value={num(r.monthly.co2_saving_kg)} unit="kg" />
              <Kpi label="Water saved per month" value={num(r.monthly.water_saving_kl)} unit="kL" />
            </div>
            <Card title="Before and after" caption="Baseline is the last 30 days of facility data."><Table head={["Measure", "Now", "With changes", "Change"]} rows={rows.map(([n, a, b]: any) => [n, num(a, 1), num(b, 1), <span key={n} className={b < a ? "text-ok" : b > a ? "text-bad" : "text-muted"}>{b === a ? "No change" : `${b > a ? "+" : ""}${num(b - a, 1)}`}</span>])} /></Card>
            <Card title="Assumptions behind these numbers"><ul className="list-disc space-y-1 pl-5 text-sm text-muted">{r.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul></Card>
          </>}
        </div>
      </div>
    </>
  );
}
