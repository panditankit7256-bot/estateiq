import { useMemo } from "react";

export interface PlanZone { zone: string; name: string; lat: number; lon: number; status?: string; label?: string }
interface Grid { lat_min: number; lat_max: number; lon_min: number; lon_max: number; n: number; values: number[][] }
interface Pt { id: string; lat: number; lon: number; fill_pct?: number; alert?: boolean }
const W = 680, H = 400;
const AQI = [[30, "#2e7d32"], [60, "#7cb342"], [90, "#f9a825"], [120, "#ef6c00"], [250, "#c62828"], [1e9, "#6a1b1a"]] as const;
const aqiColor = (v: number) => (AQI.find(([hi]) => v <= hi) ?? AQI[5])[1];
const STATUS: Record<string, string> = { ok: "rgb(var(--ok))", watch: "rgb(var(--warn))", alert: "rgb(var(--bad))" };

/** Schematic site plan drawn from zone coordinates (no map tiles needed, so it works offline). */
export function SitePlan({ zones, grid, bins, route, depot, onSelect, title }: {
  zones: PlanZone[]; grid?: Grid; bins?: Pt[]; route?: Pt[]; depot?: { lat: number; lon: number }; onSelect?: (z: string) => void; title: string;
}) {
  const proj = useMemo(() => {
    const lats = [...zones.map((z) => z.lat), ...(bins ?? []).map((b) => b.lat)], lons = [...zones.map((z) => z.lon), ...(bins ?? []).map((b) => b.lon)];
    if (grid) { lats.push(grid.lat_min, grid.lat_max); lons.push(grid.lon_min, grid.lon_max); }
    if (depot) { lats.push(depot.lat); lons.push(depot.lon); }
    const [la0, la1, lo0, lo1] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
    const k = Math.cos(((la0 + la1) / 2) * Math.PI / 180);
    const xr = Math.max((lo1 - lo0) * k, 1e-5), yr = Math.max(la1 - la0, 1e-5);
    const s = Math.min(W / xr, H / yr) * 0.86;
    const ox = (W - xr * s) / 2, oy = (H - yr * s) / 2;
    return { x: (lon: number) => ox + (lon - lo0) * k * s, y: (lat: number) => H - oy - (lat - la0) * s, s, k };
  }, [zones, grid, bins, depot]);
  const cell = grid ? { w: ((grid.lon_max - grid.lon_min) * proj.k * proj.s) / grid.n, h: ((grid.lat_max - grid.lat_min) * proj.s) / grid.n } : null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-md border border-line bg-raised" role="img" aria-label={title}>
      <defs><pattern id="g" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="rgb(var(--line))" strokeWidth="0.6" /></pattern></defs>
      <rect width={W} height={H} fill="url(#g)" />
      {grid && cell && grid.values.map((row, i) => row.map((v, j) => (
        <rect key={`${i}-${j}`} x={proj.x(grid.lon_min) + j * cell.w} y={proj.y(grid.lat_max) + (grid.n - 1 - i) * cell.h} width={cell.w + 0.5} height={cell.h + 0.5} fill={aqiColor(v)} opacity={0.38} />
      )))}
      {route && route.length > 0 && depot && (
        <polyline fill="none" stroke="rgb(var(--brand))" strokeWidth={2.2} strokeDasharray="6 4"
          points={[depot, ...route, depot].map((p) => `${proj.x(p.lon)},${proj.y(p.lat)}`).join(" ")} />
      )}
      {depot && <g><rect x={proj.x(depot.lon) - 7} y={proj.y(depot.lat) - 7} width={14} height={14} rx={3} fill="rgb(var(--ink))" /><text x={proj.x(depot.lon) + 11} y={proj.y(depot.lat) + 4} fontSize={11} fill="rgb(var(--ink))">Depot</text></g>}
      {zones.map((z) => (
        <g key={z.zone} transform={`translate(${proj.x(z.lon)},${proj.y(z.lat)})`} onClick={() => onSelect?.(z.zone)} style={{ cursor: onSelect ? "pointer" : "default" }}>
          <circle r={16} fill="rgb(var(--surface))" stroke={STATUS[z.status ?? "ok"]} strokeWidth={3.5} />
          <text textAnchor="middle" y={4} fontSize={11} fontWeight={600} fill="rgb(var(--ink))">{z.label ?? ""}</text>
          <text textAnchor="middle" y={32} fontSize={11} fill="rgb(var(--ink))" stroke="rgb(var(--raised))" strokeWidth={3} paintOrder="stroke">{z.name}</text>
        </g>
      ))}
      {bins?.map((b) => {
        const f = b.fill_pct ?? 0;
        const stopNo = route ? route.findIndex((r) => r.id === b.id) + 1 : 0;
        return (
          <g key={b.id} transform={`translate(${proj.x(b.lon)},${proj.y(b.lat)})`}>
            <rect x={-6} y={-6} width={12} height={12} rx={2} fill={f >= 90 ? "rgb(var(--bad))" : f >= 80 ? "rgb(var(--warn))" : "rgb(var(--ok))"} stroke="rgb(var(--surface))" strokeWidth={1.5} />
            {stopNo > 0 && <text x={9} y={-7} fontSize={10} fontWeight={600} fill="rgb(var(--ink))">{stopNo}</text>}
          </g>
        );
      })}
    </svg>
  );
}
