"use client";

import { useMemo } from "react";

export type ChartPoint = { label: string; value: number; key?: string };

const palette = ["#8661bb", "#6380c7", "#249b85", "#d68155", "#d05a79", "#8f9d5f", "#5b6c8e", "#bd8e38", "#9d7199"];
const compact = (value: number) => new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(value);

function EmptyChart({ message = "No data is available for this period." }: { message?: string }) {
  return <div className="flex h-[232px] items-center justify-center rounded-xl border border-dashed border-[#ded7e8] bg-[#fcfbfd] px-5 text-center text-sm text-[#77829a]">{message}</div>;
}

export function LineChart({ data, ariaLabel }: { data: ChartPoint[]; ariaLabel: string }) {
  const { points, max } = useMemo(() => {
    const maxValue = Math.max(1, ...data.map((item) => item.value));
    const horizontal = Math.max(1, data.length - 1);
    return {
      max: maxValue,
      points: data.map((item, index) => ({ ...item, x: 18 + (index / horizontal) * 264, y: 150 - (item.value / maxValue) * 116 })),
    };
  }, [data]);
  if (!data.some((item) => item.value)) return <EmptyChart />;
  const path = points.map((item, index) => `${index ? "L" : "M"}${item.x.toFixed(2)},${item.y.toFixed(2)}`).join(" ");
  const area = `${path} L282,150 L18,150 Z`;
  return <div className="h-[232px]" role="img" aria-label={ariaLabel}>
    <svg viewBox="0 0 300 190" className="h-[190px] w-full overflow-visible">
      {[34, 73, 112, 150].map((y) => <line className="chart-grid-line" key={y} x1="18" x2="282" y1={y} y2={y} />)}
      <defs><linearGradient id="overview-area" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#cbb3e8" stopOpacity=".58" /><stop offset="1" stopColor="#cbb3e8" stopOpacity="0" /></linearGradient></defs>
      <path d={area} fill="url(#overview-area)" />
      <path d={path} className="chart-line-path" fill="none" stroke="#8661bb" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((item) => <g key={item.label}><title>{`${item.label}: ${item.value}`}</title><circle cx={item.x} cy={item.y} r="4" fill="white" stroke="#8661bb" strokeWidth="2.5" /></g>)}
      <text x="2" y="37" fontSize="9" fill="#77829a">{compact(max)}</text>
      <text x="5" y="153" fontSize="9" fill="#77829a">0</text>
    </svg>
    <div className="-mt-1 flex justify-between gap-1 text-[10px] font-medium text-[#77829a]">{data.filter((_, index) => index === 0 || index === data.length - 1 || index === Math.floor(data.length / 2)).map((item) => <span key={item.label}>{item.label}</span>)}</div>
  </div>;
}

export function BarChart({ data, ariaLabel, horizontal = false }: { data: ChartPoint[]; ariaLabel: string; horizontal?: boolean }) {
  const max = Math.max(1, ...data.map((item) => item.value));
  if (!data.some((item) => item.value)) return <EmptyChart />;
  if (horizontal) return <div role="img" aria-label={ariaLabel} className="space-y-3 pt-2">{data.map((item, index) => <div key={item.label}><div className="mb-1.5 flex items-center justify-between gap-4 text-xs"><span className="truncate font-medium text-[#56627b]">{item.label}</span><strong className="metric-value text-[#17233f]">{item.value}</strong></div><div className="h-2 overflow-hidden rounded-full bg-[#eeeaf3]"><div className="chart-bar h-full rounded-full" style={{ width: `${Math.max(2, (item.value / max) * 100)}%`, background: palette[index % palette.length], animationDelay: `${index * 55}ms` }} /></div></div>)}</div>;
  return <div className="h-[232px]" role="img" aria-label={ariaLabel}><div className="flex h-[190px] items-end gap-2 border-b border-[#e9e3f0] px-1">{data.map((item, index) => <div key={item.label} className="flex h-full min-w-0 flex-1 flex-col justify-end"><div className="mb-1 text-center text-[10px] font-bold text-[#56627b]">{item.value || ""}</div><div title={`${item.label}: ${item.value}`} className="chart-bar min-h-[2px] rounded-t-md" style={{ height: `${Math.max(1, (item.value / max) * 100)}%`, background: palette[index % palette.length], animationDelay: `${index * 55}ms` }} /></div>)}</div><div className="mt-2 flex gap-2 overflow-hidden">{data.map((item) => <span key={item.label} className="min-w-0 flex-1 truncate text-center text-[10px] font-medium text-[#77829a]">{item.label}</span>)}</div></div>;
}

export function DonutChart({ data, ariaLabel }: { data: ChartPoint[]; ariaLabel: string }) {
  const nonZero = data.filter((item) => item.value > 0);
  const total = nonZero.reduce((sum, item) => sum + item.value, 0);
  if (!total) return <EmptyChart message="No lead-source data is available yet." />;
  const circumference = 2 * Math.PI * 47;
  const segments = nonZero.reduce<Array<{ item: ChartPoint; index: number; length: number; offset: number }>>((all, item, index) => {
    const offset = all.length ? all[all.length - 1].offset + all[all.length - 1].length : 0;
    all.push({ item, index, offset, length: (item.value / total) * circumference });
    return all;
  }, []);
  return <div className="grid min-h-[232px] gap-4 sm:grid-cols-[148px_1fr] sm:items-center" role="img" aria-label={ariaLabel}>
    <div className="relative mx-auto h-[148px] w-[148px]"><svg viewBox="0 0 120 120" className="h-full w-full -rotate-90"><circle cx="60" cy="60" r="47" fill="none" stroke="#eeeaf3" strokeWidth="15" />{segments.map(({ item, index, offset, length }) => <circle key={item.label} className="chart-segment" cx="60" cy="60" r="47" fill="none" stroke={palette[index % palette.length]} strokeWidth="15" strokeDasharray={`${Math.max(0, length - 2)} ${circumference}`} strokeDashoffset={-offset} style={{ animationDelay: `${index * 85}ms` }}><title>{`${item.label}: ${item.value}`}</title></circle>)}</svg><div className="absolute inset-0 flex flex-col items-center justify-center"><strong className="metric-value text-2xl text-[#17233f]">{compact(total)}</strong><span className="text-[10px] font-bold uppercase tracking-[.12em] text-[#77829a]">Leads</span></div></div>
    <div className="grid grid-cols-2 gap-x-3 gap-y-2">{nonZero.map((item, index) => <div key={item.label} className="flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: palette[index % palette.length] }} /><span className="truncate text-xs text-[#66738d]">{item.label}</span><strong className="ml-auto text-xs text-[#17233f]">{item.value}</strong></div>)}</div>
  </div>;
}

export function FunnelChart({ data, ariaLabel }: { data: ChartPoint[]; ariaLabel: string }) {
  const max = Math.max(1, ...data.map((item) => item.value));
  if (!data.some((item) => item.value)) return <EmptyChart message="No active pipeline records are available yet." />;
  return <div role="img" aria-label={ariaLabel} className="space-y-3 pt-1">{data.map((item, index) => <div key={item.label} className="text-center"><div title={`${item.label}: ${item.value}`} className="chart-bar mx-auto flex min-h-9 items-center justify-center rounded-lg px-3 text-xs font-bold text-white shadow-sm" style={{ width: `${Math.max(28, (item.value / max) * 100)}%`, background: palette[index % palette.length], animationDelay: `${index * 75}ms` }}>{item.label} <span className="metric-value ml-1.5 rounded bg-black/10 px-1.5 py-0.5">{item.value}</span></div></div>)}</div>;
}
