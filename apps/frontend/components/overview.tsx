"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { LeadSummary, User, WorkspaceSummary } from "@/lib/types";

type Kpi = { label: string; value: number | null; supporting: string; href: string; icon: "users" | "building" | "trend" | "clock"; tone: "blue" | "orange" | "green" | "navy" };

const toneStyles: Record<Kpi["tone"], string> = {
  blue: "bg-[#eaf4ff] text-[#0869d8]",
  orange: "bg-[#fff3e4] text-[#e27400]",
  green: "bg-[#eaf8f1] text-[#168460]",
  navy: "bg-[#e9eef6] text-[#0b1f3a]",
};

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

function KpiCard({ item }: { item: Kpi }) {
  return <Link href={item.href} className="focus-ring group app-card rounded-2xl p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_32px_rgba(21,43,76,.1)]"><div className="flex items-start justify-between gap-3"><span className={`flex h-10 w-10 items-center justify-center rounded-xl ${toneStyles[item.tone]}`}><Icon name={item.icon} className="h-5 w-5" /></span><Icon name="arrow" className="h-4 w-4 text-[#9aa8b9] transition group-hover:translate-x-0.5 group-hover:text-[#0869d8]" /></div><p className="mt-5 text-3xl font-bold tracking-tight text-[#10233f]">{item.value === null ? "—" : item.value.toLocaleString("en-IN")}</p><p className="mt-1.5 text-sm font-bold text-[#405773]">{item.label}</p><p className="mt-1 text-xs leading-5 text-[#7a8aa0]">{item.supporting}</p></Link>;
}

