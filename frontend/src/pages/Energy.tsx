import { useMemo, useState } from "react";
import { Card, Kpi, PageHead, State, Table } from "@/components/ui";
import { Chart, palette } from "@/components/Chart";
import { ForecastCard } from "@/components/Forecast";
import { AnomalyList } from "@/components/Anomalies";
import { useQ } from "@/lib/api";
import { useApp } from "@/store/app";
import { bar, catChart, line } from "@/lib/charts";
import { inr, num, day, hour } from "@/lib/format";

export default function Energy() {
  const days = useApp((s) => s.days);
  const [hz, setHz] = useState(168);
  const v = useQ<any>("/views/energy", { days: Math.max(days, 7) });
  const opt = useMemo(() => { const d = v.data?.daily; if (!d) return {}; const p = palette();
    return catChart(d.ts.map(day), [bar("Grid", d.grid, { stack: "e", color: p.info }), bar("Solar", d.solar, { stack: "e", color: p.warn }), bar("Diesel generator", d.dg, { stack: "e", color: p.bad }),
      line("Grid cost (₹)", d.cost, { yAxisIndex: 1, color: p.ink })], { yAxis: [{ type: "value", name: "kWh", splitLine: { lineStyle: { color: p.line, opacity: 0.6 } } }, { type: "value", name: "₹", splitLine: { show: false } }] }); }, [v.data]);
  const prof = useMemo(() => v.data ? catChart(Array.from({ length: 24 }, (_, h) => hour(h)), [bar("Average kWh", v.data.hourly_profile, { color: palette().brand })]) : {}, [v.data]);
  const zones = useMemo(() => v.data ? { ...catChart(v.data.zones.map((z: any) => z.name), [bar("kWh", v.data.zones.map((z: any) => z.kwh), { color: palette().info })]), xAxis: { type: "category", data: v.data.zones.map((z: any) => z.name), axisLabel: { interval: 0, rotate: 20, color: palette().muted } } } : {}, [v.data]);
  return (
    <>
      <PageHead title="Energy" subtitle="Load, cost, solar and diesel use, peak-hour exposure and ways to cut the bill." />
      <State q={v}>{v.data && <>
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Kpi label="Energy used" value={num(v.data.total_kwh)} unit="kWh" note={`last ${v.data.days} days`} />
          <Kpi label="Grid cost" value={inr(v.data.cost_inr)} />
          <Kpi label="Peak demand" value={num(v.data.peak_demand_kw)} unit="kW" />
          <Kpi label="Solar share" value={num(v.data.solar_share_pct, 1)} unit="%" />
          <Kpi label="Peak-hour share" value={num(v.data.peak_window_share_pct, 1)} unit="%" note="of grid energy" tone={v.data.peak_window_share_pct > 15 ? "warn" : undefined} />
          <Kpi label="Diesel generator" value={v.data.dg_hours} unit="h" note={`${v.data.dg_share_pct}% of energy`} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Daily energy and cost" caption="Bars show where energy came from. Grid energy is what you pay for."><Chart option={opt} label="Daily energy by source and grid cost" /></Card>
          <Card title="A typical day" caption="Average load by hour. The tariff peak window is where each kWh costs the most."><Chart option={prof} label="Average load by hour of day" /></Card>
          <Card title="Last 7 days vs normal" caption="Compared with the same hours and weekdays earlier in the 90-day history.">
            <p className="text-3xl font-semibold tabular-nums">{v.data.last7_vs_baseline_pct == null ? "-" : `${v.data.last7_vs_baseline_pct >= 0 ? "+" : ""}${v.data.last7_vs_baseline_pct}%`}</p>
            <div className="mt-3 rounded-md bg-brand/10 p-3 text-sm"><b>Load-shifting opportunity: </b>about {num(v.data.shift.shiftable_kwh_per_day)} kWh per day could move off-peak, saving roughly {inr(v.data.shift.saving_inr_per_month)} a month. <span className="text-muted">{v.data.shift.assumption}</span></div>
          </Card>
          <Card title="Where the energy goes" caption="Total kWh by zone in this window."><Chart option={zones} label="Energy by zone" /></Card>
        </div>
      </>}</State>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div><div className="mb-2 flex gap-2 text-sm">{[24, 168].map((h) => <button key={h} className={`btn ${hz === h ? "btn-primary" : ""}`} onClick={() => setHz(h)}>{h === 24 ? "Next 24 hours" : "Next 7 days"}</button>)}</div>
          <ForecastCard module="energy" metric="kwh" horizon={hz} title="Energy forecast (whole site)" /></div>
        <AnomalyList module="energy" days={Math.min(days, 30)} title="Abnormal loads" />
      </div>
      <div className="hidden"><Table head={[]} rows={[]} /></div>
    </>
  );
}
