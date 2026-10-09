import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "./ui";
import { api, useAct } from "@/lib/api";
import { useApp } from "@/store/app";
import { inr, num } from "@/lib/format";

export interface Rec { key: string; title: string; detected: string; why: string; action: string; owner: string; urgency: string; module: string; confidence: string; status: string;
  impact: Record<string, number | string>; basis: string[]; narrative: string }
const OWNER: Record<string, string> = { administrator: "Administrator", operations: "Operations team", sustainability: "Sustainability officer" };

function impacts(i: Rec["impact"]) {
  const out: string[] = [];
  if (typeof i.inr_month === "number" && i.inr_month) out.push(`${inr(i.inr_month)} per month`);
  if (typeof i.kwh_month === "number" && i.kwh_month) out.push(`${num(i.kwh_month)} kWh per month`);
  if (typeof i.kl_month === "number" && i.kl_month) out.push(`${num(i.kl_month)} kL water per month`);
  if (typeof i.co2_kg_month === "number" && i.co2_kg_month) out.push(`${num(i.co2_kg_month)} kg CO2 per month`);
  if (typeof i.risk_note === "string") out.push(i.risk_note);
  return out;
}

export function RecCard({ rec, compact = false }: { rec: Rec; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const user = useApp((s) => s.user)!;
  const canEdit = user.role === "administrator" || user.role === rec.owner;
  const set = useAct((status: string) => api(`/actions/${rec.key}`, { method: "PATCH", body: { status }, facility: false }), ["/recommendations"]);
  return (
    <article className="card p-4">
      <div className="flex flex-wrap items-center gap-2"><Badge>{rec.urgency}</Badge><span className="text-xs text-muted">{OWNER[rec.owner]}</span><span className="text-xs text-muted">Confidence: {rec.confidence}</span>
        {rec.narrative === "llm" && <span className="text-xs text-muted">Wording by AI</span>}</div>
      <h3 className="mt-1.5 text-base font-semibold">{rec.title}</h3>
      <p className="mt-1 text-sm">{rec.detected}</p>
      {!compact && <p className="mt-1 text-sm text-muted">{rec.why}</p>}
      <p className="mt-2 rounded-md bg-brand/10 p-2.5 text-sm"><span className="font-medium">Do this: </span>{rec.action}</p>
      {impacts(rec.impact).length > 0 && <ul className="mt-2 flex flex-wrap gap-1.5">{impacts(rec.impact).map((s) => <li key={s} className="rounded bg-raised px-2 py-0.5 text-xs">{s}</li>)}</ul>}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <button className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink" onClick={() => setOpen(!open)} aria-expanded={open}>
          <ChevronDown size={14} className={open ? "rotate-180" : ""} />Data and assumptions behind this</button>
        <label className="flex items-center gap-2 text-xs text-muted">Status
          <select className="input py-1" value={rec.status} disabled={!canEdit || set.isPending} onChange={(e) => set.mutate(e.target.value)} aria-label={`Status of ${rec.title}`}>
            {["Pending", "In progress", "Done"].map((s) => <option key={s}>{s}</option>)}</select></label>
      </div>
      {open && <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-muted">{rec.basis.map((b) => <li key={b}>{b}</li>)}</ul>}
    </article>
  );
}