export function Overview({ user }: { user: User }) {
  const [leadSummary, setLeadSummary] = useState<LeadSummary | null>(null);
  const [workSummary, setWorkSummary] = useState<WorkspaceSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void Promise.all([api.leadSummary(), api.workspaceSummary()]).then(([leads, workspace]) => {
      if (!active) return;
      setLeadSummary(leads);
      setWorkSummary(workspace);
    }).catch((caught) => {
      if (active) setError(caught instanceof Error ? caught.message : "Today’s activity could not be loaded.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const conversion = useMemo(() => leadSummary && leadSummary.total ? Math.round((leadSummary.closed / leadSummary.total) * 1000) / 10 : null, [leadSummary]);
  const overdue = workSummary ? workSummary.follow_ups.overdue + workSummary.tasks.overdue : null;
  const kpis: Kpi[] = [
    { label: user.role === "EMPLOYEE" ? "My leads" : "Total leads", value: leadSummary?.total ?? null, supporting: `Visible in your ${leadSummary?.scope ?? "authorized"} workspace`, href: "/leads", icon: "users", tone: "blue" },
    { label: "Site visits", value: leadSummary?.site_visits ?? null, supporting: "Requested or completed visits", href: "/leads", icon: "building", tone: "orange" },
    { label: "Closings", value: leadSummary?.closed ?? null, supporting: "Leads marked closed", href: "/leads", icon: "trend", tone: "green" },
    { label: "Follow-ups due", value: workSummary?.follow_ups.today ?? null, supporting: "Scheduled for today", href: "/follow-ups", icon: "clock", tone: "navy" },
  ];
  const work = [
    { label: "Hot leads", value: leadSummary?.hot ?? null, note: "Prioritize high-intent conversations", href: "/leads", tone: "bg-[#fff0e7] text-[#d96a00]" },
    { label: "Follow-ups due", value: workSummary?.follow_ups.today ?? null, note: "Keep customer momentum moving", href: "/follow-ups", tone: "bg-[#eaf4ff] text-[#0869d8]" },
    { label: "Overdue work", value: overdue, note: "Follow-ups and tasks needing attention", href: "/follow-ups", tone: "bg-[#fff0f1] text-[#bd3041]" },
    { label: "Tasks due", value: workSummary?.tasks.due_today ?? null, note: "Complete scheduled work today", href: "/tasks", tone: "bg-[#eaf8f1] text-[#168460]" },
  ];

  return <div className="space-y-6 sm:space-y-7">
    <section className="relative overflow-hidden rounded-[24px] bg-[#0b1f3a] px-6 py-7 text-white shadow-[0_20px_46px_rgba(11,31,58,.2)] sm:px-8 sm:py-9"><div className="absolute -right-20 -top-24 h-72 w-72 rounded-full border border-white/10" /><div className="absolute bottom-[-110px] right-[22%] h-56 w-56 rounded-full bg-[#1497f2]/25 blur-2xl" /><div className="absolute -bottom-20 left-[42%] h-48 w-48 rounded-full bg-[#ff8a00]/20 blur-2xl" /><div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between"><div><p className="text-xs font-bold tracking-[.16em] text-[#9ed5ff]">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" }).toUpperCase()}</p><h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">{greeting()}, {user.username} <span aria-hidden="true">👋</span></h1><p className="mt-3 max-w-2xl text-sm leading-6 text-[#c6e2fb]">Here&apos;s what&apos;s happening across your NIPRIX {user.role === "CEO" ? "company" : user.role === "MANAGER" ? "team" : "workspace"} today.</p></div><div className="flex flex-wrap gap-3"><Link href="/leads?create=1" className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 text-sm font-bold text-[#0869d8] shadow-lg transition hover:bg-[#eff8ff]"><Icon name="plus" className="h-4 w-4" />New lead</Link><Link href="/follow-ups" className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-4 text-sm font-bold text-white transition hover:bg-white/15"><Icon name="clock" className="h-4 w-4" />View follow-ups</Link></div></div></section>
    {error && <section role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#f3cbd1] bg-[#fff7f8] px-5 py-4 text-sm text-[#9e3643]"><span>{error}</span><button type="button" onClick={() => window.location.reload()} className="focus-ring rounded-lg px-2 py-1 font-bold text-[#a72536] underline">Retry</button></section>}
    <section><div className="mb-4 flex items-end justify-between gap-4"><div><p className="text-[11px] font-bold tracking-[.14em] text-[#0869d8]">LIVE CRM METRICS</p><h2 className="mt-1 text-xl font-bold tracking-tight text-[#10233f]">Your command center</h2></div><p className="hidden text-xs text-[#718198] sm:block">Metrics respect your current workspace permissions.</p></div>{loading ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <div key={index} className="shimmer h-[178px] rounded-2xl" />)}</div> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{kpis.map((item) => <KpiCard key={item.label} item={item} />)}</div>}</section>
    <section className="grid gap-5 xl:grid-cols-[1.25fr_.75fr]"><article className="app-card rounded-2xl p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[11px] font-bold tracking-[.14em] text-[#0869d8]">PIPELINE HEALTH</p><h2 className="mt-1 text-lg font-bold text-[#10233f]">Lead conversion at a glance</h2><p className="mt-1 text-sm text-[#718198]">Live lead status totals from your authorized pipeline.</p></div><Link href="/leads" className="focus-ring text-sm font-bold text-[#0869d8]">Open pipeline →</Link></div><div className="mt-7 grid gap-6 sm:grid-cols-[.75fr_1.25fr]"><div className="rounded-2xl bg-[#f5f9fe] p-5"><p className="text-xs font-bold tracking-[.11em] text-[#718198]">CONVERSION RATE</p><p className="mt-2 text-4xl font-bold tracking-tight text-[#10233f]">{conversion === null ? "—" : `${conversion}%`}</p><p className="mt-2 text-xs leading-5 text-[#718198]">Closed leads as a share of visible leads.</p></div><div className="space-y-4">{[{ label: "New leads", value: leadSummary?.new ?? null, color: "bg-[#1497f2]" }, { label: "Contacted", value: leadSummary?.contacted ?? null, color: "bg-[#0869d8]" }, { label: "Need follow-up", value: leadSummary?.follow_up_needed ?? null, color: "bg-[#ff8a00]" }, { label: "Closed", value: leadSummary?.closed ?? null, color: "bg-[#168460]" }].map((item) => <div key={item.label}><div className="flex items-center justify-between text-sm"><span className="font-medium text-[#526984]">{item.label}</span><strong className="text-[#10233f]">{item.value === null ? "—" : item.value}</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-[#edf2f7]"><div className={`h-full rounded-full ${item.color}`} style={{ width: leadSummary?.total ? `${Math.min(100, (Number(item.value) / leadSummary.total) * 100)}%` : "0%" }} /></div></div>)}</div></div></article>
      <article className="app-card rounded-2xl p-5 sm:p-6"><p className="text-[11px] font-bold tracking-[.14em] text-[#ff8a00]">TODAY&apos;S WORK</p><h2 className="mt-1 text-lg font-bold text-[#10233f]">Keep the right things moving</h2><div className="mt-5 divide-y divide-[#edf1f6]">{work.map((item) => <Link key={item.label} href={item.href} className="focus-ring flex items-center gap-3 py-3.5 first:pt-0 last:pb-0"><span className={`flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold ${item.tone}`}>{item.value === null ? "—" : item.value}</span><span className="min-w-0 flex-1"><strong className="block text-sm text-[#253a59]">{item.label}</strong><small className="mt-0.5 block truncate text-xs text-[#718198]">{item.note}</small></span><Icon name="chevron" className="h-4 w-4 text-[#9ba8b8]" /></Link>)}</div></article></section>
  </div>;
}
