import { useMemo } from "react";
import { Card, Kpi, PageHead, State, Table, Badge, Bar } from "@/components/ui";
import { Chart, palette } from "@/components/Chart";
import { useQ } from "@/lib/api";
import { bar, catChart } from "@/lib/charts";
import { day, dt } from "@/lib/format";

const SEV = ["", "Minor", "Moderate", "Serious", "Critical"];
export default function Safety() {
  const v = useQ<any>("/views/safety");
  const weekly = useMemo(() => v.data ? catChart(v.data.weekly.ts.map(day), [bar("Incidents", v.data.weekly.count, { color: palette().warn })]) : {}, [v.data]);
  const kinds = useMemo(() => v.data ? catChart(Object.keys(v.data.kinds).map((k) => k.replace("_", " ")), [bar("Incidents", Object.values(v.data.kinds), { color: palette().info })]) : {}, [v.data]);
  const zr = v.data?.zone_risk ?? [];
  return (
    <>
      <PageHead title="Safety and incidents" subtitle="Where incidents are rising and which zones to inspect first." />
      <State q={v}>{v.data && <>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Kpi label="Open incidents" value={v.data.open} tone={v.data.open > 5 ? "bad" : undefined} />
          <Kpi label="Inspect first" value={zr[0]?.name ?? "-"} note={`risk index ${zr[0]?.risk_index}`} />
          <Kpi label="Serious or critical (90 days)" value={(v.data.severity["3"] ?? 0) + (v.data.severity["4"] ?? 0)} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Incidents per week"><Chart option={weekly} label="Incidents per week" /></Card>
          <Card title="Incident types"><Chart option={kinds} label="Incidents by type" /></Card>
          <Card title="Inspection priority" caption={v.data.method}>
            <Table head={["Zone", "Risk", "Last 30 d", "Previous 30 d", "Open"]} rows={zr.map((z: any) => [z.name, <div key="b" className="w-24"><Bar value={z.risk_index} tone={z.risk_index > 70 ? "bad" : z.risk_index > 40 ? "warn" : "brand"} /></div>, z.incidents_30d, z.incidents_prev30d, z.open])} />
          </Card>
          <Card title="Open incidents"><Table head={["When", "Zone", "Type", "Severity"]} rows={v.data.open_list.map((i: any) => [dt(i.ts), i.zone, i.kind.replace("_", " "), <Badge key={i.id} tone={i.severity >= 3 ? "High" : "Medium"}>{SEV[i.severity]}</Badge>])} empty="No open incidents." /></Card>
        </div>
      </>}</State>
    </>
  );
}
