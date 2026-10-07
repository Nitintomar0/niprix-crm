"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { LeadSummary, User, WorkspaceSummary } from "@/lib/types";

type Metric = {
  label: string;
  value: number;
  hint: string;
  href: string;
  icon: "users" | "clock" | "check" | "calendar";
  alert?: boolean;
};

export function Overview({ user }: { user: User }) {
  const [leadSummary, setLeadSummary] = useState<LeadSummary | null>(null);
  const [workSummary, setWorkSummary] = useState<WorkspaceSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!window.matchMedia("(max-width: 767px)").matches) return;
    let active = true;
    void Promise.all([api.leadSummary(), api.workspaceSummary()])
      .then(([leads, workspace]) => {
        if (!active) return;
        setLeadSummary(leads);
        setWorkSummary(workspace);
      })
      .catch(() => {
        if (active) setError("Today’s activity could not be loaded.");
      });
    return () => { active = false; };
  }, []);

  const overdue = (workSummary?.follow_ups.overdue ?? 0) + (workSummary?.tasks.overdue ?? 0);
  const metrics: Metric[] = [
    { label: "Hot leads", value: leadSummary?.hot ?? 0, hint: "Need attention", href: "/leads", icon: "users", alert: Boolean(leadSummary?.hot) },
    { label: "Follow-ups today", value: workSummary?.follow_ups.today ?? 0, hint: "Keep conversations moving", href: "/follow-ups", icon: "clock" },
    { label: "Overdue", value: overdue, hint: "Resolve first", href: "/follow-ups", icon: "calendar", alert: Boolean(overdue) },
    { label: "Tasks due", value: workSummary?.tasks.due_today ?? 0, hint: "Complete today", href: "/tasks", icon: "check" },
  ];

  return <>
    <section className="space-y-5 md:hidden">
      <div className="pt-1">
        <p className="text-sm font-medium text-[#60708a]">Good day, {user.username}.</p>
        <h1 className="mt-1 text-[24px] font-bold tracking-tight text-[#10233f]">Here&apos;s your focus for today.</h1>
      </div>
      {error && <div role="alert" className="rounded-2xl border border-[#f3cbd1] bg-[#fff7f8] px-4 py-3 text-sm text-[#9e3643]">{error}</div>}
      <section className="brand-gradient relative overflow-hidden rounded-[22px] p-5 text-white shadow-[0_14px_28px_rgba(6,58,138,.18)]">
        <div className="absolute -right-12 -top-16 h-40 w-40 rounded-full border border-white/10" />
        <div className="absolute -bottom-16 right-8 h-32 w-32 rounded-full bg-[#ff8700]/25 blur-2xl" />
        <div className="relative"><p className="text-xs font-semibold tracking-[.12em] text-blue-100">YOUR WORKSPACE</p><p className="mt-2 text-xl font-bold">Turn the next conversation into momentum.</p><Link href="/leads" className="focus-ring mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 text-sm font-bold text-[#0869d8]">Open leads <Icon name="arrow" className="h-4 w-4" /></Link></div>
      </section>
      <section>
        <div className="mb-3 flex items-center justify-between"><h2 className="text-[17px] font-bold text-[#203756]">Today&apos;s overview</h2><Link href="/leads" className="text-xs font-bold text-[#0869d8]">View leads</Link></div>
        <div className="grid grid-cols-2 gap-3">{metrics.map((metric) => <Link key={metric.label} href={metric.href} className="focus-ring min-h-[132px] rounded-2xl border border-[#e1e9f2] bg-white p-4 shadow-[0_8px_18px_rgba(21,43,76,.045)]"><span className={`flex h-9 w-9 items-center justify-center rounded-xl ${metric.alert ? "bg-[#fff1e8] text-[#e66d00]" : "bg-[#eaf4ff] text-[#0869d8]"}`}><Icon name={metric.icon} className="h-[18px] w-[18px]" /></span><p className={`mt-3 text-2xl font-bold ${metric.alert ? "text-[#d75e1d]" : "text-[#203756]"}`}>{leadSummary || workSummary ? metric.value : "—"}</p><p className="mt-1 text-[13px] font-bold text-[#405773]">{metric.label}</p><p className="mt-0.5 text-[11px] text-[#8291a4]">{metric.hint}</p></Link>)}</div>
      </section>
      <section className="rounded-2xl border border-[#e1e9f2] bg-white p-4"><h2 className="text-[17px] font-bold text-[#203756]">Quick actions</h2><div className="mt-3 grid grid-cols-2 gap-2"><Link href="/follow-ups" className="focus-ring flex min-h-12 items-center gap-2 rounded-xl bg-[#f5f9fe] px-3 text-sm font-bold text-[#0869d8]"><Icon name="clock" className="h-4 w-4" />Follow-ups</Link><Link href="/tasks" className="focus-ring flex min-h-12 items-center gap-2 rounded-xl bg-[#f7faf8] px-3 text-sm font-bold text-[#168460]"><Icon name="check" className="h-4 w-4" />Tasks</Link><Link href="/attendance" className="focus-ring col-span-2 flex min-h-12 items-center justify-between rounded-xl border border-[#e2eaf4] px-3 text-sm font-bold text-[#405773]"><span className="flex items-center gap-2"><Icon name="clock" className="h-4 w-4 text-[#0869d8]" />My attendance</span><Icon name="chevron" className="h-4 w-4 text-[#8291a4]" /></Link></div></section>
    </section>
    <section className="hidden md:block">
      <p className="text-sm font-medium text-[#0869d8]">WORKSPACE OVERVIEW</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-[#10233f]">Welcome back, {user.username}.</h1>
      <p className="mt-2 text-sm text-[#60708a]">Your NIPRIX workspace brings people, attendance, and future CRM activity into one focused place.</p>
      <div className="mt-7 grid gap-5 lg:grid-cols-[1.25fr_.75fr]">
        <div className="brand-gradient relative overflow-hidden rounded-2xl p-7 text-white shadow-[0_16px_34px_rgba(6,58,138,.16)] sm:p-9"><div className="absolute -right-20 -top-24 h-64 w-64 rounded-full border border-white/10" /><div className="absolute -bottom-20 right-14 h-48 w-48 rounded-full bg-[#ff8700]/25 blur-2xl" /><div className="relative"><span className="inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold">TODAY&apos;S FOCUS</span><h2 className="mt-5 max-w-lg text-3xl font-semibold tracking-tight">Keep your workday on track.</h2><p className="mt-3 max-w-lg text-sm leading-6 text-blue-100">Check your status, record time, and review your recent attendance from one dedicated view.</p><Link href="/attendance" className="focus-ring mt-7 inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-bold text-[#075ec0] shadow-lg transition hover:bg-[#f3f9ff]">Open my attendance<Icon name="arrow" className="h-4 w-4" /></Link></div></div>
        <div className="app-card rounded-2xl p-6 sm:p-7"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#eff6fe] text-[#0869d8]"><Icon name="sparkle" className="h-5 w-5" /></span><h2 className="mt-5 text-xl font-semibold tracking-tight text-[#203756]">Built to grow with you</h2><p className="mt-3 text-sm leading-6 text-[#718198]">People, leads, follow-ups, and insights are being prepared as connected NIPRIX workspaces.</p><p className="mt-6 text-xs font-semibold tracking-[.12em] text-[#8a98aa]">ENTERPRISE CRM FOUNDATION</p></div>
      </div>
    </section>
  </>;
}
