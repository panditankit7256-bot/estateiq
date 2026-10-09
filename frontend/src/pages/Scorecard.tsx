import { useMemo } from "react";
import { Download } from "lucide-react";
import { Card, PageHead, State, Table, Bar } from "@/components/ui";
import { Chart, palette } from "@/components/Chart";
import { useQ } from "@/lib/api";
import { useApp } from "@/store/app";
import { bar, catChart } from "@/lib/charts";

const LABEL: Record<string, string> = { energy: "Energy", water: "Water", waste: "Waste service", air: "Air quality", emissions: "Emissions", safety: "Safety" };
const RAW: Record<string, string> = { energy: "energy_kwh_per_sqm_month", water: "water_lpcd", waste: "bin_service_level_pct", air: "air_hours_within_limit_pct", emissions: "co2_kg_per_sqm_month", safety: "weighted_incident_load" };
const UNIT: Record<string, string> = { energy: "kWh/m²/month", water: "L/person/day", waste: "% bin-hours under alert", air: "% hours within limit", emissions: "kg CO2/m²/month", safety: "weighted incidents" };

export default function Scorecard() {
  const { facility, token } = useApp();
  const v = useQ<any>("/scorecard");
  const hist = useMemo(() => v.data ? catChart([...v.data.history].reverse().map((h: any) => h.label), [bar("Overall score", [...v.data.history].reverse().map((h: any) => h.overall), { color: palette().brand })], { yAxis: { type: "value", min: 0, max: 100 } }) : {}, [v.data]);
  async function download() {
    const r = await fetch(`/api/v1/reports/export?kind=scorecard&facility=${facility}`, { headers: { Authorization: `Bearer ${token}` } });
    const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = `${facility}_scorecard.csv`; a.click();
  }
  const c = v.data?.current;
  return (
    <>
      <PageHead title="Sustainability scorecard" subtitle="One score out of 100, built from six areas weighted for this facility type." right={<><button className="btn no-print" onClick={download}><Download size={14} />CSV</button><button className="btn no-print" onClick={() => window.print()}>Print</button></>} />
      <State q={v}>{c && <>
        <div className="grid gap-4 lg:grid-cols-3">
          <Card title="Overall"><div className="flex items-end gap-3"><span className="text-6xl font-semibold tabular-nums">{c.overall}</span><span className="mb-2 rounded bg-brand px-2.5 py-0.5 text-lg font-semibold text-brandfg">Grade {c.grade}</span></div>
            <p className="mt-2 text-sm text-muted">{c.label}. Grades: A 85+, B 70+, C 55+, D 40+.</p></Card>
          <Card className="lg:col-span-2" title="Trend (month on month)" caption="A rising bar means the facility is closer to its targets."><Chart option={hist} label="Overall score by 30-day window" height={170} /></Card>
        </div>
        <Card className="mt-4" title="Score by area" caption={v.data.method}>
          <Table head={["Area", "Weight", "Score", "Measured", "Target"]} rows={Object.keys(c.sub).map((k) => [LABEL[k], `${Math.round(v.data.weights[k] * 100)}%`, <div key={k} className="w-36"><div className="flex justify-between text-xs"><b>{c.sub[k]}</b></div><Bar value={c.sub[k]} tone={c.sub[k] < 50 ? "bad" : c.sub[k] < 75 ? "warn" : "brand"} /></div>,
            `${c.raw[RAW[k]]} ${UNIT[k]}`, k === "energy" ? `${v.data.targets.energy_kwh_per_sqm_month}` : k === "water" ? `${v.data.targets.water_lpcd}` : k === "air" ? `PM2.5 ≤ ${v.data.targets.pm25_alert} µg/m³` : k === "waste" ? `bins under ${v.data.targets.bin_alert_pct}%` : "-"])} />
        </Card>
      </>}</State>
    </>
  );
}
