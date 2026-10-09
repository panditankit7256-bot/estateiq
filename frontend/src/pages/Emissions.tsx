import { useMemo } from "react";
import { Card, Kpi, PageHead, State, Table, Badge } from "@/components/ui";
import { Chart, palette } from "@/components/Chart";
import { useQ } from "@/lib/api";
import { bar, catChart } from "@/lib/charts";
import { num } from "@/lib/format";

export default function Emissions() {
  const v = useQ<any>("/views/emissions");
  const d = v.data;
  const opt = useMemo(() => d ? catChart(["Scope 1: diesel", "Scope 2: grid power", "Scope 3: commute (indicative)", "Avoided by solar"], [bar("kg CO2e", [d.scope1_kg, d.scope2_kg, d.scope3_indicative_kg, d.solar_avoided_kg].map((x: number, i: number) => ({ value: x, itemStyle: { color: [palette().bad, palette().warn, palette().muted, palette().ok][i] } })))]) : {}, [d]);
  const tone = (s: string) => (s === "High" ? "High" : s === "Medium" ? "Medium" : "ok");
  return (
    <>
      <PageHead title="Emissions and climate resilience" subtitle="Greenhouse gases from energy and commuting, plus heat and rain readiness by zone." />
      <State q={v}>{d && <>
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Scope 1 + 2 (30 days)" value={num(d.scope1_kg + d.scope2_kg)} unit="kg CO2e" />
          <Kpi label="Intensity" value={num(d.intensity_kg_per_sqm, 2)} unit="kg per m²" />
          <Kpi label="Avoided by solar" value={num(d.solar_avoided_kg)} unit="kg CO2e" tone="ok" />
          <Kpi label="Days at 35 °C or more" value={d.heat_days} note={`Heaviest 24 h rain: ${d.max_rain_24h_mm} mm`} tone={d.heat_days >= 3 ? "warn" : undefined} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Where emissions come from" caption={d.note}><Chart option={opt} label="Emissions by scope" /><p className="mt-1 text-xs text-muted">Factors used: grid {d.factors.grid_kg_per_kwh} kg CO2/kWh, diesel {d.factors.dg_kg_per_kwh} kg CO2/kWh. Edit them in Settings.</p></Card>
          <Card title="Zone readiness (indicative)" caption="Simple screening from recent weather and zone type, not an engineering risk assessment.">
            <Table head={["Zone", "Heat stress", "Waterlogging"]} rows={d.zones.map((z: any) => [z.name, <Badge key="h" tone={tone(z.heat_stress)}>{z.heat_stress}</Badge>, <Badge key="w" tone={tone(z.waterlogging)}>{z.waterlogging}</Badge>])} />
          </Card>
        </div>
        <Card className="mt-4" title="Heat and monsoon readiness checklist" caption="Items are highlighted when recent conditions make them relevant.">
          <ul className="grid gap-2 sm:grid-cols-2">{d.checklist.map((c: any) => <li key={c.item} className="flex items-center gap-2 rounded-md border border-line p-2.5 text-sm"><Badge tone={c.flag ? "Medium" : "ok"}>{c.flag ? "Relevant now" : "Not urgent"}</Badge>{c.item}</li>)}</ul>
        </Card>
      </>}</State>
    </>
  );
}
