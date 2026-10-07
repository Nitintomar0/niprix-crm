"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "@/components/icons";
import type {
  EmployeeOption,
  Lead,
  LeadActivity,
  LeadAssignment,
  LeadSource,
  LeadSummary,
  Role,
  Task,
  FollowUp,
} from "@/lib/types";

const statuses = [
  "NEW",
  "CONTACTED",
  "SITE_VISIT_REQUESTED",
  "SITE_VISIT_DONE",
  "FOLLOW_UP_NEEDED",
  "FOLLOW_UP_DONE",
  "POSTPONED",
  "DIFFERENT_REQUIREMENT",
  "NOT_INTERESTED",
  "CLOSED",
  "INVALID_PHONE",
  "NOT_LOOKING_PROPERTY",
  "USER_IS_AGENT",
];
const sources = [
  "MANUAL",
  "WHATSAPP",
  "FACEBOOK",
  "INSTAGRAM",
  "META_LEAD_AD",
  "WEBSITE",
  "REFERRAL",
  "OTHER",
];
const temperatures = ["HOT", "WARM", "COLD"];
const empty = (value?: string | number | null) =>
  value === null || value === undefined || value === ""
    ? "Not provided"
    : String(value);
const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
const money = (value?: string | null) =>
  value
    ? new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(Number(value))
    : "Not provided";
const resultRows = <T,>(value: { results: T[] } | T[]) =>
  Array.isArray(value) ? value : value.results;
const dateValue = (date: Date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
};
const contactNumber = (phone: string) => phone.replace(/\D/g, "").replace(/^00/, "");
const hasUsablePhone = (phone?: string | null) => /^\d{7,15}$/.test(contactNumber(phone || ""));
const whatsappUrl = (phone: string, employeeName?: string) => {
  const message = `Hello Sir, this is ${employeeName || "our team"} from Paramshiv Real Estate. You had shown interest in property. Please share your property requirement, preferred location, budget and other details so we can assist you with suitable options.`;
  return `https://wa.me/${contactNumber(phone)}?text=${encodeURIComponent(message)}`;
};

