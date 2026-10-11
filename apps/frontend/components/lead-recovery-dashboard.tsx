"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/icons";
import { LeadBadge } from "@/components/lead-badge";
import { api } from "@/lib/api";
import type { EmployeeOption, LeadRecoveryCategory, LeadRecoverySummary, RecoveryLead, Role } from "@/lib/types";

const categories: Array<{ value: LeadRecoveryCategory; label: string; count: keyof LeadRecoverySummary }> = [
  { value: "NOT_PICK_CALL", label: "Not Pick Call", count: "not_pick_call" },
  { value: "NOT_INTERESTED", label: "Not Interested", count: "not_interested" },
];
const sources = ["MANUAL", "WHATSAPP", "FACEBOOK", "INSTAGRAM", "META_LEAD_AD", "WEBSITE", "REFERRAL", "OTHER"];
const label = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
const contactNumber = (phone: string) => phone.replace(/\D/g, "").replace(/^00/, "");
const hasPhone = (phone: string) => /^\d{7,15}$/.test(contactNumber(phone));

function Dialog({ title, close, children }: { title: string; close: () => void; children: React.ReactNode }) {
  return <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4"><button aria-label="Close" onClick={close} className="mobile-sheet-backdrop absolute inset-0" /><section className="mobile-sheet relative max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-[24px] bg-white p-5 shadow-2xl sm:rounded-2xl sm:p-6"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-bold text-[#203756]">{title}</h2><button aria-label="Close" onClick={close} className="focus-ring rounded-lg p-1 text-[#60708a]"><Icon name="close" className="h-5 w-5" /></button></div>{children}</section></div>;
}

