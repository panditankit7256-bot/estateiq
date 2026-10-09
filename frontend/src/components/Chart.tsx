import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkAreaComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useApp } from "@/store/app";
echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkAreaComponent, CanvasRenderer]);

const css = (n: string) => `rgb(${getComputedStyle(document.documentElement).getPropertyValue(`--${n}`).trim().split(" ").join(",")})`;
export function palette() {
  return { ink: css("ink"), muted: css("muted"), line: css("line"), brand: css("brand"), info: css("info"), warn: css("warn"), bad: css("bad"), ok: css("ok"),
           series: [css("brand"), css("info"), css("warn"), css("bad"), "#7a6ba8", "#3aa6a0", "#8a8f3c"] };
}

/** Base option shared by all charts: axes, tooltip and fonts follow the active theme. */
export function baseOption(extra: Record<string, any>) {
  const p = palette();
  return {
    color: p.series, textStyle: { fontFamily: "IBM Plex Sans, sans-serif", color: p.muted },
    grid: { left: 44, right: 16, top: 28, bottom: 28, containLabel: false },
    tooltip: { trigger: "axis", backgroundColor: css("surface"), borderColor: p.line, textStyle: { color: p.ink }, confine: true },
    legend: { top: 0, textStyle: { color: p.muted }, itemHeight: 8 },
    xAxis: { type: "category", axisLine: { lineStyle: { color: p.line } }, axisLabel: { color: p.muted }, axisTick: { show: false } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: p.line, opacity: 0.6 } }, axisLabel: { color: p.muted } },
    animation: false, ...extra,
  };
}

export function Chart({ option, height = 260, label }: { option: Record<string, any>; height?: number; label: string }) {
  const el = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);
  const theme = useApp((s) => s.theme);
  useEffect(() => {
    if (!el.current) return;
    inst.current = echarts.init(el.current);
    const ro = new ResizeObserver(() => inst.current?.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); inst.current?.dispose(); };
  }, []);
  useEffect(() => { inst.current?.setOption(option, true); }, [option, theme]);
  return <div ref={el} role="img" aria-label={label} style={{ height }} />;
}
