import { ReactNode } from "react";
import { AlertTriangle, Loader2, Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/lib/api";

export function Card({ title, caption, action, children, className = "" }: { title?: string; caption?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card p-4 ${className}`}>
      {(title || action) && <div className="mb-1 flex items-start justify-between gap-3"><h2 className="text-base font-semibold">{title}</h2>{action}</div>}
      {caption && <p className="mb-3 max-w-[70ch] text-sm text-muted">{caption}</p>}
      {children}
    </section>
  );
}

export function Kpi({ label, value, unit, note, tone }: { label: string; value: ReactNode; unit?: string; note?: ReactNode; tone?: "ok" | "warn" | "bad" }) {
  const c = tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : tone === "ok" ? "text-ok" : "";
  return (
    <div className="card px-4 py-3">
      <div className="text-sm text-muted">{label}</div>
      <div className={`mt-0.5 text-2xl font-semibold tabular-nums ${c}`}>{value}{unit && <span className="ml-1 text-sm font-normal text-muted">{unit}</span>}</div>
      {note && <div className="mt-0.5 text-xs text-muted">{note}</div>}
    </div>
  );
}

const TONES: Record<string, string> = { Critical: "bg-bad text-white", High: "bg-bad/15 text-bad", Medium: "bg-warn/15 text-warn", Low: "bg-info/15 text-info", ok: "bg-ok/15 text-ok", watch: "bg-warn/15 text-warn", alert: "bg-bad/15 text-bad" };
export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  return <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${TONES[tone ?? String(children)] ?? "bg-raised text-muted"}`}>{children}</span>;
}

export function Disclaimer() {
  const { t } = useTranslation();
  return <span className="inline-flex items-center gap-1 rounded border border-line bg-raised px-2 py-0.5 text-xs text-muted"><Info size={12} aria-hidden />{t("disclaimer")}</span>;
}

export function PageHead({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-xl font-semibold">{title}</h1>{subtitle && <p className="max-w-[75ch] text-sm text-muted">{subtitle}</p>}</div>
      <div className="flex items-center gap-2">{right}<Disclaimer /></div>
    </div>
  );
}

/** Loading, error and empty states for any query. */
export function State({ q, children }: { q: { isLoading: boolean; error: unknown; data: unknown; refetch?: () => void }; children: ReactNode }) {
  if (q.isLoading) return <div className="flex items-center gap-2 p-6 text-muted" role="status"><Loader2 className="animate-spin" size={16} />Crunching the latest sensor data. The first load of a facility can take a few seconds.</div>;
  if (q.error) return (
    <div className="card flex items-start gap-3 border-bad/40 p-4" role="alert"><AlertTriangle className="mt-0.5 text-bad" size={18} />
      <div><div className="font-medium">Could not load this data</div><div className="text-sm text-muted">{(q.error as ApiError).message}</div>
        {q.refetch && <button className="btn mt-2" onClick={() => q.refetch?.()}>Try again</button>}</div></div>
  );
  if (!q.data) return <div className="p-6 text-muted">No data yet for this facility. Upload a CSV in Settings or advance the simulator on the Command centre.</div>;
  return <>{children}</>;
}

export function Table({ head, rows, empty = "Nothing to show." }: { head: string[]; rows: ReactNode[][]; empty?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr>{head.map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{rows.length ? rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="td tabular-nums">{c}</td>)}</tr>) : <tr><td className="td text-muted" colSpan={head.length}>{empty}</td></tr>}</tbody>
      </table>
    </div>
  );
}

export function Bar({ value, max = 100, tone = "brand" }: { value: number; max?: number; tone?: "brand" | "warn" | "bad" }) {
  const cls = tone === "bad" ? "bg-bad" : tone === "warn" ? "bg-warn" : "bg-brand";
  return <div className="h-2 w-full rounded bg-raised" role="presentation"><div className={`h-2 rounded ${cls}`} style={{ width: `${Math.min(100, (value / max) * 100)}%` }} /></div>;
}