export function LeadRecoveryDashboard({ role }: { role: Role }) {
  const [category, setCategory] = useState<LeadRecoveryCategory>("NOT_PICK_CALL");
  const [rows, setRows] = useState<RecoveryLead[]>([]);
  const [summary, setSummary] = useState<LeadRecoverySummary | null>(null);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [followUpLead, setFollowUpLead] = useState<RecoveryLead | null>(null);
  const [deleteLead, setDeleteLead] = useState<RecoveryLead | null>(null);
  const latestLoad = useRef(0);
  const active = categories.find((item) => item.value === category)!;

  const load = useCallback(async () => {
    const requestId = ++latestLoad.current;
    setLoading(true); setError("");
    const query = new URLSearchParams({ page: String(page), page_size: "12" });
    if (search.trim()) query.set("search", search.trim());
    if (source) query.set("source", source);
    if (assignedTo) query.set("assigned_to", assignedTo);
    try {
      const requests: [ReturnType<typeof api.recoveryLeads>, ReturnType<typeof api.leadRecoverySummary>, ReturnType<typeof api.employees> | Promise<EmployeeOption[]>] = [
        api.recoveryLeads(category, query.toString()), api.leadRecoverySummary(), role === "CEO" ? api.employees() : Promise.resolve([]),
      ];
      const [recovery, counts, people] = await Promise.all(requests);
      if (requestId !== latestLoad.current) return;
      setRows(recovery.results); setCount(recovery.count); setSummary(counts); setEmployees(Array.isArray(people) ? people : people.results);
    } catch (caught) {
      if (requestId === latestLoad.current) setError(caught instanceof Error ? caught.message : "Could not load recovery leads.");
    } finally { if (requestId === latestLoad.current) setLoading(false); }
  }, [assignedTo, category, page, role, search, source]);

  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 250); return () => window.clearTimeout(timer); }, [load]);
  const refresh = async () => { await load(); };
  async function restore(lead: RecoveryLead) {
    setBusy(lead.id); setError("");
    try { await api.restoreLead(lead.id); await refresh(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not restore this lead."); } finally { setBusy(null); }
  }
  async function reassign(lead: RecoveryLead, employeeId: string) {
    if (!employeeId) return;
    setBusy(lead.id); setError("");
    try { await api.assignLead(lead.id, Number(employeeId), "Reassigned from Lead Recovery"); await refresh(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not reassign this lead."); } finally { setBusy(null); }
  }
  async function remove(lead: RecoveryLead) {
    setBusy(lead.id); setError("");
    try { await api.deleteLead(lead.id); setDeleteLead(null); await refresh(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not permanently delete this lead."); } finally { setBusy(null); }
  }
  async function moveToFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!followUpLead) return;
    const form = new FormData(event.currentTarget); const scheduledAt = String(form.get("scheduled_at") || "");
    if (!scheduledAt) { setError("Choose the next action date and time."); return; }
    setBusy(followUpLead.id); setError("");
    try {
      await api.moveLeadToFollowUp(followUpLead.id, { title: String(form.get("title") || ""), description: String(form.get("description") || ""), scheduled_at: new Date(scheduledAt).toISOString(), follow_up_type: "CALL", priority: "MEDIUM" });
      setFollowUpLead(null); await refresh();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not move this lead to Follow-up."); } finally { setBusy(null); }
  }

  return <section className="space-y-5 sm:space-y-6">
    <div className="rounded-2xl border border-[#dfe8f3] bg-[linear-gradient(135deg,#ffffff_0%,#f1f7ff_100%)] p-4 shadow-[0_12px_30px_rgba(22,55,94,.06)] sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.12em] text-[#4e84bd]">Sales recovery workspace</p><h1 className="mt-1 text-2xl font-bold tracking-tight text-[#17385d]">Lead Recovery</h1><p className="mt-1 text-sm text-[#60708a]">Recover missed opportunities without losing lead history.</p></div><Link href="/leads" className="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-[#b8d1ea] bg-white px-3.5 text-sm font-bold text-[#155ca8]"><Icon name="back" className="h-4 w-4" />Active leads</Link></div>
      <div role="tablist" aria-label="Recovery category" className="mt-5 flex w-full gap-2 overflow-x-auto pb-1 sm:w-auto">
        {categories.map((item) => <button key={item.value} role="tab" aria-selected={category === item.value} onClick={() => { setCategory(item.value); setPage(1); }} className={`focus-ring inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg px-3.5 text-sm font-bold ${category === item.value ? "bg-[#102f55] text-white shadow-sm" : "border border-[#d9e4f0] bg-white text-[#405773]"}`}>{item.label}<span className={`rounded-full px-2 py-0.5 text-xs ${category === item.value ? "bg-white/15" : "bg-[#eef4fa] text-[#60708a]"}`}>{summary?.[item.count] ?? "—"}</span></button>)}
      </div>
    </div>
    <div className="app-card rounded-2xl p-3 sm:p-4"><div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_180px_180px]"><label className="relative"><span className="sr-only">Search recovery leads</span><Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#75869b]" /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search customer, phone, location or lead ID" className="focus-ring h-11 w-full rounded-xl border border-[#dce4ee] py-2 pl-9 pr-3 text-sm" /></label><select value={source} onChange={(event) => { setSource(event.target.value); setPage(1); }} className="focus-ring h-11 rounded-xl border border-[#dce4ee] bg-white px-3 text-sm"><option value="">All sources</option>{sources.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select>{role === "CEO" && <select value={assignedTo} onChange={(event) => { setAssignedTo(event.target.value); setPage(1); }} className="focus-ring h-11 rounded-xl border border-[#dce4ee] bg-white px-3 text-sm"><option value="">All owners</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.display_name || employee.username}</option>)}</select>}</div></div>
    {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}<button onClick={() => void load()} className="focus-ring rounded-lg border border-rose-200 bg-white px-3 py-1.5 font-bold">Retry</button></div>}
    <div aria-live="polite" className="flex items-center justify-between text-sm text-[#60708a]"><p>{loading ? "Loading recovery leads…" : `${count} ${active.label.toLowerCase()} lead${count === 1 ? "" : "s"}`}</p><p>Page {page}</p></div>
    {!loading && !rows.length && !error && <div className="app-card rounded-2xl p-8 text-center"><div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-[#eaf4ff] text-[#0869d8]"><Icon name="check" className="h-5 w-5" /></div><h2 className="mt-3 font-bold text-[#203756]">No {active.label.toLowerCase()} leads</h2><p className="mt-1 text-sm text-[#60708a]">New recovery leads will appear here when they are categorised.</p></div>}
    <div className="grid gap-3 lg:grid-cols-2">{rows.map((lead) => <article key={lead.id} className="app-card rounded-2xl p-4 sm:p-5"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><Link href={`/leads/${lead.id}`} className="focus-ring block truncate text-base font-bold text-[#203756] hover:text-[#0869d8]">{lead.name || "Unnamed customer"}</Link><p className="mt-1 text-sm text-[#60708a]">Lead #{lead.id} · {lead.phone || "No phone"}</p></div><LeadBadge value={lead.recovery_category || category} /></div><div className="mt-4 grid gap-2 text-sm text-[#60708a] sm:grid-cols-2"><p><span className="font-semibold text-[#405773]">Owner:</span> {lead.assigned_to_detail?.display_name || lead.assigned_to_detail?.username || "Unassigned"}</p><p><span className="font-semibold text-[#405773]">Source:</span> {label(lead.source)}</p><p><span className="font-semibold text-[#405773]">Created:</span> {new Date(lead.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</p><p><span className="font-semibold text-[#405773]">Last activity:</span> {lead.last_activity ? new Date(lead.last_activity.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" }) : "No activity"}</p></div>{lead.last_activity && <p className="mt-3 rounded-xl bg-[#f6f9fc] px-3 py-2 text-xs leading-5 text-[#60708a]">{lead.last_activity.note || `${label(lead.last_activity.activity_type)}${lead.last_activity.field_name ? ` · ${label(lead.last_activity.field_name)}` : ""}`}</p>}<div className="mt-4 grid grid-cols-2 gap-2 border-t border-[#edf1f5] pt-3 sm:flex sm:flex-wrap">{hasPhone(lead.phone) ? <a href={`tel:${contactNumber(lead.phone)}`} className="focus-ring inline-flex h-10 items-center justify-center gap-1 rounded-lg bg-[#eaf4ff] px-3 text-sm font-bold text-[#0869d8]"><Icon name="phone" className="h-4 w-4" />Call</a> : <span className="inline-flex h-10 items-center justify-center rounded-lg bg-slate-100 px-3 text-sm font-semibold text-slate-400">No phone</span>}<Link href={`/leads/${lead.id}`} className="focus-ring inline-flex h-10 items-center justify-center rounded-lg border border-[#dce4ee] px-3 text-sm font-bold text-[#405773]">Details</Link><button disabled={busy === lead.id || !lead.assigned_to} onClick={() => setFollowUpLead(lead)} className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-[#f47b20] px-3 text-sm font-bold text-white disabled:opacity-50">Follow-up</button><button disabled={busy === lead.id} onClick={() => void restore(lead)} className="focus-ring inline-flex h-10 items-center justify-center rounded-lg border border-[#b8d1ea] px-3 text-sm font-bold text-[#155ca8] disabled:opacity-50">Restore</button></div>{role === "CEO" && <div className="mt-3 grid gap-2 border-t border-[#edf1f5] pt-3 sm:grid-cols-[minmax(0,1fr)_auto]"><select defaultValue="" disabled={busy === lead.id} onChange={(event) => void reassign(lead, event.target.value)} className="focus-ring h-10 rounded-lg border border-[#dce4ee] bg-white px-3 text-sm"><option value="">Reassign to employee…</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.display_name || employee.username}</option>)}</select><button disabled={busy === lead.id} onClick={() => setDeleteLead(lead)} className="focus-ring h-10 rounded-lg border border-rose-200 px-3 text-sm font-bold text-rose-700 disabled:opacity-50">Delete</button></div>}</article>)}</div>
    {count > 12 && <div className="flex justify-center gap-3"><button disabled={page === 1 || loading} onClick={() => setPage((value) => value - 1)} className="focus-ring h-10 rounded-lg border border-[#dce4ee] px-4 text-sm font-bold disabled:opacity-40">Previous</button><button disabled={rows.length < 12 || loading} onClick={() => setPage((value) => value + 1)} className="focus-ring h-10 rounded-lg border border-[#dce4ee] px-4 text-sm font-bold disabled:opacity-40">Next</button></div>}
    {followUpLead && <Dialog title="Move to Follow-up" close={() => setFollowUpLead(null)}><form onSubmit={moveToFollowUp} className="mt-5 space-y-4"><p className="text-sm text-[#60708a]">Schedule the next action for lead #{followUpLead.id}. Existing recovery history remains intact.</p><label className="block text-sm font-semibold text-[#405773]">Next action<input name="title" required defaultValue={`Follow up with ${followUpLead.name || followUpLead.phone}`} className="focus-ring mt-1 h-11 w-full rounded-lg border border-[#dce4ee] px-3" /></label><label className="block text-sm font-semibold text-[#405773]">Scheduled date & time<input name="scheduled_at" required type="datetime-local" className="focus-ring mt-1 h-11 w-full rounded-lg border border-[#dce4ee] px-3" /></label><label className="block text-sm font-semibold text-[#405773]">Notes<textarea name="description" className="focus-ring mt-1 min-h-24 w-full rounded-lg border border-[#dce4ee] p-3" /></label><div className="flex justify-end gap-3"><button type="button" onClick={() => setFollowUpLead(null)} className="focus-ring rounded-lg px-4 py-2.5 text-sm font-bold text-[#60708a]">Cancel</button><button disabled={busy === followUpLead.id} className="focus-ring rounded-lg bg-[#f47b20] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60">{busy === followUpLead.id ? "Moving…" : "Move to Follow-up"}</button></div></form></Dialog>}
    {deleteLead && <Dialog title="Permanently delete lead" close={() => setDeleteLead(null)}><div className="mt-5 space-y-5"><p className="text-sm leading-6 text-[#60708a]">Permanent deletion cannot be undone. The server will block this action when it would remove protected history.</p><div className="flex justify-end gap-3"><button onClick={() => setDeleteLead(null)} className="focus-ring rounded-lg px-4 py-2.5 text-sm font-bold text-[#60708a]">Cancel</button><button disabled={busy === deleteLead.id} onClick={() => void remove(deleteLead)} className="focus-ring rounded-lg bg-rose-700 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60">{busy === deleteLead.id ? "Deleting…" : "Permanently delete"}</button></div></div></Dialog>}
  </section>;
}
