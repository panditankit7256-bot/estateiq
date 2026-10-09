import { useMemo } from "react";
import { Chart } from "./Chart";
import { Card, State } from "./ui";
import { useQ } from "@/lib/api";
import { line, pairs, timeChart } from "@/lib/charts";
import { palette } from "./Chart";

/** History + forecast + 95% band, with honest accuracy metrics against a seasonal-naive baseline. */
export function ForecastCard({ module, metric, title, horizon = 24, caption }: { module: string; metric?: string; title: string; horizon?: number; caption?: string }) {
  const q = useQ<any>(`/forecast/${module}`, { metric, horizon });
  const opt = useMemo(() => {
    const d = q.data; if (!d) return {};
    const p = palette();
    return timeChart([
      line("Recent", pairs(d.history_ts, d.history), { color: p.muted }),
      line("Forecast", pairs(d.ts, d.yhat), { color: p.brand, lineStyle: { type: "dashed", width: 2.5 } }),
      line("lo", pairs(d.ts, d.lo), { stack: "band", lineStyle: { opacity: 0 }, tooltip: { show: false }, silent: true }),
      { name: "95% range", type: "line", showSymbol: false, stack: "band", lineStyle: { opacity: 0 }, areaStyle: { color: p.brand, opacity: 0.16 }, data: d.ts.map((t: string, i: number) => [t, +(d.hi[i] - d.lo[i]).toFixed(3)]) },
    ], { legend: { top: 0, data: ["Recent", "Forecast", "95% range"], textStyle: { color: p.muted } }, yAxis: { type: "value", name: d.unit, nameTextStyle: { color: p.muted }, splitLine: { lineStyle: { color: p.line, opacity: 0.6 } }, axisLabel: { color: p.muted } } });
  }, [q.data]);
  return (
    <Card title={title} caption={caption ?? "Short-term forecast with an approximate 95% range. It learns daily and weekly patterns; unusual events are not predicted."}>
      <State q={q}>
        <Chart option={opt} label={title} height={250} />
        {q.data && <>
          <p className="mt-2 text-sm"><b>How good is it?</b> Average miss {q.data.metrics.mae} {q.data.unit} (about {q.data.metrics.mape_pct}%) on a held-out day; a "same as yesterday" guess missed by {q.data.metrics.baseline_mae}. That is {q.data.metrics.improvement_vs_baseline_pct}% {q.data.metrics.improvement_vs_baseline_pct >= 0 ? "better" : "worse"}.</p>
          <details className="mt-1 text-xs text-muted"><summary className="cursor-pointer">Assumptions</summary><ul className="mt-1 list-disc pl-5">{q.data.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul></details>
        </>}
      </State>
    </Card>
  );
}
