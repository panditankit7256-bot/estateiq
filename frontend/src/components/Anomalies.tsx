import { Card, State, Badge } from "./ui";
import { useQ } from "@/lib/api";
import { dt } from "@/lib/format";

export function AnomalyList({ module, days = 14, title = "Unusual readings", limit = 6 }: { module?: string; days?: number; title?: string; limit?: number }) {
  const q = useQ<any>("/anomalies", { module, days });
  return (
    <Card title={title} caption="Flagged when a sensor departs from its own normal pattern for that hour (and, for energy, after allowing for temperature).">
      <State q={q}>
        <ul className="space-y-2">
          {q.data?.events.slice(0, limit).map((e: any) => (
            <li key={e.entity + e.start} className="rounded-md border border-line p-2.5 text-sm">
              <div className="flex flex-wrap items-center gap-2">{e.active ? <Badge tone="High">Active now</Badge> : <Badge tone="Low">Resolved</Badge>}<span className="font-medium">{e.zone_name}</span>
                <span className="text-xs text-muted">{dt(e.start)} to {dt(e.end)} ({e.hours} h)</span></div>
              <p className="mt-1 text-muted">{e.explanation}</p>
            </li>))}
          {q.data && q.data.events.length === 0 && <li className="text-sm text-muted">No unusual readings in this window.</li>}
        </ul>
        {q.data && (() => { const ev = Object.entries<any>(q.data.evaluation).filter(([k]) => !module || k.startsWith(module)); return ev.length ? (
          <details className="mt-3 text-xs text-muted"><summary className="cursor-pointer">How reliable is detection? (against injected synthetic faults)</summary>
            <ul className="mt-1 space-y-0.5">{ev.map(([k, v]) => <li key={k}>{k}: found {v.recall == null ? "-" : Math.round(v.recall * 100) + "%"} of {v.injected_events} injected events; {v.precision == null ? "-" : Math.round(v.precision * 100) + "%"} of {v.flagged_events} alerts were real.</li>)}</ul>
            <p className="mt-1">{q.data.method}</p></details>) : null; })()}
      </State>
    </Card>
  );
}
