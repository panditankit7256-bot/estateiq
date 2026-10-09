import { useMemo } from "react";
import { Card, Kpi, PageHead, State, Table, Badge } from "@/components/ui";
import { Chart } from "@/components/Chart";
import { SitePlan } from "@/components/SitePlan";
import { ForecastCard } from "@/components/Forecast";
import { AnomalyList } from "@/components/Anomalies";
import { useQ } from "@/lib/api";
import { useApp } from "@/store/app";
import { line, pairs, threshold, timeChart } from "@/lib/charts";
import { num } from "@/lib/format";

export default function Air() {
  const days = useApp((s) => s.days);
  const v = useQ<any>("/views/air"), m = useQ<any>("/metrics/air", { metric: "pm25", days, granularity: days > 14 ? "d" : "h" });
  const opt = useMemo(() => m.data && v.data ? timeChart(Object.entries<any>(m.data.series).map(([z, d]) => line(v.data.zones.find((x: any) => x.zone === z)?.name ?? z, pairs(m.data.ts, d))),
    { yAxis: { type: "value", name: "µg/m³" }, series: Object.entries<any>(m.data.series).map(([z, d], i) => line(v.data.zones.find((x: any) => x.zone === z)?.name ?? z, pairs(m.data.ts, d), i === 0 ? { markLine: threshold(v.data.pm25_alert, "Alert level") } : {})) }) : {}, [m.data, v.data]);
  return (
    <>
      <PageHead title="Air quality" subtitle="Zone-wise fine particles (PM2.5), hotspots and a 24-hour outlook. Categories follow CPCB PM2.5 bands." />
      <State q={v}>
        {v.data && <>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <Kpi label="Campus PM2.5, last 24 h" value={num(v.data.campus_pm25_24h)} unit="µg/m³" note={<span style={{ color: v.data.category.color }}>{v.data.category.label}</span>} />
            <Kpi label="Hotspot" value={v.data.hotspot.name} note={`${v.data.hotspot.pm25_24h} µg/m³ (24 h)`} tone={v.data.hotspot.pm25_24h > v.data.pm25_alert ? "bad" : undefined} />
            <Kpi label="Alert level (configurable)" value={v.data.pm25_alert} unit="µg/m³" />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Pollution hotspot map" caption="Colour is interpolated between sensors (inverse-distance weighting), so areas between zones are estimates.">
              <SitePlan title="PM2.5 hotspot map" zones={v.data.zones.map((z: any) => ({ ...z, label: String(Math.round(z.pm25_24h)), status: z.pm25_24h > v.data.pm25_alert ? "alert" : z.pm25_24h > 0.8 * v.data.pm25_alert ? "watch" : "ok" }))} grid={v.data.heat_grid} />
              <p className="mt-3 rounded-md bg-brand/10 p-2.5 text-sm"><b>Advisory: </b>{v.data.advisory}</p>
            </Card>
            <Card title="Zones now"><Table head={["Zone", "Now", "24 h average", "Category"]} rows={[...v.data.zones].sort((a: any, b: any) => b.pm25_24h - a.pm25_24h).map((z: any) => [z.name, num(z.pm25_now, 1), num(z.pm25_24h, 1), <Badge key={z.zone} tone="x"><span style={{ color: z.category.color }}>{z.category.label}</span></Badge>])} /></Card>
          </div>
        </>}
      </State>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="PM2.5 by zone" caption="Dashed line marks your configured alert level."><State q={m}><Chart option={opt} label="PM2.5 trend by zone" /></State></Card>
        <ForecastCard module="air" metric="pm25" title="Next 24 hours (campus average PM2.5)" />
      </div>
      <div className="mt-4"><AnomalyList module="air" days={Math.min(days, 30)} title="Pollution episodes and sensor faults" /></div>
    </>
  );
}
