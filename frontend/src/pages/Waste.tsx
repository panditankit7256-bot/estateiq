import { useMemo, useState } from "react";
import { Card, Kpi, PageHead, State, Table, Badge, Bar } from "@/components/ui";
import { SitePlan } from "@/components/SitePlan";
import { Chart, palette } from "@/components/Chart";
import { useQ } from "@/lib/api";
import { useApp } from "@/store/app";
import { line, pairs, threshold, timeChart } from "@/lib/charts";
import { num } from "@/lib/format";

export default function Waste() {
  const days = useApp((s) => s.days);
  const [mode, setMode] = useState<"optimized" | "none">("optimized");
  const v = useQ<any>("/views/waste"), ov = useQ<any>("/overview"), m = useQ<any>("/metrics/waste", { metric: "fill_pct", days: Math.min(days, 14) });
  const trend = useMemo(() => m.data ? timeChart(Object.entries<any>(m.data.series).map(([z, d], i) => line(z, pairs(m.data.ts, d), i === 0 ? { markLine: threshold(v.data?.threshold ?? 80, "Collect at") } : {})), { yAxis: { type: "value", name: "% full (zone average)", max: 100 } }) : {}, [m.data, v.data]);
  const d = v.data;
  return (
    <>
      <PageHead title="Waste" subtitle="Which bins will overflow, in what order to collect them, and how much driving that saves." />
      <State q={v}>{d && <>
        <div className="mb-4 grid gap-3 sm:grid-cols-4">
          <Kpi label="Bins needing pickup" value={d.bins.filter((b: any) => b.alert).length} unit={`of ${d.bins.length}`} tone={d.bins.some((b: any) => b.alert) ? "warn" : "ok"} />
          <Kpi label="Optimised round" value={num(d.route.optimized_km, 2)} unit="km" note={`vs ${num(d.route.current_km, 2)} km visiting every bin`} />
          <Kpi label="Distance saved" value={num(d.route.saved_km, 2)} unit="km per round" tone="ok" />
          <Kpi label="Overflow bin-hours (90 days)" value={d.overflow_bin_hours_90d} note="bin was 90%+ full" />
        </div>
        <div className="grid gap-4 lg:grid-cols-5">
          <Card className="lg:col-span-3" title="Bins and suggested collection order" caption="Squares are bins (green under the alert level, amber near it, red nearly full). Numbers show the visiting order for bins that need pickup.">
            <div className="mb-2 flex gap-2 text-sm no-print">{([["optimized", "Show suggested route"], ["none", "Hide route"]] as const).map(([k, l]) => <button key={k} className={`btn ${mode === k ? "btn-primary" : ""}`} onClick={() => setMode(k)}>{l}</button>)}</div>
            <SitePlan title="Bins and collection route" zones={(ov.data?.zones ?? []).map((z: any) => ({ ...z, label: "" , status: "ok" }))} bins={d.bins} depot={d.depot} route={mode === "optimized" ? d.route.optimized_points : undefined} />
            <p className="mt-2 text-xs text-muted">{d.route.note}</p>
          </Card>
          <Card className="lg:col-span-2" title="Collect first" caption="Sorted by time left before 90% full.">
            <Table head={["Bin", "Fill", "Hours to 90%", "Overflow in 6 h"]} rows={[...d.bins].sort((a: any, b: any) => a.hours_to_90 - b.hours_to_90).slice(0, 8).map((b: any) => [<span key={b.id}>{b.id.replace("bin-", "")} <span className="text-xs text-muted">{b.type}</span></span>, <div key="f" className="w-24"><Bar value={b.fill_pct} tone={b.fill_pct >= 90 ? "bad" : b.fill_pct >= 80 ? "warn" : "brand"} /><span className="text-xs">{b.fill_pct}%</span></div>, b.hours_to_90 <= 0 ? "Full now" : num(b.hours_to_90, 1), <Badge key="p" tone={b.p_overflow_6h >= 0.5 ? "High" : b.p_overflow_6h >= 0.2 ? "Medium" : "ok"}>{Math.round(b.p_overflow_6h * 100)}%</Badge>])} />
            <p className="mt-2 text-xs text-muted">{d.model_note}</p>
          </Card>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card title="Fill level over time" caption="Each line is a zone's average. Sharp drops are collections."><State q={m}><Chart option={trend} label="Bin fill level by zone" /></State></Card>
          <Card title="Segregation snapshot" caption="Average fill by waste stream right now. A stream that fills much faster than others may need extra bins or awareness drives.">
            <ul className="space-y-2">{Object.entries<number>(d.avg_fill_by_type).map(([t, v2]) => <li key={t}><div className="flex justify-between text-sm"><span className="capitalize">{t}</span><span className="tabular-nums">{v2}%</span></div><Bar value={v2} /></li>)}</ul>
          </Card>
        </div>
      </>}</State>
      <span className="hidden" style={{ color: palette().ink }} />
    </>
  );
}
