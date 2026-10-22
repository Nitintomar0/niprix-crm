"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { SiteVisit } from "@/lib/types";

type VisitTab = "requested" | "done";

function formatWhen(value: string | null) {
  if (!value) return "Unscheduled";
  return new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function localDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const part = (item: number) => String(item).padStart(2, "0");
  return `${date.getFullYear()}-${part(date.getMonth() + 1)}-${part(date.getDate())}T${part(date.getHours())}:${part(date.getMinutes())}`;
}

function VisitDialog({ visit, close, saved }: { visit: SiteVisit; close: () => void; saved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!visit.assigned_to) { setError("Assign this lead before scheduling its site visit."); return; }
    const data = new FormData(event.currentTarget);
    const scheduled = String(data.get("scheduled_at") || "");
    if (!scheduled) { setError("Choose a date and time for the site visit."); return; }
    setBusy(true); setError("");
    try {
      await api.createFollowUp({
        title: `Site visit · ${visit.name || visit.phone}`,
        description: String(data.get("notes") || "Site visit scheduled from the Site Visits workspace."),
        assigned_to: visit.assigned_to,
        lead: visit.id,
        follow_up_type: "SITE_VISIT",
        customer_progress: "SITE_VISIT_SCHEDULED",
        scheduled_at: new Date(scheduled).toISOString(),
        priority: "HIGH",
        status: "PENDING",
      });
      saved();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The site visit could not be scheduled."); } finally { setBusy(false); }
  }
  return <div role="dialog" aria-modal="true" aria-label="Schedule site visit" className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4"><button onClick={close} aria-label="Close schedule form" className="mobile-sheet-backdrop absolute inset-0" /><form onSubmit={submit} className="mobile-sheet relative w-full max-w-lg rounded-t-[28px] bg-white p-5 shadow-2xl sm:rounded-2xl sm:p-6"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-bold tracking-[.15em] text-[#805bab]">SITE VISIT</p><h2 className="mt-1 text-xl font-bold text-[#17233f]">Schedule {visit.name || "customer"}</h2><p className="mt-1 text-sm text-[#77829a]">{visit.assigned_to_detail?.display_name || visit.assigned_to_detail?.username || "Assigned employee"} will receive the follow-up.</p></div><button type="button" onClick={close} className="focus-ring rounded-lg p-2 text-[#77829a]" aria-label="Close">×</button></div><label className="mt-5 block text-sm font-semibold text-[#35435e]">Date and time<input required name="scheduled_at" type="datetime-local" defaultValue={localDateTime(visit.site_visit_at)} className="focus-ring mt-2 w-full rounded-xl border border-[#ded8e8] bg-[#fcfbfd] px-3 py-2.5" /></label><label className="mt-4 block text-sm font-semibold text-[#35435e]">Notes <span className="font-normal text-[#77829a]">(optional)</span><textarea name="notes" defaultValue={visit.requirement_notes} className="focus-ring mt-2 min-h-24 w-full rounded-xl border border-[#ded8e8] bg-[#fcfbfd] px-3 py-2.5" placeholder="Add access, project, or customer notes" /></label>{error && <p role="alert" className="mt-4 rounded-xl bg-[#fff4f5] p-3 text-sm text-[#a3344a]">{error}</p>}<div className="mt-5 flex justify-end gap-3"><button type="button" onClick={close} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-bold text-[#66738d]">Cancel</button><button disabled={busy || !visit.assigned_to} className="brand-button focus-ring min-h-11 rounded-xl px-4 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Scheduling…" : "Schedule visit"}</button></div>{!visit.assigned_to && <p className="mt-3 text-xs text-[#a15d2f]">This lead has no assigned employee yet. Open the lead to assign an owner first.</p>}</form></div>;
}

export function SiteVisitsDashboard() {
  const [tab, setTab] = useState<VisitTab>("requested");
  const [rows, setRows] = useState<SiteVisit[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scheduled, setScheduled] = useState<SiteVisit | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const query = new URLSearchParams({ status: tab, page: "1", page_size: "50" });
      if (search.trim()) query.set("search", search.trim());
      const response = await api.siteVisits(query.toString());
      setRows(response.results); setTotal(response.count);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Site visits could not be loaded."); } finally { setLoading(false); }
  }, [search, tab]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 220); return () => window.clearTimeout(timer); }, [load]);
  async function markDone(visit: SiteVisit) {
    if (!window.confirm(`Mark the site visit for ${visit.name || visit.phone} as done?`)) return;
    try { await api.updateLead(visit.id, { status: "SITE_VISIT_DONE" }); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "The site visit could not be updated."); }
  }
  return <section className="space-y-5 sm:space-y-6"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-bold tracking-[.15em] text-[#805bab]">LEAD WORKFLOW</p><h1 className="mt-1 text-[25px] font-bold tracking-tight text-[#17233f]">Site visits</h1><p className="mt-1 max-w-2xl text-sm leading-6 text-[#66738d]">A live view of leads in the requested and completed site-visit stages. Customer records stay in the lead pipeline—nothing is duplicated here.</p></div><Link href="/leads" className="subtle-button focus-ring inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#ddd4e8] bg-white px-4 text-sm font-bold text-[#56627b]"><Icon name="users" className="h-4 w-4" />Open leads</Link></div><div className="app-card rounded-2xl p-3 sm:p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center"><div className="flex rounded-xl bg-[#f3f0f8] p-1">{(["requested", "done"] as VisitTab[]).map((value) => <button key={value} onClick={() => setTab(value)} className={`focus-ring flex-1 rounded-lg px-3 py-2 text-sm font-bold ${tab === value ? "bg-white text-[#684496] shadow-sm" : "text-[#77829a]"}`}>{value === "requested" ? "Requested" : "Done"}</button>)}</div><label className="relative min-w-0 flex-1"><span className="sr-only">Search site visits</span><Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8490a4]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search customer, phone, city or property" className="focus-ring w-full rounded-xl border border-[#ded8e8] bg-[#fcfbfd] py-2.5 pl-9 pr-3 text-sm" /></label><span className="text-sm text-[#77829a]">{total} {tab === "requested" ? "requested" : "completed"}</span></div></div>{error && <div role="alert" className="rounded-xl border border-[#f1cbd3] bg-[#fff7f8] px-4 py-3 text-sm text-[#9e364b]">{error}</div>}<div className="grid gap-4 lg:grid-cols-2">{loading ? Array.from({ length: 4 }).map((_, index) => <div key={index} className="shimmer h-[238px] rounded-2xl" />) : rows.map((visit) => <article key={visit.id} className="card-enter app-card rounded-2xl p-5"><div className="flex items-start justify-between gap-4"><div className="min-w-0"><p className="text-[10px] font-bold tracking-[.14em] text-[#805bab]">{tab === "requested" ? "AWAITING VISIT" : "VISIT COMPLETED"}</p><h2 className="mt-1 truncate text-lg font-bold text-[#17233f]">{visit.name || "Unnamed customer"}</h2><p className="mt-1 text-sm text-[#66738d]">{visit.phone} {visit.preferred_location ? `· ${visit.preferred_location}` : ""}</p></div><span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-bold ${tab === "requested" ? "bg-[#fff0e9] text-[#a6572d]" : "bg-[#e8f7f2] text-[#15836d]"}`}>{tab === "requested" ? "Requested" : "Done"}</span></div><div className="mt-5 grid gap-3 border-y border-[#eee9f3] py-4 text-sm sm:grid-cols-2"><div><p className="text-[10px] font-bold tracking-[.12em] text-[#8992a4]">PROPERTY</p><p className="mt-1 font-semibold text-[#35435e]">{visit.property_type || "Not specified"}</p></div><div><p className="text-[10px] font-bold tracking-[.12em] text-[#8992a4]">ASSIGNED TO</p><p className="mt-1 font-semibold text-[#35435e]">{visit.assigned_to_detail?.display_name || visit.assigned_to_detail?.username || "Unassigned"}</p></div><div className="sm:col-span-2"><p className="text-[10px] font-bold tracking-[.12em] text-[#8992a4]">SCHEDULE</p><p className={`mt-1 font-semibold ${visit.site_visit_at ? "text-[#35435e]" : "text-[#a6572d]"}`}>{formatWhen(visit.site_visit_at)}</p></div></div>{visit.requirement_notes && <p className="mt-4 line-clamp-2 text-sm leading-6 text-[#66738d]">{visit.requirement_notes}</p>}<div className="mt-5 flex flex-wrap items-center gap-3"><Link href={`/leads/${visit.id}`} className="focus-ring text-sm font-bold text-[#684496]">Open lead timeline</Link>{tab === "requested" && <><button onClick={() => setScheduled(visit)} className="focus-ring text-sm font-bold text-[#56627b]">{visit.site_visit_at ? "Reschedule" : "Schedule"}</button><button onClick={() => void markDone(visit)} className="focus-ring ml-auto rounded-lg bg-[#e8f7f2] px-3 py-2 text-xs font-bold text-[#15836d]">Mark done</button></>}</div></article>)}{!loading && !rows.length && <div className="app-card col-span-full rounded-2xl py-14 text-center"><span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#f0e9f8] text-[#805bab]"><Icon name="calendar" className="h-5 w-5" /></span><h2 className="mt-4 font-bold text-[#35435e]">No {tab === "requested" ? "requested" : "completed"} site visits</h2><p className="mt-1 text-sm text-[#77829a]">Leads will appear here as soon as their site-visit status is updated.</p></div>}</div>{scheduled && <VisitDialog visit={scheduled} close={() => setScheduled(null)} saved={() => { setScheduled(null); void load(); }} />}</section>;
}
