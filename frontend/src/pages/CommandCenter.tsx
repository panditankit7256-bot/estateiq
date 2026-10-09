import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Zap, Droplets, Trash2, ShieldAlert, Wind, Cloud, IndianRupee, Play } from "lucide-react";
import { Card, Kpi, PageHead, State, Badge } from "@/components/ui";
import { SitePlan } from "@/components/SitePlan";
import { RecCard } from "@/components/RecCard";
import { AnomalyList } from "@/components/Anomalies";
import { api, useAct, useQ } from "@/lib/api";
import { useApp } from "@/store/app";
import { inr, num, dt } from "@/lib/format";

const SPIKES: [string, string][] = [["leak", "Water leak"], ["pollution", "Pollution episode"], ["energy", "Energy spike"], ["bins", "Missed bin collection"], ["outage", "Grid outage"], ["advance", "Advance 3 hours"]];

export default function CommandCenter() {
  const { t } = useTranslation();
  const user = useApp((s) => s.user)!;
  const ov = useQ<any>("/overview"), recs = useQ<any>("/recommendations");
  const [sel, setSel] = useState<string | null>(null);
  const spike = useAct((kind: string) => api("/simulate/spike", { method: "POST", body: { kind } }), ["/overview", "/recommendations", "/anomalies"]);
  const k = ov.data?.kpis;
  const zone = ov.data?.zones.find((z: any) => z.zone === sel);
  return (
    <>
      <PageHead title={ov.data ? ov.data.facility.name : "Command centre"} subtitle={ov.data ? `${ov.data.facility.city}, ${ov.data.facility.state}. Data as of ${dt(ov.data.as_of)}. Everything here updates when new readings arrive.` : undefined} />
      <State q={ov}>
        {k && <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
          <Kpi label={t("kpi.aqi")} value={num(k.aqi.pm25_24h)} unit="µg/m³ PM2.5" note={<span style={{ color: k.aqi.color }}>{k.aqi.label}</span>} />
          <Kpi label={t("kpi.energy")} value={num(k.energy_kwh_24h)} unit="kWh" note={`${k.energy_change_pct >= 0 ? "+" : ""}${k.energy_change_pct}% vs previous day`} />
          <Kpi label={t("kpi.cost")} value={inr(k.cost_inr_24h)} />
          <Kpi label={t("kpi.water")} value={num(k.water_kl_24h)} unit="kL" tone={k.water_kl_24h > k.water_budget_kl ? "warn" : undefined} note={`Budget ${num(k.water_budget_kl)} kL/day`} />
          <Kpi label={t("kpi.bins")} value={k.bins_over_threshold} unit={`of ${k.bins_total}`} tone={k.bins_over_threshold ? "warn" : "ok"} />
          <Kpi label={t("kpi.incidents")} value={k.open_incidents} tone={k.open_incidents > 5 ? "bad" : undefined} />
          <Kpi label={t("kpi.co2")} value={num(k.co2_kg_24h)} unit="kg" />
        </div>}
        <div className="grid gap-4 xl:grid-cols-5">
          <div className="space-y-4 xl:col-span-3">
            <Card title="Site plan" caption="Each circle is a zone. The ring shows its status (green normal, amber watch, red act now) and the number inside is the 24 h PM2.5 in µg/m³. Select a zone for details.">
              {ov.data && <SitePlan title="Site plan with zone status" zones={ov.data.zones.map((z: any) => ({ ...z, label: String(Math.round(z.pm25_24h)) }))} onSelect={setSel} />}
              <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-muted">
                {[["ok", "Normal"], ["watch", "Watch"], ["alert", "Act now"]].map(([s, l]) => <span key={s} className="flex items-center gap-1.5"><span className={`h-3 w-3 rounded-full border-2 ${s === "ok" ? "border-ok" : s === "watch" ? "border-warn" : "border-bad"}`} />{l}</span>)}
              </div>
              {zone && <div className="mt-3 rounded-md border border-line p-3 text-sm"><div className="mb-1 flex items-center gap-2 font-medium">{zone.name}<Badge tone={zone.status}>{zone.status === "ok" ? "Normal" : zone.status === "watch" ? "Watch" : "Act now"}</Badge></div>
                <div className="grid grid-cols-3 gap-2 text-muted"><span><Wind size={13} className="mr-1 inline" />{zone.pm25_24h} µg/m³</span><span><Zap size={13} className="mr-1 inline" />{num(zone.kwh_24h)} kWh</span><span><Trash2 size={13} className="mr-1 inline" />{zone.max_bin_fill}% fullest bin</span></div></div>}
            </Card>
            {(user.role !== "sustainability") && (
              <Card title="Try a live scenario" caption="Demo helper: adds three new simulated hours with an incident, then watch alerts and recommendations update on their own.">
                <div className="flex flex-wrap gap-2">{SPIKES.map(([kind, label]) => <button key={kind} className="btn" disabled={spike.isPending} onClick={() => spike.mutate(kind)}><Play size={13} />{label}</button>)}</div>
                {spike.isPending && <p className="mt-2 text-sm text-muted">Adding readings and refreshing analysis...</p>}
                {spike.data && <p className="mt-2 text-sm">{(spike.data as any).message}.</p>}
                {spike.error && <p role="alert" className="mt-2 text-sm text-bad">{spike.error.message}</p>}
              </Card>)}
          </div>
          <div className="space-y-4 xl:col-span-2">
            <Card title="Top actions for you" caption="Ranked by urgency for your role.">
              <State q={recs}><div className="space-y-3">{recs.data?.recommendations.slice(0, 4).map((r: any) => <RecCard key={r.key} rec={r} compact />)}</div></State>
            </Card>
            <AnomalyList days={3} title="Alert feed (last 3 days)" limit={4} />
          </div>
        </div>
      </State>
      <span className="hidden"><Droplets /><ShieldAlert /><Cloud /><IndianRupee /></span>
    </>
  );
}