function tone(value: string) {
  if (value === "HOT" || value === "CLOSED")
    return "bg-[#fff0f1] text-[#b12938]";
  if (value === "WARM" || value.includes("FOLLOW") || value.includes("SITE"))
    return "bg-[#fff4e5] text-[#a96908]";
  return "bg-[#eaf4ff] text-[#0869d8]";
}
function Badge({ value }: { value: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone(value)}`}
    >
      {label(value)}
    </span>
  );
}
function Card({ title, value }: { title: string; value: number }) {
  return (
    <div className="app-card rounded-2xl p-4">
      <p className="text-xs font-semibold tracking-[.08em] text-[#75869b]">
        {title.toUpperCase()}
      </p>
      <p className="mt-2 text-2xl font-semibold text-[#203756]">{value}</p>
    </div>
  );
}
function Dialog({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4"
    >
      <button
        aria-label="Close"
        onClick={close}
        className="mobile-sheet-backdrop absolute inset-0"
      />
      <div className="mobile-sheet relative max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-t-[24px] bg-white p-5 shadow-2xl sm:rounded-2xl sm:p-6">
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[#d8e1ec] sm:hidden" />
        <div className="flex justify-between gap-3">
          <h2 className="text-xl font-semibold text-[#203756]">{title}</h2>
          <button
            aria-label="Close"
            onClick={close}
            className="focus-ring text-xl text-[#60708a]"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
function Input({
  name,
  label: title,
  defaultValue,
  required = false,
  type = "text",
  readOnly = false,
}: {
  name: string;
  label: string;
  defaultValue?: string | number | null;
  required?: boolean;
  type?: string;
  readOnly?: boolean;
}) {
  return (
    <label className="block text-sm font-medium text-[#405773]">
      {title}
      <input
        name={name}
        type={type}
        required={required}
        readOnly={readOnly}
        defaultValue={defaultValue ?? ""}
        className={`focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm ${readOnly ? "bg-[#f5f8fc] text-[#60708a]" : ""}`}
      />
    </label>
  );
}

export function LeadsDashboard({
  role,
  leadId,
}: {
  role: Role;
  leadId?: number;
}) {
  const [summary, setSummary] = useState<LeadSummary | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [temperature, setTemperature] = useState("");
  const [source, setSource] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [location, setLocation] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [specificDate, setSpecificDate] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const latestLoad = useRef(0);
  const load = useCallback(async () => {
    if (leadId) return;
    const requestId = ++latestLoad.current;
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({
        page: String(page),
        page_size: "25",
      });
      if (search) query.set("search", search);
      if (status) query.set("status", status);
      if (temperature) query.set("temperature", temperature);
      if (source) query.set("source", source);
      if (assignedTo) query.set("assigned_to", assignedTo);
      if (location) query.set("location", location);
      if (dateFilter) {
        const today = new Date(); const start = new Date(today); start.setHours(0, 0, 0, 0); const end = new Date(start);
        if (dateFilter === "today") { query.set("date_from", dateValue(start)); query.set("date_to", dateValue(start)); }
        if (dateFilter === "yesterday") { start.setDate(start.getDate() - 1); query.set("date_from", dateValue(start)); query.set("date_to", dateValue(start)); }
        if (dateFilter === "week") { start.setDate(start.getDate() - ((start.getDay() + 6) % 7)); query.set("date_from", dateValue(start)); query.set("date_to", dateValue(end)); }
        if (dateFilter === "month") { start.setDate(1); query.set("date_from", dateValue(start)); query.set("date_to", dateValue(end)); }
      }
      if (specificDate) { query.set("date_from", specificDate); query.set("date_to", specificDate); }
      if (dateFrom) query.set("date_from", dateFrom);
      if (dateTo) query.set("date_to", dateTo);
      const [records, metrics, people] = await Promise.all([
        api.leads(query.toString()),
        api.leadSummary(),
        api.employees(),
      ]);
      if (requestId !== latestLoad.current) return;
      setLeads(records.results);
      setTotal(records.count);
      setSummary(metrics);
      setEmployees(resultRows(people));
    } catch (caught) {
      if (requestId !== latestLoad.current) return;
      setError(
        caught instanceof Error ? caught.message : "Could not load leads.",
      );
    } finally {
      if (requestId === latestLoad.current) setLoading(false);
    }
  }, [assignedTo, dateFilter, dateFrom, dateTo, leadId, location, page, search, source, specificDate, status, temperature]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    // Avoid a full list/summary request for every keystroke while keeping
    // filter changes responsive.
    }, 250);
    return () => window.clearTimeout(timer);
  }, [load]);
  if (leadId) return <LeadDetail id={leadId} role={role} />;
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {};
    for (const [key, value] of data.entries())
      if (String(value).trim()) body[key] = String(value).trim();
    if (body.budget_minimum) body.budget_minimum = Number(body.budget_minimum);
    if (body.budget_maximum) body.budget_maximum = Number(body.budget_maximum);
    try {
      await api.createLead(body);
      setCreating(false);
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not create lead.",
      );
    }
  }
  const resetFilters = () => {
    setPage(1); setStatus(""); setTemperature(""); setSource(""); setAssignedTo(""); setLocation(""); setDateFilter(""); setSpecificDate(""); setDateFrom(""); setDateTo("");
  };
  const activeFilterCount = [status, temperature, source, assignedTo, location, dateFilter, specificDate, dateFrom, dateTo].filter(Boolean).length;
  const filterControls = (className: string) => (
    <div className={className}>
      <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }} className="focus-ring rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"><option value="">All statuses</option>{statuses.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select>
      <select value={temperature} onChange={(event) => { setPage(1); setTemperature(event.target.value); }} className="focus-ring rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"><option value="">All temperatures</option>{temperatures.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select>
      <select value={source} onChange={(event) => { setPage(1); setSource(event.target.value); }} className="focus-ring rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"><option value="">All sources</option>{sources.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select>
      <select value={assignedTo} onChange={(event) => { setPage(1); setAssignedTo(event.target.value); }} className="focus-ring rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"><option value="">All permitted owners</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.display_name || employee.username}</option>)}</select>
      <input value={location} onChange={(event) => { setPage(1); setLocation(event.target.value); }} placeholder="Filter location" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" />
      <select value={dateFilter} onChange={(event) => { setPage(1); setDateFilter(event.target.value); setSpecificDate(""); setDateFrom(""); setDateTo(""); }} className="focus-ring rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"><option value="">All received dates</option><option value="today">Today</option><option value="yesterday">Yesterday</option><option value="week">This week</option><option value="month">This month</option></select>
      <input value={specificDate} onChange={(event) => { setPage(1); setSpecificDate(event.target.value); setDateFilter(""); setDateFrom(""); setDateTo(""); }} type="date" aria-label="Specific lead received date" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" />
      <input value={dateFrom} max={dateTo || undefined} onChange={(event) => { setPage(1); setDateFrom(event.target.value); setDateFilter(""); setSpecificDate(""); }} type="date" aria-label="Lead received from date" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" />
      <input value={dateTo} min={dateFrom || undefined} onChange={(event) => { setPage(1); setDateTo(event.target.value); setDateFilter(""); setSpecificDate(""); }} type="date" aria-label="Lead received to date" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" />
    </div>
  );
  return (
    <section className="space-y-5 sm:space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[#60708a]">
            Scoped to your{" "}
            {role === "CEO"
              ? "company"
              : role === "MANAGER"
                ? "team"
                : "assigned work"}
          </p>
          <h1 className="mt-1 text-[24px] font-semibold tracking-tight text-[#203756]">Leads</h1>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_16px_rgba(8,105,216,.18)]"
        >
          <Icon name="plus" className="h-4 w-4" /> Create lead
        </button>
      </div>
      {summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
          <Card title="Total" value={summary.total} />
          <Card title="New" value={summary.new} />
          <Card title="Contacted" value={summary.contacted} />
          <Card title="Hot" value={summary.hot} />
          <Card title="Follow-up" value={summary.follow_up_needed} />
          <Card title="Site visits" value={summary.site_visits} />
          <Card title="Closed" value={summary.closed} />
        </div>
      )}
      <div className="app-card rounded-2xl p-3 sm:p-5">
        <div className="flex gap-2 md:hidden">
          <label className="relative min-w-0 flex-1"><span className="sr-only">Search leads</span><Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#75869b]" /><input value={search} onChange={(event) => { setPage(1); setSearch(event.target.value); }} placeholder="Search leads" className="focus-ring w-full rounded-xl border border-[#dce4ee] py-2.5 pl-9 pr-3 text-sm" /></label>
          <button onClick={() => setFiltersOpen(true)} className="focus-ring relative inline-flex min-h-11 items-center gap-1 rounded-xl border border-[#dce4ee] px-3 text-sm font-semibold text-[#405773]"><Icon name="filter" className="h-4 w-4" />Filter{activeFilterCount > 0 && <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#ff7a00] px-1 text-[10px] text-white">{activeFilterCount}</span>}</button>
        </div>
        <div className="hidden grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <input
            value={search}
            onChange={(event) => {
              setPage(1);
              setSearch(event.target.value);
            }}
            placeholder="Search name, phone, email, ID"
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm xl:col-span-2"
          />
          <select
            value={status}
            onChange={(event) => {
              setPage(1);
              setStatus(event.target.value);
            }}
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
          >
            <option value="">All statuses</option>
            {statuses.map((item) => (
              <option key={item} value={item}>{label(item)}</option>
            ))}
          </select>
          <select
            value={temperature}
            onChange={(event) => {
              setPage(1);
              setTemperature(event.target.value);
            }}
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
          >
            <option value="">All temperatures</option>
            {temperatures.map((item) => (
              <option key={item} value={item}>{label(item)}</option>
            ))}
          </select>
          <select
            value={source}
            onChange={(event) => {
              setPage(1);
              setSource(event.target.value);
            }}
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
          >
            <option value="">All sources</option>
            {sources.map((item) => (
              <option key={item} value={item}>{label(item)}</option>
            ))}
          </select>
          <select
            value={assignedTo}
            onChange={(event) => {
              setPage(1);
              setAssignedTo(event.target.value);
            }}
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
          >
            <option value="">All permitted owners</option>
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.display_name || employee.username}
              </option>
            ))}
          </select>
          <input
            value={location}
            onChange={(event) => {
              setPage(1);
              setLocation(event.target.value);
            }}
            placeholder="Filter location"
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
          />
          <select value={dateFilter} onChange={(event) => { setPage(1); setDateFilter(event.target.value); setSpecificDate(""); setDateFrom(""); setDateTo(""); }} className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"><option value="">All received dates</option><option value="today">Today</option><option value="yesterday">Yesterday</option><option value="week">This week</option><option value="month">This month</option></select>
          <input value={specificDate} onChange={(event) => { setPage(1); setSpecificDate(event.target.value); setDateFilter(""); setDateFrom(""); setDateTo(""); }} type="date" aria-label="Specific lead received date" className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm" />
          <input value={dateFrom} max={dateTo || undefined} onChange={(event) => { setPage(1); setDateFrom(event.target.value); setDateFilter(""); setSpecificDate(""); }} type="date" aria-label="Lead received from date" className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm" />
          <input value={dateTo} min={dateFrom || undefined} onChange={(event) => { setPage(1); setDateTo(event.target.value); setDateFilter(""); setSpecificDate(""); }} type="date" aria-label="Lead received to date" className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm" />
        </div>
        {error && (
          <p
            role="alert"
            className="mt-4 rounded-lg bg-[#fff0f1] px-3 py-2 text-sm text-[#b12938]"
          >
            {error}
          </p>
        )}
        {loading && <div className="mt-5 grid gap-3 md:hidden">{[0, 1, 2].map((item) => <div key={item} className="shimmer h-36 rounded-2xl" />)}</div>}
        <div className="mt-5 grid gap-3 md:hidden">
          {!loading && leads.map((lead, index) => <article key={lead.id} className="mobile-card-enter rounded-2xl border border-[#e2eaf3] bg-white p-4" style={{ animationDelay: `${index * 25}ms` }}>
            <Link href={`/leads/${lead.id}`} className="block focus-ring rounded-lg"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 className="truncate text-[16px] font-bold text-[#203756]">{empty(lead.name)}</h2><p className="mt-1 truncate text-[13px] text-[#60708a]">{lead.phone || "No phone available"}</p></div><Badge value={lead.temperature} /></div><p className="mt-3 truncate text-sm font-medium text-[#405773]">{empty(lead.property_type)} <span className="text-[#9aa7b8]">·</span> {empty(lead.preferred_location)}</p><div className="mt-3 flex flex-wrap gap-1.5"><Badge value={lead.status} /><Badge value={lead.source} /></div>{role !== "EMPLOYEE" && <p className="mt-3 truncate text-xs text-[#75869b]">Owner: {lead.assigned_to_detail?.display_name || lead.assigned_to_detail?.username || "Unassigned"}</p>}</Link>
            <div className="mt-4 grid grid-cols-3 gap-2 border-t border-[#edf1f5] pt-3">{hasUsablePhone(lead.phone) ? <a href={`tel:${contactNumber(lead.phone)}`} className="focus-ring inline-flex min-h-10 items-center justify-center gap-1 rounded-xl bg-[#edf8f4] text-xs font-bold text-[#168460]"><Icon name="phone" className="h-3.5 w-3.5" />Call</a> : <span className="inline-flex min-h-10 items-center justify-center rounded-xl bg-[#f4f6f8] text-xs font-medium text-[#91a0b1]">No number</span>}{hasUsablePhone(lead.phone) ? <a target="_blank" rel="noreferrer" href={whatsappUrl(lead.phone, lead.assigned_to_detail?.display_name || lead.assigned_to_detail?.username)} className="focus-ring inline-flex min-h-10 items-center justify-center gap-1 rounded-xl bg-[#e9f8ef] text-xs font-bold text-[#168460]"><Icon name="message" className="h-3.5 w-3.5" />WhatsApp</a> : <span className="inline-flex min-h-10 items-center justify-center rounded-xl bg-[#f4f6f8] text-xs font-medium text-[#91a0b1]">WhatsApp</span>}<Link href={`/leads/${lead.id}`} className="focus-ring inline-flex min-h-10 items-center justify-center rounded-xl bg-[#eaf4ff] text-xs font-bold text-[#0869d8]">Open</Link></div>
          </article>)}
        </div>
        <div className="mt-5 hidden overflow-x-auto md:block">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b text-xs uppercase tracking-[.08em] text-[#8291a4]">
              <tr>
                <th className="pb-3">Lead</th>
                <th className="pb-3">Requirement</th>
                <th className="pb-3">Owner</th>
                <th className="pb-3">Source</th>
                <th className="pb-3">Status</th>
                <th className="pb-3" />
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id} className="border-b border-[#edf1f5]">
                  <td className="py-4">
                    <p className="font-semibold text-[#2a405f]">
                      {empty(lead.name)}
                    </p>
                    <p className="mt-1 text-xs text-[#7b8ba1]">
                      #{lead.id} · {lead.phone}
                    </p>
                    <p className="mt-1 text-xs text-[#7b8ba1]">Lead received: {new Date(lead.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</p>
                  </td>
                  <td className="py-4 text-[#526984]">
                    <p>{empty(lead.property_type)}</p>
                    <p className="mt-1 text-xs text-[#7b8ba1]">
                      {empty(lead.preferred_location)}
                    </p>
                  </td>
                  <td className="py-4 text-[#526984]">
                    {lead.assigned_to_detail?.display_name ||
                      lead.assigned_to_detail?.username ||
                      "Unassigned"}
                  </td>
                  <td className="py-4">
                    <Badge value={lead.source} />
                  </td>
                  <td className="py-4">
                    <div className="flex flex-wrap gap-1">
                      <Badge value={lead.status} />
                      <Badge value={lead.temperature} />
                    </div>
                  </td>
                  <td className="py-4 text-right">
                    {hasUsablePhone(lead.phone) && <a href={`tel:${contactNumber(lead.phone)}`} className="focus-ring rounded-lg px-2 py-1 text-xs font-semibold text-[#168460]">Call</a>}
                    {hasUsablePhone(lead.phone) && <a target="_blank" rel="noreferrer" href={whatsappUrl(lead.phone, lead.assigned_to_detail?.display_name || lead.assigned_to_detail?.username)} className="focus-ring rounded-lg px-2 py-1 text-xs font-semibold text-[#168460]">WhatsApp</a>}
                    <Link
                      href={`/leads/${lead.id}`}
                      className="focus-ring rounded-lg px-2 py-1 text-xs font-semibold text-[#0869d8]"
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !leads.length && (
          <div className="py-12 text-center"><span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eaf4ff] text-[#0869d8]"><Icon name="users" className="h-5 w-5" /></span><p className="mt-3 text-sm font-semibold text-[#405773]">No leads found</p><p className="mt-1 text-sm text-[#75869b]">Try changing your search or filters.</p>{activeFilterCount > 0 && <button onClick={resetFilters} className="mt-3 text-sm font-bold text-[#0869d8]">Clear filters</button>}</div>
        )}
        <div className="mt-4 flex items-center justify-between text-sm text-[#60708a]">
          <span>
            {loading ? "Loading…" : `${total} lead${total === 1 ? "" : "s"}`}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 1 || loading}
              onClick={() => setPage(page - 1)}
              className="focus-ring rounded-lg border px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={leads.length < 25 || loading}
              onClick={() => setPage(page + 1)}
              className="focus-ring rounded-lg border px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>
      {creating && (
        <Dialog title="Create manual lead" close={() => setCreating(false)}>
          <form onSubmit={create} className="mt-5 grid gap-4 sm:grid-cols-2">
            <Input name="phone" label="Phone" required />
            <Input name="name" label="Name" />
            <Input name="email" label="Email" type="email" />
            <Input name="alternate_phone" label="Alternate phone" />
            <Input name="property_type" label="Property type" />
            <Input name="preferred_location" label="Preferred location" />
            <Input name="budget_minimum" label="Budget minimum" type="number" />
            <Input name="budget_maximum" label="Budget maximum" type="number" />
            <Input name="bhk" label="BHK" />
            <Input name="purpose" label="Purpose" />
            <label className="sm:col-span-2 block text-sm font-medium text-[#405773]">
              Requirement notes
              <textarea
                name="requirement_notes"
                className="focus-ring mt-1 min-h-24 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
              />
            </label>
            <div className="sm:col-span-2 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="focus-ring rounded-lg px-4 py-2.5 text-sm font-semibold text-[#60708a]"
              >
                Cancel
              </button>
              <button className="focus-ring rounded-lg bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white">
                Save lead
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {filtersOpen && <Dialog title="Filter leads" close={() => setFiltersOpen(false)}><div className="mt-4 space-y-3">{filterControls("grid gap-3")}</div><div className="mt-5 grid grid-cols-2 gap-3"><button onClick={resetFilters} className="focus-ring rounded-xl border border-[#dce4ee] px-4 py-2.5 text-sm font-bold text-[#405773]">Reset</button><button onClick={() => setFiltersOpen(false)} className="focus-ring rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-bold text-white">Apply filters</button></div></Dialog>}
    </section>
  );
}

function LeadDetail({ id, role }: { id: number; role: Role }) {
  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [sources, setSources] = useState<LeadSource[]>([]);
  const [assignments, setAssignments] = useState<LeadAssignment[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [callLog, setCallLog] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setError("");
    try {
      const [
        record,
        activityData,
        sourceData,
        assignmentData,
        followData,
        taskData,
        people,
      ] = await Promise.all([
        api.lead(id),
        api.leadActivities(id),
        api.leadSources(id),
        api.leadAssignments(id),
        api.followUps(`lead=${id}&page=1&page_size=100`),
        api.tasks(`lead=${id}&page=1&page_size=100`),
        api.employees(),
      ]);
      setLead(record);
      setActivities(activityData.results);
      setSources(sourceData.results);
      setAssignments(assignmentData.results);
      setFollowUps(followData.results);
      setTasks(taskData.results);
      setEmployees(resultRows(people));
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not load this lead.",
      );
    }
  }, [id]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  if (!lead)
    return (
      <section>
        <Link href="/leads" className="text-sm font-semibold text-[#0869d8]">
          ← Back to leads
        </Link>
        <p className="mt-6 text-sm text-[#60708a]">
          {error || "Loading lead…"}
        </p>
      </section>
    );
  const currentLead = lead;
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {};
    for (const [key, value] of data.entries()) body[key] = String(value);
    for (const field of ["budget_minimum", "budget_maximum"])
      if (!body[field]) body[field] = null;
      else body[field] = Number(body[field]);
    setBusy(true);
    try {
      await api.updateLead(id, body);
      setEditing(false);
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not update lead.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function addNote(event: FormEvent) {
    event.preventDefault();
    if (!note.trim()) return;
    try {
      await api.addLeadNote(id, note);
      setNote("");
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not add note.",
      );
    }
  }
  async function reassign(value: string) {
    if (!value) return;
    try {
      await api.assignLead(id, Number(value));
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not reassign lead.",
      );
    }
  }
  async function remove() {
    setBusy(true);
    try {
      await api.deleteLead(id);
      setDeleted(true);
      setConfirmDelete(false);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not delete lead.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function logCall(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const nextStatus = String(data.get("status") || "CONTACTED");
    const callNote = String(data.get("note") || "").trim();
    const followUpAt = String(data.get("follow_up_at") || "");
    const shouldCreateFollowUp = data.get("create_follow_up") === "on";
    if (shouldCreateFollowUp && !followUpAt) {
      setError("Choose a follow-up date and time before saving.");
      return;
    }
    if (shouldCreateFollowUp && !currentLead.assigned_to) {
      setError("Assign this lead before creating a follow-up.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.updateLead(id, { status: nextStatus });
      if (callNote) await api.addLeadNote(id, `Call result: ${callNote}`);
      if (shouldCreateFollowUp && currentLead.assigned_to && followUpAt) {
        await api.createFollowUp({
          title: `Follow up with ${empty(currentLead.name)}`,
          description: callNote,
          assigned_to: currentLead.assigned_to,
          lead: id,
          scheduled_at: new Date(followUpAt).toISOString(),
          follow_up_type: "CALL",
          priority: "MEDIUM",
          status: "PENDING",
        });
      }
      setCallLog(false);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save this call result.");
    } finally {
      setBusy(false);
    }
  }
  if (deleted)
    return (
      <section className="app-card rounded-2xl p-8">
        <h1 className="text-xl font-semibold text-[#203756]">Lead deleted</h1>
        <p className="mt-2 text-sm text-[#60708a]">
          The lead was permanently deleted.
        </p>
        <Link
          href="/leads"
          className="mt-5 inline-block text-sm font-semibold text-[#0869d8]"
        >
          Return to leads
        </Link>
      </section>
    );
  return (
    <section className="space-y-5 sm:space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/leads" className="text-sm font-semibold text-[#0869d8]">
            ← Back to leads
          </Link>
          <h1 className="mt-2 text-[24px] font-semibold tracking-tight text-[#203756]">
            {empty(lead.name)}{" "}
            <span className="text-base font-medium text-[#7b8ba1]">
              #{lead.id}
            </span>
          </h1>
          <p className="mt-1 text-sm text-[#60708a]">Lead received: {new Date(lead.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</p>
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <Badge value={lead.status} />
          <Badge value={lead.temperature} />
          {hasUsablePhone(lead.phone) && <a href={`tel:${contactNumber(lead.phone)}`} onClick={() => setCallLog(true)} className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-bold text-white"><Icon name="phone" className="h-4 w-4" />Call</a>}
          {hasUsablePhone(lead.phone) && <a target="_blank" rel="noreferrer" href={whatsappUrl(lead.phone, lead.assigned_to_detail?.display_name || lead.assigned_to_detail?.username)} className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#e9f8ef] px-4 py-2.5 text-sm font-bold text-[#168460]"><Icon name="message" className="h-4 w-4" />WhatsApp</a>}
          {!hasUsablePhone(lead.phone) && <span className="inline-flex min-h-11 items-center rounded-xl bg-[#f1f4f7] px-4 text-sm font-semibold text-[#718198]">No usable phone number</span>}
          <button
            onClick={() => setEditing(true)}
            className="focus-ring min-h-11 rounded-xl border border-[#0869d8] px-4 py-2 text-sm font-semibold text-[#0869d8]"
          >
            Edit lead
          </button>
          {role !== "EMPLOYEE" && (
            <button
              onClick={() => setConfirmDelete(true)}
              className="focus-ring min-h-11 rounded-xl border border-[#c43d4b] px-4 py-2 text-sm font-semibold text-[#c43d4b]"
            >
              Delete lead
            </button>
          )}
        </div>
      </div>
      {error && (
        <p
          role="alert"
          className="rounded-lg bg-[#fff0f1] px-3 py-2 text-sm text-[#b12938]"
        >
          {error}
        </p>
      )}
      <div className="grid gap-5 xl:grid-cols-[1.25fr_.75fr]">
        <div className="space-y-5">
          <section className="app-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-[#203756]">Overview</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Property label="Status">
                <Badge value={lead.status} />
              </Property>
              <Property label="Temperature">
                <Badge value={lead.temperature} />
              </Property>
              <Property label="Owner">
                {lead.assigned_to_detail?.display_name ||
                  lead.assigned_to_detail?.username ||
                  "Unassigned"}
              </Property>
              <Property label="Primary source">
                <Badge value={lead.source} />
              </Property>
            </div>
          </section>
          <section className="app-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-[#203756]">
              Contact / identity
            </h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Property label="Name">{empty(lead.name)}</Property>
              <Property label="Phone">
                <span>{lead.phone}</span>
                <span className="ml-2 text-xs text-[#7b8ba1]">
                  Locked after creation
                </span>
              </Property>
              <Property label="Email">{empty(lead.email)}</Property>
              <Property label="Alternate phone">
                {empty(lead.alternate_phone)}
              </Property>
            </div>
          </section>
          <section className="app-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-[#203756]">
              Requirement
            </h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Property label="Property type">
                {empty(lead.property_type)}
              </Property>
              <Property label="Location">
                {empty(lead.preferred_location)}
              </Property>
              <Property label="Budget">
                {lead.budget_minimum || lead.budget_maximum
                  ? `${money(lead.budget_minimum)} – ${money(lead.budget_maximum)}`
                  : "Not provided"}
              </Property>
              <Property label="BHK / purpose">
                {[lead.bhk, lead.purpose].filter(Boolean).join(" · ") ||
                  "Not provided"}
              </Property>
              <Property label="Notes">
                <span className="whitespace-pre-wrap">
                  {empty(lead.requirement_notes)}
                </span>
              </Property>
            </div>
          </section>
          <section className="app-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-[#203756]">
              Activity timeline
            </h2>
            <form onSubmit={addNote} className="mt-4 flex gap-2">
              <input
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Add a note"
                className="focus-ring min-w-0 flex-1 rounded-lg border border-[#dce4ee] px-3 py-2 text-sm"
              />
              <button className="focus-ring rounded-lg bg-[#0869d8] px-3 py-2 text-sm font-semibold text-white">
                Add
              </button>
            </form>
            <div className="mt-5 space-y-3">
              {activities.map((activity) => (
                <article
                  key={activity.id}
                  className="border-l-2 border-[#dce4ee] pl-4"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <p className="font-semibold text-sm text-[#405773]">
                      {label(activity.activity_type)}
                    </p>
                    <time className="text-xs text-[#7b8ba1]">
                      {new Date(activity.created_at).toLocaleString()}
                    </time>
                  </div>
                  <p className="mt-1 text-sm text-[#60708a]">
                    {activity.note ||
                      (activity.field_name
                        ? `${label(activity.field_name)}: ${activity.old_value} → ${activity.new_value}`
                        : "")}
                  </p>
                  <p className="mt-1 text-xs text-[#8291a4]">
                    {activity.performed_by_name || "System"}
                  </p>
                </article>
              ))}
              {!activities.length && (
                <p className="text-sm text-[#60708a]">No activity yet.</p>
              )}
            </div>
          </section>
        </div>
        <aside className="space-y-5">
          <section className="app-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-[#203756]">Assignment</h2>
            <p className="mt-2 text-sm text-[#60708a]">
              {lead.assigned_to_detail?.display_name ||
                lead.assigned_to_detail?.username ||
                "Unassigned"}
            </p>
            {role !== "EMPLOYEE" && (
              <select
                value={lead.assigned_to ?? ""}
                onChange={(event) => void reassign(event.target.value)}
                className="focus-ring mt-3 w-full rounded-lg border border-[#dce4ee] px-3 py-2 text-sm"
              >
                <option value="">Choose owner</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.display_name || employee.username}
                  </option>
                ))}
              </select>
            )}
            <div className="mt-4 space-y-2">
              {assignments.map((item) => (
                <p key={item.id} className="text-xs text-[#60708a]">
                  {label(item.assignment_type)} →{" "}
                  {item.assigned_to_detail.display_name ||
                    item.assigned_to_detail.username}{" "}
                  · {new Date(item.created_at).toLocaleString()}
                </p>
              ))}
            </div>
          </section>
          <section className="app-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-[#203756]">Sources</h2>
            <div className="mt-4 space-y-3">
              {sources.map((item) => (
                <div key={item.id} className="rounded-lg bg-[#f5f8fc] p-3">
                  <Badge value={item.source} />
                  <p className="mt-2 text-xs text-[#60708a]">
                    {item.source_details || "No source details"}
                  </p>
                  <p className="mt-1 text-xs text-[#8291a4]">
                    {new Date(item.received_at).toLocaleString()}
                  </p>
                </div>
              ))}
              {!sources.length && (
                <p className="text-sm text-[#60708a]">No source events.</p>
              )}
            </div>
          </section>
          <section className="app-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-[#203756]">
              Tasks & follow-ups
            </h2>
            <p className="mt-3 text-sm text-[#60708a]">
              {followUps.length} follow-up{followUps.length === 1 ? "" : "s"} ·{" "}
              {tasks.length} task{tasks.length === 1 ? "" : "s"}
            </p>
            <div className="mt-3 space-y-2">
              {followUps.slice(0, 4).map((item) => (
                <p key={item.id} className="text-xs text-[#60708a]">
                  Follow-up: {item.title}
                </p>
              ))}
              {tasks.slice(0, 4).map((item) => (
                <p key={item.id} className="text-xs text-[#60708a]">
                  Task: {item.title}
                </p>
              ))}
            </div>
            <p className="mt-4 text-xs text-[#8291a4]">
              Create linked work from the Tasks or Follow-ups workspace using
              this lead ID.
            </p>
          </section>
        </aside>
      </div>
      {editing && (
        <Dialog title="Edit lead" close={() => setEditing(false)}>
          <form onSubmit={save} className="mt-5 grid gap-4 sm:grid-cols-2">
            <Input name="name" label="Name" defaultValue={lead.name} />
            <Input
              name="email"
              label="Email"
              defaultValue={lead.email}
              type="email"
            />
            <Input
              name="phone"
              label="Phone"
              defaultValue={lead.phone}
              readOnly
            />
            <Input
              name="alternate_phone"
              label="Alternate phone"
              defaultValue={lead.alternate_phone}
            />
            <Input
              name="property_type"
              label="Property type"
              defaultValue={lead.property_type}
            />
            <Input
              name="preferred_location"
              label="Preferred location"
              defaultValue={lead.preferred_location}
            />
            <Input
              name="budget_minimum"
              label="Budget minimum"
              type="number"
              defaultValue={lead.budget_minimum}
            />
            <Input
              name="budget_maximum"
              label="Budget maximum"
              type="number"
              defaultValue={lead.budget_maximum}
            />
            <Input name="bhk" label="BHK" defaultValue={lead.bhk} />
            <Input name="purpose" label="Purpose" defaultValue={lead.purpose} />
            <label className="block text-sm font-medium text-[#405773]">
              Status
              <select
                name="status"
                defaultValue={lead.status}
                className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
              >
                {statuses.map((item) => (
                  <option key={item} value={item}>
                    {label(item)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-[#405773]">
              Temperature
              <select
                name="temperature"
                defaultValue={lead.temperature}
                className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
              >
                {temperatures.map((item) => (
                  <option key={item} value={item}>
                    {label(item)}
                  </option>
                ))}
              </select>
            </label>
            <label className="sm:col-span-2 block text-sm font-medium text-[#405773]">
              Requirement notes
              <textarea
                name="requirement_notes"
                defaultValue={lead.requirement_notes}
                className="focus-ring mt-1 min-h-24 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
              />
            </label>
            <div className="sm:col-span-2 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="focus-ring rounded-lg px-4 py-2.5 text-sm font-semibold text-[#60708a]"
              >
                Cancel
              </button>
              <button
                disabled={busy}
                className="focus-ring rounded-lg bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white"
              >
                {busy ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {callLog && <Dialog title="Log call result" close={() => setCallLog(false)}><form onSubmit={logCall} className="mt-4 space-y-4"><p className="text-sm text-[#60708a]">Save the outcome while the conversation is fresh.</p><label className="block text-sm font-medium text-[#405773]">Call outcome<select name="status" defaultValue="CONTACTED" className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm">{statuses.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label><label className="block text-sm font-medium text-[#405773]">Notes<textarea name="note" placeholder="What did the lead say?" className="focus-ring mt-1 min-h-24 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /></label><label className="flex min-h-11 items-center gap-3 rounded-xl bg-[#f5f8fc] px-3 text-sm font-semibold text-[#405773]"><input name="create_follow_up" type="checkbox" className="h-4 min-h-0 w-4" />Create a follow-up</label><label className="block text-sm font-medium text-[#405773]">Follow-up date & time<input name="follow_up_at" type="datetime-local" className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /></label><button disabled={busy} className="focus-ring flex w-full items-center justify-center rounded-xl bg-[#0869d8] px-4 py-3 text-sm font-bold text-white disabled:opacity-60">{busy ? "Saving…" : "Save call result"}</button></form></Dialog>}
      {confirmDelete && (
        <Dialog title="Permanently delete lead" close={() => setConfirmDelete(false)}>
          <div className="mt-5 space-y-5">
            <p className="text-sm text-[#405773]">
              This permanently deletes this lead and cannot be undone. Its lead
              timeline, source attribution, and assignment history will be removed.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmDelete(false)} className="focus-ring rounded-lg px-4 py-2.5 text-sm font-semibold text-[#60708a]">Cancel</button>
              <button disabled={busy} onClick={() => void remove()} className="focus-ring rounded-lg bg-[#c43d4b] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{busy ? "Deleting…" : "Permanently delete"}</button>
            </div>
          </div>
        </Dialog>
      )}
    </section>
  );
}
function Property({
  label: title,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[.08em] text-[#8291a4]">
        {title}
      </p>
      <div className="mt-1 text-sm text-[#405773]">{children}</div>
    </div>
  );
}
