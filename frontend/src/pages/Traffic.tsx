import { useMemo } from "react";
import { Card, Kpi, PageHead, State, Table } from "@/components/ui";
import { Chart, palette } from "@/components/Chart";
import { ForecastCard } from "@/components/Forecast";
import { useQ } from "@/lib/api";
import { bar, catChart, line } from "@/lib/charts";
import { hour, num } from "@/lib/format";

export default function Traffic() {
  const v = useQ<any>("/views/traffic");
  const H = Array.from({ length: 24 }, (_, h) => hour(h));
  const gate = useMemo(() => v.data ? catChart(H, [bar("Vehicles entering", v.data.gate_profile, { color: palette().info }), line("Queue (min)", v.data.queue_profile_min, { yAxisIndex: 1, color: palette().bad })],
    { yAxis: [{ type: "value", name: "vehicles/h" }, { type: "value", name: "min", splitLine: { show: false } }] }) : {}, [v.data]);
  const park = useMemo(() => v.data ? catChart(H, v.data.parking.map((p: any) => line(p.name, p.profile)), { yAxis: { type: "value", name: "% full", max: 100 } }) : {}, [v.data]);
  return (
    <>
      <PageHead title="Traffic and parking" subtitle="When vehicles arrive, where queues form and which parking areas fill up." />
      <State q={v}>{v.data && <>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Kpi label="Busiest gate hour (weekdays)" value={hour(v.data.peak_hour)} note={`${num(v.data.peak_vehicles)} vehicles`} />
          {v.data.parking.slice(0, 2).map((p: any) => <Kpi key={p.zone} label={p.name} value={num(p.now_pct)} unit="% full" note={`${p.hours_over_90_14d} h above 90% in 14 days`} tone={p.hours_over_90_14d >= 10 ? "warn" : undefined} />)}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Gate arrivals and queue" caption="Weekday average by hour. Queue minutes are an estimate from arrival rate versus gate capacity."><Chart option={gate} label="Vehicles entering and queue by hour" /></Card>
          <Card title="Parking occupancy by hour" caption="Weekday average. Lines near the top mean drivers are circling for slots."><Chart option={park} label="Parking occupancy by hour" /></Card>
        </div>
        <Card className="mt-4" title="Parking hotspots"><Table head={["Area", "Capacity", "Now", "Hours over 90% (14 days)", "Peak hour"]} rows={v.data.parking.map((p: any) => [p.name, p.capacity ?? "-", `${p.now_pct}%`, p.hours_over_90_14d, hour(p.peak_hour)])} /></Card>
      </>}</State>
      <div className="mt-4"><ForecastCard module="traffic" metric="occupancy_pct" title="Parking occupancy, next 24 hours" /></div>
    </>
  );
}
