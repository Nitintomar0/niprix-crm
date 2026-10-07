"use client";

import { FormEvent, useCallback, useEffect, useState, type ReactNode } from "react";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { RawDistributionPreview, RawEligibleEmployee, RawLead, RawPreview, RawPreviewRow, Role } from "@/lib/types";

const editableFields: Array<{ key: keyof RawPreviewRow; label: string; type?: string }> = [
  { key: "name", label: "Name" }, { key: "phone", label: "Phone" }, { key: "email", label: "Email", type: "email" },
  { key: "preferred_location", label: "City" }, { key: "property_type", label: "Property type" }, { key: "requirement_notes", label: "Requirement" },
  { key: "budget_maximum", label: "Budget", type: "number" }, { key: "source", label: "Source" },
];
const manualFields = editableFields.filter((field) => !["requirement_notes", "budget_maximum", "source"].includes(String(field.key)));
const sources = ["MANUAL", "WHATSAPP", "FACEBOOK", "INSTAGRAM", "META_LEAD_AD", "WEBSITE", "REFERRAL", "OTHER"];
const label = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (item) => item.toUpperCase());

function Dialog({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  return <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
    <button aria-label="Close" onClick={close} className="mobile-sheet-backdrop absolute inset-0" />
    <div className="mobile-sheet relative max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-t-[24px] bg-white p-5 shadow-2xl sm:rounded-2xl sm:p-6">
      <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[#d8e1ec] sm:hidden" />
      <div className="flex items-center justify-between gap-4"><h2 className="text-xl font-semibold text-[#203756]">{title}</h2><button className="focus-ring flex h-10 w-10 items-center justify-center rounded-xl text-xl text-[#60708a]" onClick={close} aria-label="Close">×</button></div>
      {children}
    </div>
  </div>;
}

function Card({ label: title, value }: { label: string; value: number }) {
  return <div className="app-card rounded-2xl p-4"><p className="text-xs font-semibold tracking-[.08em] text-[#75869b]">{title.toUpperCase()}</p><p className="mt-2 text-2xl font-semibold text-[#203756]">{value}</p></div>;
}

function RawLeadFields({ lead }: { lead?: RawLead }) {
  return <>{manualFields.map((field) => <label key={String(field.key)} className="text-sm font-medium text-[#405773]">{field.label}<input name={String(field.key)} type={field.type || "text"} required={field.key === "phone"} defaultValue={lead ? String(lead[field.key as keyof RawLead] ?? "") : ""} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5" /></label>)}<label className="text-sm font-medium text-[#405773]">Source<select name="source" defaultValue={lead?.source || "MANUAL"} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5">{sources.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label><label className="text-sm font-medium text-[#405773] sm:col-span-2">Requirement<textarea name="requirement_notes" defaultValue={lead?.requirement_notes || ""} className="focus-ring mt-1 min-h-24 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5" /></label></>;
}

export function RawDataDashboard({ role }: { role: Role }) {
  const [rows, setRows] = useState<RawLead[]>([]);
  const [total, setTotal] = useState(0);
  const [available, setAvailable] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [people, setPeople] = useState<RawEligibleEmployee[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [source, setSource] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<RawLead | null>(null);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<RawPreview | null>(null);
  const [distributing, setDistributing] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [mode, setMode] = useState<"EQUAL" | "SPECIFIC" | "CUSTOM">("EQUAL");
  const [employeeIds, setEmployeeIds] = useState<number[]>([]);
  const [quantity, setQuantity] = useState("");
  const [allocations, setAllocations] = useState<Record<string, number>>({});
  const [distributionPreview, setDistributionPreview] = useState<RawDistributionPreview | null>(null);

  const load = useCallback(async (pageToLoad = 1, append = false) => {
    if (role !== "CEO") return;
    if (append) setLoadingMore(true);
    else { setLoading(true); setError(""); }
    try {
      const query = new URLSearchParams({ page: String(pageToLoad), page_size: "25" });
      if (search) query.set("search", search);
      if (location) query.set("location", location);
      if (propertyType) query.set("property_type", propertyType);
      if (source) query.set("source", source);
      if (dateFilter) { query.set("date_from", dateFilter); query.set("date_to", dateFilter); }
      const [listing, summary, employees] = await Promise.all([api.rawLeads(query.toString()), api.rawDataSummary(), api.rawEligibleEmployees()]);
      setRows((current) => append ? [...current, ...listing.results] : listing.results);
      setTotal(summary.total);
      setAvailable(summary.available);
      setPeople(employees);
      setPage(pageToLoad);
      if (!append) setSelected([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load Raw Data.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [dateFilter, location, propertyType, role, search, source]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (role !== "CEO") return <div className="app-card rounded-2xl p-8"><h1 className="text-xl font-semibold text-[#203756]">Raw Data is restricted</h1><p className="mt-2 text-sm text-[#60708a]">Only the CEO can access this workspace.</p></div>;

  const toggle = (id: number) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  const allVisible = rows.length > 0 && rows.every((row) => selected.includes(row.id));
  const toggleVisible = () => setSelected((current) => allVisible ? current.filter((id) => !rows.some((row) => row.id === id)) : Array.from(new Set([...current, ...rows.map((row) => row.id)])));
  const clearFilters = () => { setSearch(""); setLocation(""); setPropertyType(""); setSource(""); setDateFilter(""); };
  const activeFilters = [location, propertyType, source, dateFilter].filter(Boolean).length;

  async function loadMore() {
    if (loadingMore || rows.length >= total) return;
    await load(page + 1, true);
  }
  async function removeRawLead(id: number) {
    try {
      await api.deleteRawLead(id);
      setRows((current) => current.filter((row) => row.id !== id));
      setSelected((current) => current.filter((currentId) => currentId !== id));
      setTotal((current) => Math.max(0, current - 1));
      setAvailable((current) => Math.max(0, current - 1));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete raw lead.");
    }
  }
  async function submitManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body: Record<string, unknown> = {};
    new FormData(event.currentTarget).forEach((value, key) => { const text = String(value).trim(); if (text) body[key] = text; });
    try {
      const created = await api.createRawLead(body);
      setRows((current) => [created, ...current]);
      setTotal((current) => current + 1);
      setAvailable((current) => current + 1);
      setAdding(false);
      setMessage("Raw lead added to the pool.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add raw lead.");
    }
  }
  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const body: Record<string, unknown> = {};
    new FormData(event.currentTarget).forEach((value, key) => { body[key] = String(value).trim(); });
    try {
      await api.updateRawLead(editing.id, body);
      setEditing(null);
      setMessage("Raw lead updated.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update raw lead.");
    }
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = new FormData(event.currentTarget).get("file");
    if (!(file instanceof File) || !file.size) { setError("Choose a CSV or XLSX file first."); return; }
    try {
      const body = new FormData();
      body.set("file", file);
      setPreview(await api.previewRawData(body));
      setUploading(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not preview this file.");
    }
  }
  function changePreview(index: number, key: keyof RawPreviewRow, value: string) {
    if (!preview) return;
    setPreview({ ...preview, rows: preview.rows.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row) });
  }
  async function savePreview() {
    if (!preview) return;
    try {
      const fresh = await api.previewRawData({ rows: preview.rows });
      setPreview(fresh);
      if (fresh.summary.valid === 0) { setError("Correct or remove rows before saving. No valid unique rows remain."); return; }
      const saved = await api.saveRawPreview(fresh.rows);
      setPreview(null);
      setMessage(`${saved.created} valid raw lead${saved.created === 1 ? "" : "s"} saved. Rows needing attention were not saved.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save preview rows.");
    }
  }
  function payloadForDistribution() {
    const body: Record<string, unknown> = { employee_ids: employeeIds, mode };
    if (selected.length) body.raw_lead_ids = selected;
    else body.quantity = Number(quantity);
    if (mode === "CUSTOM") body.allocations = allocations;
    return body;
  }
  async function previewDistribution() {
    setError("");
    try {
      setDistributionPreview(await api.previewRawDistribution(payloadForDistribution()));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not prepare distribution.");
    }
  }
  async function confirmDistribution() {
    if (!distributionPreview) return;
    try {
      const body: Record<string, unknown> = { raw_lead_ids: distributionPreview.raw_lead_ids, employee_ids: employeeIds, mode };
      if (mode === "CUSTOM") body.allocations = allocations;
      const result = await api.distributeRawData(body);
      setDistributionPreview(null);
      setDistributing(false);
      setSelected([]);
      setMessage(`${result.distributed} raw lead${result.distributed === 1 ? "" : "s"} distributed into CRM Leads.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Distribution could not be completed.");
    }
  }

  const filters = <div className="grid gap-3"><input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Filter city" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /><input value={propertyType} onChange={(event) => setPropertyType(event.target.value)} placeholder="Property type" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /><select value={source} onChange={(event) => setSource(event.target.value)} className="focus-ring rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"><option value="">All sources</option>{sources.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select><input type="date" value={dateFilter} onChange={(event) => setDateFilter(event.target.value)} aria-label="Filter by created date" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /></div>;

  return <section className="space-y-5 sm:space-y-6">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-semibold tracking-[.12em] text-[#0869d8]">CEO INTAKE POOL</p><h1 className="mt-1 text-[24px] font-semibold tracking-tight text-[#203756]">Raw Data</h1><p className="mt-1 text-sm text-[#60708a]">Review incoming leads before securely distributing them to your sales team.</p></div><div className="flex flex-wrap gap-2"><button onClick={() => setUploading(true)} className="focus-ring min-h-11 rounded-xl border border-[#c9d8ea] bg-white px-3 py-2.5 text-sm font-bold text-[#36526f] sm:px-4">Upload CSV / XLSX</button><button onClick={() => setAdding(true)} className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#0869d8] px-3 py-2.5 text-sm font-bold text-white sm:px-4"><Icon name="plus" className="h-4 w-4" />Add raw lead</button></div></div>
    {error && <div role="alert" className="rounded-xl border border-[#f1c2c7] bg-[#fff4f5] px-4 py-3 text-sm text-[#a62d3d]">{error}</div>}
    {message && <div className="rounded-xl border border-[#bee7d8] bg-[#effbf6] px-4 py-3 text-sm text-[#167257]">{message}</div>}
    <div className="grid grid-cols-3 gap-3"><Card label="Total" value={total} /><Card label="Available" value={available} /><Card label="Selected" value={selected.length} /></div>
    <div className="app-card rounded-2xl p-3 sm:p-4"><div className="flex gap-2 md:hidden"><label className="relative min-w-0 flex-1"><span className="sr-only">Search raw leads</span><Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#75869b]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, phone, email" className="focus-ring w-full rounded-xl border border-[#dce4ee] py-2.5 pl-9 pr-3 text-sm" /></label><button onClick={() => setFiltersOpen(true)} className="focus-ring relative inline-flex min-h-11 items-center gap-1 rounded-xl border border-[#dce4ee] px-3 text-sm font-bold text-[#405773]"><Icon name="filter" className="h-4 w-4" />Filter{activeFilters > 0 && <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#ff7a00] px-1 text-[10px] text-white">{activeFilters}</span>}</button></div><div className="hidden grid gap-3 md:grid-cols-5"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, phone, email" className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm" />{filters.props.children}</div></div>
    <section className="app-card overflow-hidden rounded-2xl"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#e4eaf2] px-4 py-4 sm:px-5"><div><h2 className="font-semibold text-[#203756]">Leads waiting for distribution</h2><p className="mt-0.5 text-xs text-[#75869b]">{selected.length ? `${selected.length} selected` : "Select leads or distribute a specific quantity"}</p></div><div className="flex gap-2"><button onClick={() => setSelected([])} disabled={!selected.length} className="focus-ring min-h-10 rounded-xl px-3 text-xs font-bold text-[#60708a] disabled:opacity-40">Clear</button><button onClick={() => setDistributing(true)} disabled={!available} className="focus-ring min-h-10 rounded-xl bg-[#102e51] px-3 text-xs font-bold text-white disabled:opacity-40">Distribute</button></div></div>
      <div className="grid gap-3 p-3 md:hidden">{loading ? [0, 1, 2].map((value) => <div key={value} className="shimmer h-40 rounded-2xl" />) : rows.map((row) => <article key={row.id} className={`rounded-2xl border p-4 ${selected.includes(row.id) ? "border-[#91c7ff] bg-[#f5faff]" : "border-[#e2eaf3] bg-white"}`}><div className="flex items-start gap-3"><input aria-label={`Select ${row.name || "raw lead"}`} type="checkbox" checked={selected.includes(row.id)} onChange={() => toggle(row.id)} className="mt-1 h-4 min-h-0 w-4 shrink-0" /><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="truncate text-[16px] font-bold text-[#203756]">{row.name || "Unnamed lead"}</h3><p className="mt-1 text-sm text-[#60708a]">{row.phone || "No phone"}{row.preferred_location ? ` · ${row.preferred_location}` : ""}</p></div><span className="rounded-full bg-[#eaf4ff] px-2 py-1 text-[11px] font-bold text-[#0869d8]">{label(row.source)}</span></div><p className="mt-3 text-sm font-medium text-[#405773]">{row.property_type || "Property type not provided"}</p>{row.requirement_notes && <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#75869b]">{row.requirement_notes}</p>}<div className="mt-3 flex justify-end gap-3 border-t border-[#edf1f5] pt-3"><button onClick={() => setEditing(row)} className="focus-ring min-h-10 text-xs font-bold text-[#0869d8]">Edit</button><button onClick={() => void removeRawLead(row.id)} className="focus-ring min-h-10 text-xs font-bold text-[#b12938]">Delete</button></div></div></div></article>)}</div>
      <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-[#f8fbff] text-xs font-semibold tracking-wide text-[#75869b]"><tr><th className="px-5 py-3"><input aria-label="Select all visible leads" type="checkbox" checked={allVisible} onChange={toggleVisible} /></th><th>Name</th><th>Phone</th><th>City</th><th>Property type</th><th>Requirement</th><th>Source</th><th className="px-5">Actions</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t border-[#edf1f6] text-[#405773]"><td className="px-5 py-3"><input aria-label={`Select ${row.name || "raw lead"}`} type="checkbox" checked={selected.includes(row.id)} onChange={() => toggle(row.id)} /></td><td className="py-3 font-medium text-[#203756]">{row.name || "—"}<div className="text-xs font-normal text-[#75869b]">{row.email || ""}</div></td><td>{row.phone}</td><td>{row.preferred_location || "—"}</td><td>{row.property_type || "—"}</td><td className="max-w-[180px] truncate">{row.requirement_notes || "—"}</td><td>{label(row.source)}</td><td className="px-5"><button onClick={() => setEditing(row)} className="mr-3 text-xs font-semibold text-[#0869d8]">Edit</button><button onClick={() => void removeRawLead(row.id)} className="text-xs font-semibold text-[#b12938]">Delete</button></td></tr>)}</tbody></table></div>
      {!loading && !rows.length && <div className="py-12 text-center"><span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eaf4ff] text-[#0869d8]"><Icon name="users" className="h-5 w-5" /></span><p className="mt-3 font-semibold text-[#405773]">No raw leads found</p><p className="mt-1 text-sm text-[#75869b]">Try changing the filters or add a new lead.</p></div>}
      {rows.length < total && <div className="flex justify-center border-t border-[#e4eaf2] px-5 py-4"><button type="button" onClick={() => void loadMore()} disabled={loadingMore} className="focus-ring min-h-11 rounded-xl border border-[#c9d8ea] bg-white px-5 text-sm font-bold text-[#36526f] disabled:opacity-50">{loadingMore ? "Loading…" : `Load more (${rows.length} of ${total})`}</button></div>}
    </section>
    {filtersOpen && <Dialog title="Filter raw leads" close={() => setFiltersOpen(false)}><div className="mt-4">{filters}</div><div className="mt-5 grid grid-cols-2 gap-3"><button onClick={clearFilters} className="focus-ring rounded-xl border border-[#dce4ee] px-4 py-2.5 text-sm font-bold text-[#405773]">Reset</button><button onClick={() => setFiltersOpen(false)} className="focus-ring rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-bold text-white">Apply filters</button></div></Dialog>}
    {adding && <Dialog title="Add Raw Lead" close={() => setAdding(false)}><form onSubmit={submitManual} className="mt-5 grid gap-4 sm:grid-cols-2"><RawLeadFields /><FormActions close={() => setAdding(false)} saveLabel="Save Raw Lead" /></form></Dialog>}
    {editing && <Dialog title="Edit Raw Lead" close={() => setEditing(null)}><form onSubmit={submitEdit} className="mt-5 grid gap-4 sm:grid-cols-2"><RawLeadFields lead={editing} /><FormActions close={() => setEditing(null)} saveLabel="Save changes" /></form></Dialog>}
    {uploading && <Dialog title="Upload Raw Data" close={() => setUploading(false)}><form onSubmit={upload} className="mt-5 space-y-5"><p className="text-sm text-[#60708a]">Choose a CSV or XLSX file. Nothing is saved until you review and approve the preview.</p><input name="file" type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="focus-ring block w-full rounded-xl border border-[#dce4ee] p-2 text-sm" /><div className="flex justify-end gap-3"><button type="button" onClick={() => setUploading(false)} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button className="focus-ring min-h-11 rounded-xl bg-[#0869d8] px-4 text-sm font-semibold text-white">Preview file</button></div></form></Dialog>}
    {preview && <Dialog title="Preview Raw Data" close={() => setPreview(null)}><div className="mt-4 flex flex-wrap gap-3 text-sm"><span>Total: <b>{preview.summary.total}</b></span><span className="text-[#167257]">Valid: <b>{preview.summary.valid}</b></span><span className="text-[#b12938]">Needs attention: <b>{preview.summary.invalid}</b></span><span>Duplicates: <b>{preview.summary.duplicates}</b></span></div><p className="mt-3 text-xs text-[#75869b]">Edit rows to correct them, or remove rows you do not want to save. Validation is checked again before saving.</p><div className="mt-4 space-y-3 md:hidden">{preview.rows.map((row, index) => <fieldset key={`${row.row_number}-${index}`} className={`rounded-2xl border p-4 ${row.valid ? "border-[#e2eaf3]" : "border-[#f1c5cb] bg-[#fff8f8]"}`}><legend className="px-1 text-sm font-bold text-[#405773]">Row {row.row_number}</legend><div className="mt-2 grid gap-3">{editableFields.map((field) => <label key={String(field.key)} className="text-xs font-semibold text-[#60708a]">{field.label}<input value={String(row[field.key] ?? "")} onChange={(event) => changePreview(index, field.key, event.target.value)} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /></label>)}</div>{row.errors.length > 0 && <p className="mt-3 text-xs text-[#b12938]">{row.errors.join(" ")}</p>}<button type="button" onClick={() => setPreview({ ...preview, rows: preview.rows.filter((_, rowIndex) => rowIndex !== index) })} className="focus-ring mt-3 min-h-10 text-sm font-bold text-[#b12938]">Remove row</button></fieldset>)}</div><div className="mt-4 hidden max-h-[48vh] overflow-auto border border-[#e4eaf2] md:block"><table className="w-full min-w-[1100px] text-left text-xs"><thead className="sticky top-0 bg-[#f8fbff] text-[#75869b]"><tr>{editableFields.map((field) => <th key={String(field.key)} className="px-2 py-2">{field.label}</th>)}<th>Issues</th><th /></tr></thead><tbody>{preview.rows.map((row, index) => <tr key={`${row.row_number}-${index}`} className={`border-t ${row.valid ? "" : "bg-[#fff7f7]"}`}>{editableFields.map((field) => <td key={String(field.key)} className="p-1"><input value={String(row[field.key] ?? "")} onChange={(event) => changePreview(index, field.key, event.target.value)} className="w-full min-w-24 rounded border border-[#dce4ee] px-2 py-1.5" /></td>)}<td className="max-w-48 p-2 text-[#b12938]">{row.errors.join(" ")}</td><td className="p-2"><button type="button" onClick={() => setPreview({ ...preview, rows: preview.rows.filter((_, rowIndex) => rowIndex !== index) })} className="font-semibold text-[#b12938]">Remove</button></td></tr>)}</tbody></table></div><div className="mt-5 flex justify-end gap-3"><button type="button" onClick={() => setPreview(null)} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button type="button" onClick={() => void savePreview()} className="focus-ring min-h-11 rounded-xl bg-[#0869d8] px-4 text-sm font-semibold text-white">Save to Raw Data</button></div></Dialog>}
    {distributing && <DistributionSheet selected={selected} available={available} people={people} mode={mode} setMode={setMode} employeeIds={employeeIds} setEmployeeIds={setEmployeeIds} quantity={quantity} setQuantity={setQuantity} allocations={allocations} setAllocations={setAllocations} preview={distributionPreview} onClose={() => { setDistributing(false); setDistributionPreview(null); }} onPreview={() => void previewDistribution()} onConfirm={() => void confirmDistribution()} />}
  </section>;
}

function FormActions({ close, saveLabel }: { close: () => void; saveLabel: string }) {
  return <div className="sm:col-span-2 flex justify-end gap-3"><button type="button" onClick={close} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button className="focus-ring min-h-11 rounded-xl bg-[#0869d8] px-4 text-sm font-semibold text-white">{saveLabel}</button></div>;
}

function DistributionSheet({ selected, available, people, mode, setMode, employeeIds, setEmployeeIds, quantity, setQuantity, allocations, setAllocations, preview, onClose, onPreview, onConfirm }: { selected: number[]; available: number; people: RawEligibleEmployee[]; mode: "EQUAL" | "SPECIFIC" | "CUSTOM"; setMode: (value: "EQUAL" | "SPECIFIC" | "CUSTOM") => void; employeeIds: number[]; setEmployeeIds: (value: number[]) => void; quantity: string; setQuantity: (value: string) => void; allocations: Record<string, number>; setAllocations: (value: Record<string, number>) => void; preview: RawDistributionPreview | null; onClose: () => void; onPreview: () => void; onConfirm: () => void }) {
  const valid = employeeIds.length > 0 && (selected.length > 0 || (Boolean(quantity) && Number(quantity) <= available));
  return <Dialog title="Distribute Raw Leads" close={onClose}><div className="mt-4 space-y-4"><p className="text-sm text-[#60708a]">{selected.length ? `${selected.length} selected raw lead${selected.length === 1 ? "" : "s"} will be distributed.` : "Enter how many of the oldest available raw leads to distribute."}</p>{!selected.length && <label className="block text-sm font-medium text-[#405773]">Number of leads<input type="number" min="1" max={available} value={quantity} onChange={(event) => setQuantity(event.target.value)} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5" /></label>}<div><p className="text-sm font-medium text-[#405773]">Distribution mode</p><div className="mt-2 flex flex-wrap gap-2">{(["EQUAL", "SPECIFIC", "CUSTOM"] as const).map((item) => <button type="button" key={item} onClick={() => setMode(item)} className={`focus-ring min-h-10 rounded-xl px-3 text-sm font-bold ${mode === item ? "bg-[#eaf4ff] text-[#0869d8]" : "border border-[#dce4ee] text-[#60708a]"}`}>{label(item)}</button>)}</div></div><div><p className="text-sm font-medium text-[#405773]">Eligible employees</p>{people.length ? <div className="mt-2 grid gap-2 sm:grid-cols-2">{people.map((person) => <label key={person.id} className="flex min-h-12 items-center gap-2 rounded-xl border border-[#e4eaf2] p-3 text-sm"><input type={mode === "SPECIFIC" ? "radio" : "checkbox"} name="employee" checked={employeeIds.includes(person.id)} onChange={() => setEmployeeIds(mode === "SPECIFIC" ? [person.id] : employeeIds.includes(person.id) ? employeeIds.filter((id) => id !== person.id) : [...employeeIds, person.id])} />{person.username} <span className="text-xs text-[#75869b]">{person.employee_code}</span></label>)}</div> : <p className="mt-2 text-sm text-[#b12938]">No eligible employees can receive leads.</p>}</div>{mode === "CUSTOM" && employeeIds.map((id) => { const person = people.find((item) => item.id === id); return <label key={id} className="block text-sm font-medium text-[#405773]">{person?.username}<input type="number" min="0" value={allocations[String(id)] ?? 0} onChange={(event) => setAllocations({ ...allocations, [String(id)]: Number(event.target.value) })} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5" /></label>; })}<div className="flex justify-end gap-3"><button type="button" onClick={onClose} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button type="button" disabled={!valid} onClick={onPreview} className="focus-ring min-h-11 rounded-xl bg-[#0869d8] px-4 text-sm font-semibold text-white disabled:opacity-40">Preview distribution</button></div></div>{preview && <div className="mt-5 rounded-xl border border-[#b9d8fb] bg-[#f5faff] p-4"><h3 className="font-semibold text-[#203756]">Distribution Preview</h3><p className="mt-1 text-sm text-[#60708a]">Total leads: {preview.total}</p><div className="mt-3 space-y-1 text-sm">{preview.allocations.map((item) => <div key={item.employee_id} className="flex justify-between"><span>{item.employee_name}</span><b>{item.count}</b></div>)}</div><div className="mt-4 flex justify-end gap-3"><button type="button" onClick={onClose} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button type="button" onClick={onConfirm} className="focus-ring min-h-11 rounded-xl bg-[#102e51] px-4 text-sm font-semibold text-white">Confirm Distribution</button></div></div>}</Dialog>;
}
