"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BarChart, DonutChart, FunnelChart, LineChart } from "@/components/dashboard-charts";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { LeadOverviewAnalytics, LeadSummary, User, WorkspaceSummary } from "@/lib/types";

type Kpi = { label: string; value: number | null; supporting: string; href: string; icon: "users" | "building" | "trend" | "clock"; tone: string };

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

function AnimatedNumber({ value }: { value: number | null }) {
  const [display, setDisplay] = useState(value ?? 0);
  useEffect(() => {
    if (value === null) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const frame = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(frame);
    }
    const from = display;
    const started = performance.now();
    let frame = 0;
    const draw = (now: number) => {
      const progress = Math.min(1, (now - started) / 480);
      setDisplay(Math.round(from + (value - from) * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  // The current display is deliberately captured when the value changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return <>{value === null ? "—" : display.toLocaleString("en-IN")}</>;
}

function KpiCard({ item }: { item: Kpi }) {
  return <Link href={item.href} className="card-enter focus-ring group app-card rounded-2xl p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_32px_rgba(23,35,63,.1)]"><div className="flex items-start justify-between gap-3"><span className={`flex h-10 w-10 items-center justify-center rounded-xl ${item.tone}`}><Icon name={item.icon} className="h-5 w-5" /></span><Icon name="arrow" className="h-4 w-4 text-[#9aa3b4] transition group-hover:translate-x-0.5 group-hover:text-[#805bab]" /></div><p className="metric-value mt-5 text-3xl font-bold tracking-tight text-[#17233f]"><AnimatedNumber value={item.value} /></p><p className="mt-1.5 text-sm font-bold text-[#35435e]">{item.label}</p><p className="mt-1 text-xs leading-5 text-[#77829a]">{item.supporting}</p></Link>;
}

function ChartPanel({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <article className="app-card rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-bold tracking-[.16em] text-[#805bab]">{eyebrow}</p><h2 className="mt-1 text-lg font-bold text-[#17233f]">{title}</h2></div>{action}</div><div className="mt-5">{children}</div></article>;
}

export function Overview({ user }: { user: User }) {
  const cachedLeads = api.peekLeadSummary();
  const cachedWorkspace = api.peekWorkspaceSummary();
  const [leadSummary, setLeadSummary] = useState<LeadSummary | null>(() => cachedLeads ?? null);
  const [workSummary, setWorkSummary] = useState<WorkspaceSummary | null>(() => cachedWorkspace ?? null);
  const [analytics, setAnalytics] = useState<LeadOverviewAnalytics | null>(null);
  const [days, setDays] = useState(14);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(() => !cachedLeads || !cachedWorkspace);
  const [refreshing, setRefreshing] = useState(false);
  const requestId = useRef(0);

  const load = useCallback(async (period: number, background = false) => {
    const currentRequest = ++requestId.current;
    if (background || cachedLeads || cachedWorkspace) setRefreshing(true); else setLoading(true);
    setError("");
    try {
      const [leads, workspace, nextAnalytics] = await Promise.all([api.leadSummary(), api.workspaceSummary(), api.leadOverviewAnalytics(period)]);
      if (currentRequest !== requestId.current) return;
      setLeadSummary(leads); setWorkSummary(workspace); setAnalytics(nextAnalytics);
    } catch (caught) {
      if (currentRequest === requestId.current) setError(caught instanceof Error ? caught.message : "Today’s activity could not be loaded.");
    } finally {
      if (currentRequest === requestId.current) { setLoading(false); setRefreshing(false); }
    }
  }, [cachedLeads, cachedWorkspace]);
  useEffect(() => { const timer = window.setTimeout(() => void load(days, Boolean(cachedLeads || cachedWorkspace)), 0); return () => window.clearTimeout(timer); }, [cachedLeads, cachedWorkspace, days, load]);

  const conversion = useMemo(() => leadSummary?.total ? Math.round((leadSummary.closed / leadSummary.total) * 1000) / 10 : null, [leadSummary]);
  const overdue = workSummary ? workSummary.follow_ups.overdue + workSummary.tasks.overdue : null;
  const kpis: Kpi[] = [
    { label: user.role === "EMPLOYEE" ? "My leads" : "Total leads", value: leadSummary?.total ?? null, supporting: `Visible in your ${leadSummary?.scope ?? "authorized"} workspace`, href: "/leads", icon: "users", tone: "bg-[#f0e9f8] text-[#805bab]" },
    { label: "Site visits", value: leadSummary?.site_visits ?? null, supporting: "Requested or completed visits", href: "/site-visits", icon: "building", tone: "bg-[#fff0e9] text-[#bd6333]" },
    { label: "Closings", value: leadSummary?.closed ?? null, supporting: "Leads marked closed", href: "/leads?status=CLOSED", icon: "trend", tone: "bg-[#e8f7f2] text-[#15836d]" },
    { label: "Follow-ups due", value: workSummary?.follow_ups.today ?? null, supporting: "Scheduled for today", href: "/follow-ups", icon: "clock", tone: "bg-[#edf0f8] text-[#42537d]" },
  ];

  return <div className="space-y-6 sm:space-y-7">
    <section className="relative overflow-hidden rounded-[24px] border border-[#e2d7ee] bg-[linear-gradient(112deg,#f4edfb_0%,#fffefe_52%,#edf8f5_100%)] px-5 py-5 shadow-[0_16px_34px_rgba(34,35,68,.07)] sm:px-6"><div className="absolute -right-12 -top-16 h-52 w-52 rounded-full border-[18px] border-[#cbb3e8]/30" /><div className="absolute -bottom-24 right-[28%] h-40 w-40 rounded-full bg-[#e8b8a5]/25 blur-2xl" /><div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div><p className="text-[10px] font-bold tracking-[.16em] text-[#805bab]">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" }).toUpperCase()}</p><h1 className="mt-1.5 text-2xl font-bold tracking-tight text-[#222344] sm:text-[28px]">{greeting()}, {user.username} <span aria-hidden="true">👋</span></h1><p className="mt-1.5 max-w-2xl text-sm leading-6 text-[#66738d]">Your daily CRM command center, with the conversations and work that deserve attention first.</p></div><div className="flex flex-wrap gap-2.5"><Link href="/leads?create=1" className="brand-button focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl px-4 text-sm font-bold text-white"><Icon name="plus" className="h-4 w-4" />New lead</Link><Link href="/site-visits" className="subtle-button focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl border border-[#d9cbe9] bg-white/85 px-4 text-sm font-bold text-[#684496]"><Icon name="calendar" className="h-4 w-4" />Site visits</Link></div></div></section>
    {error && <section role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#f1cbd3] bg-[#fff7f8] px-5 py-4 text-sm text-[#9e364b]"><span>{error}</span><button type="button" onClick={() => void load(days)} className="focus-ring rounded-lg px-2 py-1 font-bold text-[#8e2e44] underline">Retry</button></section>}
    <section><div className="mb-4 flex items-end justify-between gap-4"><div><p className="text-[11px] font-bold tracking-[.14em] text-[#805bab]">LIVE CRM METRICS</p><h2 className="mt-1 text-xl font-bold tracking-tight text-[#17233f]">Your command center</h2></div><p className="hidden text-xs text-[#77829a] sm:block">{refreshing ? "Refreshing metrics…" : "Metrics respect your current workspace permissions."}</p></div>{loading ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <div key={index} className="shimmer h-[178px] rounded-2xl" />)}</div> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{kpis.map((item) => <KpiCard key={item.label} item={item} />)}</div>}</section>
    <section className="grid gap-5 xl:grid-cols-[1.2fr_.8fr]"><ChartPanel eyebrow="LEAD MOMENTUM" title={`New leads across the last ${days} days`} action={<div className="flex rounded-lg bg-[#f3f0f8] p-0.5">{[14, 30].map((period) => <button key={period} onClick={() => setDays(period)} className={`focus-ring rounded-md px-2.5 py-1 text-xs font-bold ${days === period ? "bg-white text-[#684496] shadow-sm" : "text-[#77829a]"}`}>{period}d</button>)}</div>}><LineChart data={analytics?.growth ?? []} ariaLabel="New lead growth over the selected period" /></ChartPanel><ChartPanel eyebrow="CONVERSION SNAPSHOT" title="Current pipeline progression"><FunnelChart data={analytics?.funnel ?? []} ariaLabel="Current lead pipeline progression" /><p className="mt-4 text-xs leading-5 text-[#77829a]">A current-status snapshot: stages are not historical cohorts, so values can overlap as a lead advances.</p></ChartPanel></section>
    <section className="grid gap-5 xl:grid-cols-2"><ChartPanel eyebrow="PIPELINE MIX" title="Lead status comparison"><BarChart data={analytics?.pipeline ?? []} ariaLabel="Lead pipeline status comparison" /></ChartPanel><ChartPanel eyebrow="ACQUISITION" title="Lead source distribution"><DonutChart data={analytics?.sources ?? []} ariaLabel="Lead source distribution" /></ChartPanel></section>
    <section className="grid gap-5 xl:grid-cols-[.9fr_1.1fr]"><ChartPanel eyebrow="WORK TO PROTECT" title="Keep the right things moving"><div className="grid gap-3 sm:grid-cols-2">{[{ label: "Hot leads", value: leadSummary?.hot ?? null, note: "Prioritize high-intent conversations", href: "/leads?temperature=HOT", tone: "bg-[#fff0e9] text-[#bd6333]" }, { label: "Overdue work", value: overdue, note: "Follow-ups and tasks needing attention", href: "/follow-ups", tone: "bg-[#fff0f3] text-[#b43f58]" }, { label: "Tasks due", value: workSummary?.tasks.due_today ?? null, note: "Complete scheduled work today", href: "/tasks", tone: "bg-[#e8f7f2] text-[#15836d]" }, { label: "Conversion rate", value: conversion, note: "Closed leads as a share of visible leads", href: "/leads?status=CLOSED", tone: "bg-[#edf0f8] text-[#42537d]" }].map((item) => <Link key={item.label} href={item.href} className="subtle-button focus-ring rounded-xl border border-[#e8e2ee] p-4"><span className={`flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold ${item.tone}`}>{item.value === null ? "—" : item.label === "Conversion rate" ? `${item.value}%` : item.value}</span><strong className="mt-3 block text-sm text-[#293754]">{item.label}</strong><small className="mt-1 block text-xs leading-5 text-[#77829a]">{item.note}</small></Link>)}</div></ChartPanel><ChartPanel eyebrow="PERMISSION-SAFE DATA" title="One dashboard, the right scope"><div className="rounded-xl border border-[#e6deed] bg-[#fcfbfd] p-5"><p className="text-sm leading-6 text-[#56627b]">Your dashboard only aggregates the leads and work records that your role can access. CEO users see their company, managers see their team, and employees see their own workspace.</p><div className="mt-5 flex flex-wrap gap-3"><Link href="/leads" className="focus-ring inline-flex items-center gap-2 rounded-lg bg-[#f0e9f8] px-3 py-2 text-sm font-bold text-[#684496]">Open lead pipeline <Icon name="arrow" className="h-4 w-4" /></Link><Link href="/tasks" className="focus-ring inline-flex items-center gap-2 rounded-lg border border-[#dfd6e9] px-3 py-2 text-sm font-bold text-[#56627b]">Review tasks</Link></div></div></ChartPanel></section>
  </div>;
}
