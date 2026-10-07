"use client";

import { FormEvent, useCallback, useEffect, useState, type ChangeEvent, type ReactNode } from "react";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { InventoryItem, InventoryStatus, InventorySummary, Role } from "@/lib/types";

const statuses: InventoryStatus[] = ["AVAILABLE", "HOLD", "BOOKED", "SOLD", "BLOCKED", "RESERVED"];
const label = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
const money = (value: string) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value));
const blankRow = () => ({ project: "", unit_number: "", property_type: "", size_sqft: "", floor: "", basic_price: "", status: "AVAILABLE" as InventoryStatus, booking_date: "", landing: "" });
type InventoryRow = ReturnType<typeof blankRow>;

function Dialog({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  return <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
    <button aria-label="Close" onClick={close} className="mobile-sheet-backdrop absolute inset-0" />
    <div className="mobile-sheet relative max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-t-[24px] bg-white p-5 shadow-2xl sm:rounded-2xl sm:p-6">
      <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[#d8e1ec] sm:hidden" />
      <div className="flex items-center justify-between gap-4"><h2 className="text-xl font-semibold text-[#203756]">{title}</h2><button onClick={close} aria-label="Close" className="focus-ring flex h-10 w-10 items-center justify-center rounded-xl text-xl text-[#60708a]">×</button></div>
      {children}
    </div>
  </div>;
}

function InventoryBadge({ value }: { value: InventoryStatus }) {
  const tone = value === "AVAILABLE" ? "bg-[#e9f6f1] text-[#168460]" : value === "SOLD" || value === "BOOKED" ? "bg-[#eaf4ff] text-[#0869d8]" : value === "HOLD" || value === "RESERVED" ? "bg-[#fff4e5] text-[#a96908]" : "bg-[#fff0f1] text-[#b12938]";
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${tone}`}>{label(value)}</span>;
}

export function InventoryDashboard({ role }: { role: Role }) {
  const ceo = role === "CEO";
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [project, setProject] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [floor, setFloor] = useState("");
  const [bookingDate, setBookingDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState<InventoryItem | null>(null);
  const [bulk, setBulk] = useState(false);
  const [rows, setRows] = useState<InventoryRow[]>([blankRow()]);
  const [deleting, setDeleting] = useState<InventoryItem | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "25" });
      if (search) query.set("search", search);
      if (status) query.set("status", status);
      if (project) query.set("project", project);
      if (propertyType) query.set("property_type", propertyType);
      if (floor) query.set("floor", floor);
      if (bookingDate) query.set("booking_date", bookingDate);
      const [list, metrics] = await Promise.all([api.inventory(query.toString()), api.inventorySummary()]);
      setItems(list.results);
      setTotal(list.count);
      setSummary(metrics);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load inventory.");
    } finally {
      setLoading(false);
    }
  }, [bookingDate, floor, page, project, propertyType, search, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  const filtersChanged = (set: (value: string) => void) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setPage(1); set(event.target.value); };
  const clear = () => { setPage(1); setSearch(""); setStatus(""); setProject(""); setPropertyType(""); setFloor(""); setBookingDate(""); };
  const activeFilters = [status, project, propertyType, floor, bookingDate].filter(Boolean).length;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries()) as Record<string, string>;
    if (!data.booking_date) delete data.booking_date;
    if (!ceo) delete data.landing;
    try {
      if (form?.id) await api.updateInventory(form.id, data);
      else await api.createInventory(data);
      setForm(null);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save inventory.");
    }
  }

  async function submitBulk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const clean = rows.map(({ landing, booking_date, ...row }) => ({ ...row, ...(booking_date ? { booking_date } : {}), ...(ceo && landing ? { landing } : {}) }));
      await api.bulkCreateInventory(clean);
      setBulk(false);
      setRows([blankRow()]);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add inventory rows.");
    }
  }

  async function remove() {
    if (!deleting) return;
    try {
      await api.deleteInventory(deleting.id);
      setDeleting(null);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not archive inventory.");
    }
  }

  const cards = [["Total inventory", summary?.total], ["Available", summary?.available], ["Hold", summary?.hold], ["Booked", summary?.booked], ["Sold", summary?.sold]];
  const filterControls = <div className="grid gap-3"><input value={project} onChange={filtersChanged(setProject)} placeholder="Project" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /><input value={propertyType} onChange={filtersChanged(setPropertyType)} placeholder="Property type" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /><input value={floor} onChange={filtersChanged(setFloor)} placeholder="Floor" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /><select value={status} onChange={filtersChanged(setStatus)} className="focus-ring rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"><option value="">All statuses</option>{statuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select><input value={bookingDate} onChange={filtersChanged(setBookingDate)} type="date" aria-label="Booking date" className="focus-ring rounded-xl border border-[#dce4ee] px-3 py-2.5 text-sm" /></div>;

  return <section className="space-y-5 sm:space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm text-[#60708a]">Company inventory</p><h1 className="mt-1 text-[24px] font-semibold tracking-tight text-[#203756]">Inventory</h1></div>{role !== "EMPLOYEE" && <div className="flex gap-2"><button onClick={() => setBulk(true)} className="focus-ring min-h-11 rounded-xl border border-[#0869d8] px-3 py-2.5 text-sm font-bold text-[#0869d8] sm:px-4">Bulk add</button><button onClick={() => setForm({} as InventoryItem)} className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#0869d8] px-3 py-2.5 text-sm font-bold text-white shadow-[0_8px_16px_rgba(8,105,216,.18)] sm:px-4"><Icon name="plus" className="h-4 w-4" />Add</button></div>}</div>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">{cards.map(([name, value]) => <div key={String(name)} className="app-card rounded-2xl p-4"><p className="text-xs font-semibold uppercase tracking-[.07em] text-[#75869b]">{name}</p><p className="mt-2 text-2xl font-semibold text-[#203756]">{value ?? "—"}</p></div>)}</div>
    {ceo && summary?.landing_total !== undefined && <p className="text-sm text-[#60708a]">Total landing: <strong className="text-[#203756]">{money(summary.landing_total)}</strong></p>}
    <div className="app-card rounded-2xl p-3 sm:p-5">
      <div className="flex gap-2 md:hidden"><label className="relative min-w-0 flex-1"><span className="sr-only">Search inventory</span><Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#75869b]" /><input value={search} onChange={filtersChanged(setSearch)} placeholder="Search inventory" className="focus-ring w-full rounded-xl border border-[#dce4ee] py-2.5 pl-9 pr-3 text-sm" /></label><button onClick={() => setFiltersOpen(true)} className="focus-ring relative inline-flex min-h-11 items-center gap-1 rounded-xl border border-[#dce4ee] px-3 text-sm font-bold text-[#405773]"><Icon name="filter" className="h-4 w-4" />Filter{activeFilters > 0 && <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#ff7a00] px-1 text-[10px] text-white">{activeFilters}</span>}</button></div>
      <div className="hidden grid gap-3 md:grid-cols-3 xl:grid-cols-7"><input value={search} onChange={filtersChanged(setSearch)} placeholder="Search project, unit, type, floor" className="focus-ring rounded-lg border px-3 py-2.5 text-sm xl:col-span-2" /><input value={project} onChange={filtersChanged(setProject)} placeholder="Project" className="focus-ring rounded-lg border px-3 py-2.5 text-sm" /><input value={propertyType} onChange={filtersChanged(setPropertyType)} placeholder="Property type" className="focus-ring rounded-lg border px-3 py-2.5 text-sm" /><input value={floor} onChange={filtersChanged(setFloor)} placeholder="Floor" className="focus-ring rounded-lg border px-3 py-2.5 text-sm" /><select value={status} onChange={filtersChanged(setStatus)} className="focus-ring rounded-lg border px-3 py-2.5 text-sm"><option value="">All statuses</option>{statuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select><input value={bookingDate} onChange={filtersChanged(setBookingDate)} type="date" aria-label="Booking date" className="focus-ring rounded-lg border px-3 py-2.5 text-sm" /></div>
      <button onClick={clear} className="mt-3 text-sm font-bold text-[#0869d8]">Clear filters</button>
      {error && <p role="alert" className="mt-3 rounded-xl bg-[#fff0f1] p-3 text-sm text-[#b12938]">{error}</p>}
      <div className="mt-5 grid gap-3 md:hidden">{loading ? [0, 1, 2].map((value) => <div key={value} className="shimmer h-40 rounded-2xl" />) : items.map((item) => <article key={item.id} className="rounded-2xl border border-[#e2eaf3] bg-white p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 className="truncate text-[16px] font-bold text-[#203756]">{item.project}</h2><p className="mt-1 text-sm text-[#60708a]">Unit {item.unit_number} · {item.property_type}</p></div><InventoryBadge value={item.status} /></div><div className="mt-4 grid grid-cols-2 gap-3 border-y border-[#edf1f5] py-3 text-sm"><p className="text-[#75869b]">Size<span className="mt-1 block font-semibold text-[#405773]">{item.size_sqft} sq.ft</span></p><p className="text-[#75869b]">Floor<span className="mt-1 block font-semibold text-[#405773]">{item.floor}</span></p><p className="text-[#75869b]">Basic price<span className="mt-1 block font-semibold text-[#405773]">{money(item.basic_price)}</span></p><p className="text-[#75869b]">Booked<span className="mt-1 block font-semibold text-[#405773]">{item.booking_date || "—"}</span></p>{ceo && <p className="col-span-2 text-[#75869b]">Landing<span className="mt-1 block font-semibold text-[#405773]">{item.landing == null ? "—" : money(item.landing)}</span></p>}</div><div className="mt-3 flex justify-end gap-2"><button onClick={() => setForm(item)} className="focus-ring min-h-10 rounded-xl bg-[#eaf4ff] px-3 text-xs font-bold text-[#0869d8]">View / edit</button>{role !== "EMPLOYEE" && <button onClick={() => setDeleting(item)} className="focus-ring min-h-10 rounded-xl px-3 text-xs font-bold text-[#b12938]">Archive</button>}</div></article>)}</div>
      <div className="mt-5 hidden overflow-x-auto md:block"><table className="w-full min-w-[900px] text-left text-sm"><thead className="border-b text-xs uppercase text-[#8291a4]"><tr>{["Project", "Unit / flat no.", "Property type", "Size", "Floor", "Basic price", "Status", ...(ceo ? ["Landing"] : []), "Booking date", ""].map((title) => <th key={title} className="pb-3">{title}</th>)}</tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-b border-[#edf1f5]"><td className="py-4 font-semibold text-[#2a405f]">{item.project}</td><td>{item.unit_number}</td><td>{item.property_type}</td><td>{item.size_sqft} sq.ft</td><td>{item.floor}</td><td>{money(item.basic_price)}</td><td><InventoryBadge value={item.status} /></td>{ceo && <td>{item.landing == null ? "—" : money(item.landing)}</td>}<td>{item.booking_date || "—"}</td><td><button onClick={() => setForm(item)} className="mr-2 text-xs font-semibold text-[#0869d8]">View / edit</button>{role !== "EMPLOYEE" && <button onClick={() => setDeleting(item)} className="text-xs font-semibold text-[#c43d4b]">Archive</button>}</td></tr>)}</tbody></table></div>
      {!loading && !items.length && <div className="py-10 text-center"><span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eaf4ff] text-[#0869d8]"><Icon name="building" className="h-5 w-5" /></span><p className="mt-3 font-semibold text-[#405773]">No inventory found</p><p className="mt-1 text-sm text-[#75869b]">Try changing your filters.</p></div>}
      <div className="mt-4 flex items-center justify-between text-sm text-[#60708a]"><span>{loading ? "Loading…" : `${total} item${total === 1 ? "" : "s"}`}</span><div className="flex gap-2"><button disabled={page === 1 || loading} onClick={() => setPage(page - 1)} className="focus-ring min-h-10 rounded-xl border px-3 py-1.5 disabled:opacity-40">Previous</button><button disabled={items.length < 25 || loading} onClick={() => setPage(page + 1)} className="focus-ring min-h-10 rounded-xl border px-3 py-1.5 disabled:opacity-40">Next</button></div></div>
    </div>
    {form && <InventoryForm item={form.id ? form : undefined} ceo={ceo} close={() => setForm(null)} save={save} />}
    {bulk && <BulkForm rows={rows} setRows={setRows} ceo={ceo} close={() => setBulk(false)} save={submitBulk} />}
    {deleting && <Dialog title="Archive inventory item" close={() => setDeleting(null)}><p className="mt-4 text-sm text-[#60708a]">Archive {deleting.project} — {deleting.unit_number}? It will no longer appear in inventory.</p><div className="mt-5 flex justify-end gap-3"><button onClick={() => setDeleting(null)} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button onClick={() => void remove()} className="focus-ring min-h-11 rounded-xl bg-[#c43d4b] px-4 text-sm font-semibold text-white">Archive</button></div></Dialog>}
    {filtersOpen && <Dialog title="Filter inventory" close={() => setFiltersOpen(false)}><div className="mt-4">{filterControls}</div><div className="mt-5 grid grid-cols-2 gap-3"><button onClick={clear} className="focus-ring rounded-xl border border-[#dce4ee] px-4 py-2.5 text-sm font-bold text-[#405773]">Reset</button><button onClick={() => setFiltersOpen(false)} className="focus-ring rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-bold text-white">Apply filters</button></div></Dialog>}
  </section>;
}

function Fields({ item, ceo }: { item?: Partial<InventoryItem>; ceo: boolean }) {
  const fields: Array<[keyof InventoryRow, string, string]> = [["project", "Project", "text"], ["unit_number", "Unit / flat no.", "text"], ["property_type", "Property type", "text"], ["size_sqft", "Size (sq.ft)", "number"], ["floor", "Floor", "text"], ["basic_price", "Basic price", "number"], ...(ceo ? [["landing", "Landing", "number"] as [keyof InventoryRow, string, string]] : []), ["booking_date", "Booking date", "date"]];
  return <>{fields.map(([name, title, type]) => <label key={name} className="block text-sm font-medium text-[#405773]">{title}<input name={name} type={type} required={name !== "booking_date" && name !== "landing"} defaultValue={item?.[name as keyof InventoryItem] ?? ""} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5" /></label>)}<label className="block text-sm font-medium text-[#405773]">Status<select name="status" defaultValue={item?.status || "AVAILABLE"} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5">{statuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label></>;
}

function InventoryForm({ item, ceo, close, save }: { item?: InventoryItem; ceo: boolean; close: () => void; save: (event: FormEvent<HTMLFormElement>) => void }) {
  return <Dialog title={item ? "Inventory details" : "Add inventory"} close={close}><form onSubmit={save} className="mt-5 grid gap-4 sm:grid-cols-2"><Fields item={item} ceo={ceo} /><div className="sm:col-span-2 flex justify-end gap-3"><button type="button" onClick={close} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button className="focus-ring min-h-11 rounded-xl bg-[#0869d8] px-4 text-sm font-semibold text-white">Save</button></div></form></Dialog>;
}

function BulkForm({ rows, setRows, ceo, close, save }: { rows: InventoryRow[]; setRows: (rows: InventoryRow[]) => void; ceo: boolean; close: () => void; save: (event: FormEvent<HTMLFormElement>) => void }) {
  const update = (index: number, field: keyof InventoryRow, value: string) => setRows(rows.map((row, position) => position === index ? { ...row, [field]: value } : row));
  const fields: Array<[keyof InventoryRow, string, string]> = [["project", "Project", "text"], ["unit_number", "Unit / flat no.", "text"], ["property_type", "Property type", "text"], ["size_sqft", "Size (sq.ft)", "number"], ["floor", "Floor", "text"], ["basic_price", "Basic price", "number"], ...(ceo ? [["landing", "Landing", "number"] as [keyof InventoryRow, string, string]] : [])];
  return <Dialog title="Bulk add inventory" close={close}><form onSubmit={save} className="mt-5"><div className="space-y-4">{rows.map((row, index) => <fieldset key={index} className="rounded-2xl border border-[#e2eaf4] p-4"><legend className="px-1 text-sm font-bold text-[#405773]">Item {index + 1}</legend><div className="mt-2 grid gap-3 sm:grid-cols-2">{fields.map(([field, title, type]) => <label key={field} className="text-sm font-medium text-[#405773]">{title}<input required={field !== "landing"} type={type} value={row[field]} onChange={(event) => update(index, field, event.target.value)} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5" /></label>)}<label className="text-sm font-medium text-[#405773]">Status<select value={row.status} onChange={(event) => update(index, "status", event.target.value)} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] bg-white px-3 py-2.5">{statuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label><label className="text-sm font-medium text-[#405773]">Booking date<input type="date" value={row.booking_date} onChange={(event) => update(index, "booking_date", event.target.value)} className="focus-ring mt-1 w-full rounded-xl border border-[#dce4ee] px-3 py-2.5" /></label></div>{rows.length > 1 && <button type="button" onClick={() => setRows(rows.filter((_, position) => position !== index))} className="focus-ring mt-3 min-h-10 text-sm font-bold text-[#b12938]">Remove item</button>}</fieldset>)}</div><button type="button" onClick={() => setRows([...rows, blankRow()])} className="focus-ring mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl border border-[#0869d8] px-4 text-sm font-bold text-[#0869d8]"><Icon name="plus" className="h-4 w-4" />Add another item</button><div className="mt-5 flex justify-end gap-3"><button type="button" onClick={close} className="focus-ring min-h-11 rounded-xl px-4 text-sm font-semibold text-[#60708a]">Cancel</button><button className="focus-ring min-h-11 rounded-xl bg-[#0869d8] px-4 text-sm font-semibold text-white">Create {rows.length} item{rows.length === 1 ? "" : "s"}</button></div></form></Dialog>;
}
