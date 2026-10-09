import { useMemo } from "react";
import { Card, Kpi, PageHead, State, Table, Badge, Bar } from "@/components/ui";
import { Chart, palette } from "@/components/Chart";
import { useQ } from "@/lib/api";
import { bar, catChart } from "@/lib/charts";

export default function Assets() {
  const v = useQ<any>("/views/assets");
  const imp = useMemo(() => v.data ? catChart(Object.keys(v.data.feature_importance).map((k) => ({ vib_excess: "Vibration above baseline", temp_excess: "Temperature above baseline", util24: "Recent utilisation", days_since_service: "Days since service" } as Record<string, string>)[k] ?? k),
    [bar("Importance", Object.values(v.data.feature_importance), { color: palette().brand })]) : {}, [v.data]);
  const a = v.data?.assets ?? [];
  return (
    <>
      <PageHead title="Assets and equipment" subtitle="Which equipment is most likely to need attention, and which is sitting idle." />
      <State q={v}>{v.data && <>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Kpi label="Need attention" value={a.filter((x: any) => x.risk_band === "Critical" || x.risk_band === "High").length} unit={`of ${a.length}`} tone={a.some((x: any) => x.risk_band === "Critical") ? "bad" : undefined} />
          <Kpi label="Idle assets (under 15% use, 7 days)" value={a.filter((x: any) => x.idle).length} />
          <Kpi label="Highest risk" value={a[0]?.name ?? "-"} note={a[0] ? `${a[0].risk_band}, score ${a[0].risk}` : undefined} />
        </div>
        <Card title="Maintenance priority queue" caption="Highest risk first. The score blends a learned model with simple rules, and the reasons say why.">
          <Table head={["Asset", "Zone", "Risk", "Why", "Use (7 d)", "Last service"]} rows={a.map((x: any) => [<span key={x.id}><b>{x.name}</b><span className="ml-1 text-xs text-muted">{x.type}</span></span>, x.zone,
            <div key="r" className="w-28"><div className="mb-0.5 flex justify-between"><Badge tone={x.risk_band === "Normal" ? "ok" : x.risk_band}>{x.risk_band}</Badge><span className="text-xs">{x.risk}</span></div><Bar value={x.risk} max={1} tone={x.risk >= 0.6 ? "bad" : x.risk >= 0.35 ? "warn" : "brand"} /></div>,
            <span key="w" className="text-muted">{x.reasons.join("; ") || "Within normal range"}</span>, `${x.util_7d_pct}%${x.idle ? " (idle)" : ""}`, `${x.days_since_service} days ago`])} />
        </Card>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card title="What drives the risk model" caption="Relative importance of each signal in the learned part of the score."><Chart option={imp} label="Risk model feature importance" height={220} /></Card>
          <Card title="About this score"><p className="text-sm text-muted">{v.data.model_note}</p></Card>
        </div>
      </>}</State>
    </>
  );
}
