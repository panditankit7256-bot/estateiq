import { useMemo } from "react";
import { Card, Kpi, PageHead, State, Table, Badge, Bar } from "@/components/ui";
import { Chart, palette } from "@/components/Chart";
import { AnomalyList } from "@/components/Anomalies";
import { useQ } from "@/lib/api";
import { useApp } from "@/store/app";
import { line, pairs, timeChart } from "@/lib/charts";
import { num } from "@/lib/format";

export default function Water() {
  const days = useApp((s) => s.days);
  const v = useQ<any>("/views/water"), m = useQ<any>("/metrics/water", { metric: "flow_kl", days, granularity: days > 14 ? "d" : "h" });
  const opt = useMemo(() => m.data && v.data ? timeChart(Object.entries<any>(m.data.series).map(([z, d]) => line(v.data.zones.find((x: any) => x.zone === z)?.name ?? z, pairs(m.data.ts, d))), { yAxis: { type: "value", name: m.data.agg === "sum" && days > 14 ? "kL/day" : "kL/h" } }) : {}, [m.data, v.data, days]);
  const tank = useMemo(() => v.data ? timeChart([line("Tank level forecast", pairs(v.data.tank_forecast.ts, v.data.tank_forecast.yhat), { color: palette().brand }),
    line("Low", pairs(v.data.tank_forecast.ts, v.data.tank_forecast.lo), { lineStyle: { opacity: 0.25 }, color: palette().muted }), line("High", pairs(v.data.tank_forecast.ts, v.data.tank_forecast.hi), { lineStyle: { opacity: 0.25 }, color: palette().muted })], { yAxis: { type: "value", name: "%", min: 0, max: 100 } }) : {}, [v.data]);
  return (
    <>
      <PageHead title="Water" subtitle="Consumption by zone, per-person use against a benchmark, and leak watch based on flow when the area should be quiet." />
      <State q={v}>{v.data && <>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Kpi label="Use per person per day" value={num(v.data.lpcd)} unit="litres" note={`Benchmark ${v.data.benchmark_lpcd} (configurable)`} tone={v.data.lpcd > 1.15 * v.data.benchmark_lpcd ? "warn" : "ok"} />
          <Kpi label="Average daily use" value={num(v.data.kl_per_day)} unit="kL" note={`Budget ${num(v.data.budget_kl_per_day)} kL`} />
          <Kpi label="Rainwater harvesting potential" value={num(v.data.rainwater_harvest_kl_per_year)} unit="kL/year" note="indicative" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Leak watch" caption="Compares small-hours flow (1 to 5 am) in the last 3 nights with the zone's earlier normal. Continuous extra flow when the area is empty suggests a leak.">
            <Table head={["Zone", "Use (kL/day)", "Small-hours change", "Possible excess", "Status"]} rows={v.data.zones.map((z: any) => [z.name, num(z.kl_per_day, 1), `${z.night_change_pct >= 0 ? "+" : ""}${z.night_change_pct}%`, `${z.excess_kl_per_day} kL/day`, z.leak_suspect ? <Badge key={z.zone} tone="Critical">Check for leak</Badge> : <Badge key={z.zone} tone="ok">Normal</Badge>])} />
            <div className="mt-2"><Bar value={v.data.lpcd} max={Math.max(v.data.benchmark_lpcd * 1.6, v.data.lpcd)} tone={v.data.lpcd > v.data.benchmark_lpcd ? "warn" : "brand"} /></div>
            <p className="mt-1 text-xs text-muted">{v.data.rwh_assumption}</p>
          </Card>
          <Card title="Overhead tank, next 24 hours" caption="Forecast tank level with a rough range. Low points show when pumping may need to start earlier."><Chart option={tank} label="Tank level forecast" /></Card>
        </div>
      </>}</State>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Flow by zone"><State q={m}><Chart option={opt} label="Water flow by zone" /></State></Card>
        <AnomalyList module="water" days={Math.min(days, 30)} title="Unusual flow" />
      </div>
    </>
  );
}
