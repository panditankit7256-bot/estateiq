import { baseOption, palette } from "@/components/Chart";

export const pairs = (ts: string[], v: (number | null)[]) => ts.map((t, i) => [t, v[i]]);
export const line = (name: string, data: unknown[], extra: Record<string, unknown> = {}) => ({ name, type: "line", showSymbol: false, data, lineStyle: { width: 2 }, ...extra });
export const bar = (name: string, data: unknown[], extra: Record<string, unknown> = {}) => ({ name, type: "bar", data, ...extra });

export function timeChart(series: unknown[], extra: Record<string, unknown> = {}) {
  return baseOption({ xAxis: { type: "time", axisLabel: { color: palette().muted, hideOverlap: true }, axisLine: { lineStyle: { color: palette().line } } }, series, ...extra });
}
export function catChart(cats: (string | number)[], series: unknown[], extra: Record<string, unknown> = {}) {
  return baseOption({ xAxis: { type: "category", data: cats, axisLabel: { color: palette().muted, hideOverlap: true } }, series, ...extra });
}
export const threshold = (v: number, name: string) => ({ silent: true, symbol: "none", lineStyle: { color: palette().bad, type: "dashed" }, label: { formatter: name, color: palette().bad }, data: [{ yAxis: v }] });
