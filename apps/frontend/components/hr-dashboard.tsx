"use client";
/* eslint-disable react-hooks/set-state-in-effect -- API state resolves asynchronously. */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { BarChart, DonutChart, LineChart } from "@/components/dashboard-charts";
import { api } from "@/lib/api";
import type { HRDashboard, Role } from "@/lib/types";

const day = (value: string) => new Date(value + "T00:00:00").toLocaleDateString(undefined, { weekday: "short" });
const checkInTime = (value: string | null) => value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";
type MetricTone = "primary" | "success" | "warning" | "info" | "danger" | "neutral";

function Metric({ name, value, tone }: { name: string; value: number; tone: MetricTone }) {
  return <article className={"app-card hr-metric hr-metric--" + tone + " rounded-2xl"}><p className="hr-metric__name text-sm font-medium">{name}</p><p className="hr-metric__value metric-value mt-2 text-3xl font-bold tracking-tight">{value}</p></article>;
}

function Empty({ text }: { text: string }) { return <p className="hr-empty py-9 text-center text-sm">{text}</p>; }
function activityColor(status: string) { return status === "CHECKED_IN" ? "var(--success)" : status === "CHECKED_OUT" ? "var(--info)" : "var(--ink-muted)"; }

export function HRDashboardPage({ role }: { role: Role }) {
  const [data, setData] = useState<HRDashboard | null>(() => api.peekHRDashboard() ?? null);
  const [error, setError] = useState("");
  const load = useCallback(async () => { try { setError(""); setData(await api.hrDashboard()); } catch (caught) { setError(caught instanceof Error ? caught.message : "HR dashboard could not be loaded."); } }, []);
  useEffect(() => { void load(); }, [load]);

  if (error) return <section className="rounded-2xl border border-[color-mix(in_srgb,var(--danger)_32%,var(--line))] bg-[color-mix(in_srgb,var(--danger)_11%,var(--surface-muted))] p-6 text-[var(--danger)]"><p>{error}</p><button onClick={() => void load()} className="focus-ring mt-3 rounded-lg px-2 py-1 font-bold underline">Retry</button></section>;
  if (!data) return <section className="space-y-5"><div className="shimmer h-48 rounded-3xl" /><div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, index) => <div key={index} className="shimmer h-28 rounded-2xl" />)}</div></section>;

  const maxTrend = Math.max(1, ...data.attendance.trend.flatMap((item) => [item.present, item.late, item.on_leave, item.absent]));
  const summary: Array<[string, number, MetricTone]> = [["Total employees", data.kpis.total_employees, "primary"], ["Present", data.attendance.present, "success"], ["Late", data.attendance.late, "warning"], ["On leave", data.attendance.on_leave, "info"], ["Absent", data.attendance.absent, "danger"], ["Active now", data.attendance.working_now, "neutral"]];

  return <div className="space-y-6">
    <section className="hr-hero p-5 sm:p-6">
      <div className="hr-hero__orb absolute -right-12 -top-16 h-48 w-48 rounded-full border-[18px]" />
      <div className="hr-hero__glow absolute -bottom-20 right-20 h-40 w-40 rounded-full blur-2xl" />
      <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div><p className="hr-eyebrow text-[10px] font-bold tracking-[.16em]">HUMAN RESOURCES · LIVE OPERATIONS</p><h1 className="hr-hero__title mt-1.5 text-2xl font-bold tracking-tight sm:text-[28px]">HR Command Center</h1><p className="hr-hero__copy mt-1.5 max-w-2xl text-sm leading-6">Workforce attendance, live availability, and sales activity across your {data.scope === "company" ? "company" : "authorized team"}.</p></div>
        <div className="flex flex-wrap gap-2.5"><Link href="/attendance" className="hr-primary-action focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl px-4 text-sm font-bold"><Icon name="clock" className="h-4 w-4" />Attendance</Link><Link href="/employees" className="hr-secondary-action focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-bold"><Icon name="users" className="h-4 w-4" />People</Link></div>
      </div>
    </section>

    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">{summary.map(([name, value, tone]) => <Metric key={name} name={name} value={value} tone={tone} />)}</section>

    <section className="grid gap-5 xl:grid-cols-[1.4fr_.85fr]">
      <article className="app-card rounded-2xl p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="hr-section-eyebrow text-[11px] font-bold tracking-[.14em]">ATTENDANCE INTELLIGENCE</p><h2 className="hr-section-title mt-1 text-lg font-bold">Seven-day attendance trend</h2><p className="hr-section-copy mt-1 text-sm">Recorded attendance and approved leave, not estimates.</p></div><span className="hr-percent-badge rounded-full px-3 py-1.5 text-xs font-bold">{data.attendance.percentage}% present today</span></div>
        <div className="mt-8 grid h-56 grid-cols-7 items-end gap-2 sm:gap-4">{data.attendance.trend.map((item) => <div key={item.date} className="flex h-full min-w-0 flex-col justify-end"><div className="flex h-[190px] items-end justify-center gap-0.5"><span title={"Present: " + item.present} className="chart-bar w-2 rounded-t sm:w-3" style={{ height: String(item.present / maxTrend * 100) + "%", background: "var(--success)" }} /><span title={"Late: " + item.late} className="chart-bar w-2 rounded-t sm:w-3" style={{ height: String(item.late / maxTrend * 100) + "%", background: "var(--warning)" }} /><span title={"Leave: " + item.on_leave} className="chart-bar w-2 rounded-t sm:w-3" style={{ height: String(item.on_leave / maxTrend * 100) + "%", background: "var(--info)" }} /><span title={"Absent: " + item.absent} className="chart-bar w-2 rounded-t sm:w-3" style={{ height: String(item.absent / maxTrend * 100) + "%", background: "var(--danger)" }} /></div><p className="hr-section-copy mt-3 text-center text-xs font-bold">{day(item.date)}</p></div>)}</div>
        <div className="hr-section-copy mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs"><span><i className="mr-1.5 inline-block h-2 w-2 rounded" style={{ background: "var(--success)" }} />Present</span><span><i className="mr-1.5 inline-block h-2 w-2 rounded" style={{ background: "var(--warning)" }} />Late</span><span><i className="mr-1.5 inline-block h-2 w-2 rounded" style={{ background: "var(--info)" }} />On leave</span><span><i className="mr-1.5 inline-block h-2 w-2 rounded" style={{ background: "var(--danger)" }} />Absent</span></div>
      </article>
      <article className="app-card rounded-2xl p-5 sm:p-6"><p className="hr-section-eyebrow text-[11px] font-bold tracking-[.14em]">WORKFORCE ACTIVITY</p><h2 className="hr-section-title mt-1 text-lg font-bold">Who&apos;s active now</h2><p className="hr-section-copy mt-1 text-sm">Today&apos;s employee check-in state.</p><div className="mt-5 space-y-1">{data.workforce_activity.length ? data.workforce_activity.slice(0, 6).map((item) => <Link href={"/employees/" + item.employee_id} key={item.employee_id} className="hr-activity-row focus-ring flex items-center gap-3 rounded-xl px-2 py-2.5 transition"><i className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: activityColor(item.status) }} /><span className="min-w-0 flex-1"><strong className="hr-activity-name block truncate text-sm">{item.employee_name}</strong><small className="hr-activity-meta mt-0.5 block text-xs">{item.status === "CHECKED_IN" ? "Checked in " + checkInTime(item.check_in_at) : item.status === "CHECKED_OUT" ? "Checked out" : "Not checked in"}</small></span><Icon name="chevron" className="hr-activity-chevron h-4 w-4" /></Link>) : <Empty text="No active employees in this workspace." />}</div><Link href="/attendance" className="hr-link focus-ring mt-5 inline-flex text-sm font-bold">Review attendance →</Link></article>
    </section>

    <section className="grid gap-5 xl:grid-cols-2">
      <article className="app-card rounded-2xl p-5 sm:p-6"><p className="hr-section-eyebrow text-[11px] font-bold tracking-[.14em]">ATTENDANCE PATTERN</p><h2 className="hr-section-title mt-1 text-lg font-bold">Present attendance over time</h2><p className="hr-section-copy mt-1 text-sm">A seven-day area trend from recorded attendance.</p><div className="mt-5"><LineChart data={data.attendance.trend.map((item) => ({ label: day(item.date), value: item.present }))} ariaLabel="Present attendance trend" /></div></article>
      <article className="app-card rounded-2xl p-5 sm:p-6"><p className="hr-section-eyebrow text-[11px] font-bold tracking-[.14em]">TASK FLOW</p><h2 className="hr-section-title mt-1 text-lg font-bold">Task status distribution</h2><p className="hr-section-copy mt-1 text-sm">Only tasks within your authorized workforce scope.</p><div className="mt-3"><DonutChart data={data.tasks.status_distribution} ariaLabel="Task status distribution" /></div></article>
    </section>

    <section className="app-card overflow-hidden rounded-2xl">
      <div className="hr-divider flex flex-wrap items-start justify-between gap-4 border-b p-5 sm:p-6"><div><p className="hr-section-eyebrow text-[11px] font-bold tracking-[.14em]">EMPLOYEE PERFORMANCE</p><h2 className="hr-section-title mt-1 text-lg font-bold">Sales performance leaderboard</h2><p className="hr-section-copy mt-1 text-sm">Ranked by closings, then completed site visits. Attendance is deliberately separate.</p></div><Link href="/employees" className="hr-link focus-ring text-sm font-bold">Open people →</Link></div>
      {data.performance.leaderboard.length ? <><div className="hr-divider border-b p-5 sm:p-6"><BarChart horizontal data={data.performance.leaderboard.slice(0, 6).map((item) => ({ label: item.employee_name, value: item.closings }))} ariaLabel="Employee closings comparison" /></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left"><thead className="hr-table-head text-[11px] font-bold uppercase tracking-[.1em]"><tr><th className="px-6 py-3">Rank</th><th className="px-4 py-3">Employee</th><th className="px-4 py-3 text-right">Leads</th><th className="px-4 py-3 text-right">Contacted</th><th className="px-4 py-3 text-right">Site visits</th><th className="px-4 py-3 text-right">Closings</th><th className="px-6 py-3 text-right">Conversion</th></tr></thead><tbody className="hr-table-rule divide-y">{data.performance.leaderboard.map((item, index) => <tr key={item.employee_id} className="hr-table-row transition"><td className="px-6 py-4"><span className={"hr-rank " + (index < 3 ? "hr-rank--top " : "") + "flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold"}>{index + 1}</span></td><td className="px-4 py-4"><Link href={"/employees/" + item.employee_id} className="hr-table-name focus-ring font-bold hover:text-[var(--brand-strong)]">{item.employee_name}</Link></td><td className="hr-table-value px-4 py-4 text-right text-sm font-semibold">{item.leads_assigned}</td><td className="hr-table-value px-4 py-4 text-right text-sm font-semibold">{item.leads_contacted}</td><td className="px-4 py-4 text-right text-sm font-bold text-[var(--brand-strong)]">{item.site_visits}</td><td className="px-4 py-4 text-right text-sm font-bold text-[var(--success)]">{item.closings}</td><td className="hr-table-value px-6 py-4 text-right text-sm font-bold">{item.conversion_rate}%</td></tr>)}</tbody></table></div></> : <Empty text="No employee performance data is available yet." />}
    </section>

    <section className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]">
      <article className="app-card rounded-2xl p-5 sm:p-6"><p className="hr-section-eyebrow text-[11px] font-bold tracking-[.14em]">WORKFORCE DISTRIBUTION</p><h2 className="hr-section-title mt-1 text-lg font-bold">Teams and departments</h2><div className="mt-5 space-y-4">{data.distribution.departments.length ? data.distribution.departments.map((item) => <div key={item.department__name}><div className="flex justify-between gap-3 text-sm"><span className="hr-department-name truncate font-medium">{item.department__name}</span><strong className="hr-table-value">{item.count}</strong></div><div className="hr-progress-track mt-2 h-2 overflow-hidden rounded-full"><div className="hr-progress-value h-full rounded-full" style={{ width: String(item.count / Math.max(1, ...data.distribution.departments.map((entry) => entry.count)) * 100) + "%" }} /></div></div>) : <Empty text="No department data yet." />}</div></article>
      <article className="app-card overflow-hidden rounded-2xl"><div className="hr-divider border-b p-5 sm:p-6"><p className="hr-section-eyebrow text-[11px] font-bold tracking-[.14em]">RECENT ACTIVITY</p><h2 className="hr-section-title mt-1 text-lg font-bold">HR activity stream</h2></div>{data.activity.length ? <div className="hr-table-rule divide-y">{data.activity.slice(0, 5).map((item) => <div key={item.id} className="flex gap-3 p-4 sm:px-6"><span className="hr-activity-icon mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"><Icon name="sparkle" className="h-3.5 w-3.5" /></span><div className="min-w-0 flex-1"><p className="hr-activity-name text-sm font-bold">{item.action.replaceAll(".", " ")}</p><p className="hr-activity-meta mt-1 text-xs">{item.actor}{item.reason ? " · " + item.reason : ""}</p></div><time className="hr-activity-meta whitespace-nowrap text-[11px]">{new Date(item.created_at).toLocaleDateString()}</time></div>)}</div> : <Empty text="No recent HR activity." />}</article>
    </section>
    {role === "CEO" && <p className="hr-section-copy px-1 text-xs">All workforce and performance metrics are scoped to your company.</p>}
  </div>;
}
