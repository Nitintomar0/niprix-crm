"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppDialog } from "@/components/app-dialog";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { CustomerLedger, IssuedReceipt, Role } from "@/lib/types";

const money = (value: string) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value));
const input = "mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2.5 text-sm text-[var(--ink)] outline-none focus:border-[var(--brand-strong)]";
const today = () => new Date().toISOString().slice(0, 10);

export function AccountsLedger({ role, customerId }: { role: Role; customerId?: number }) {
  const router = useRouter();
  const [customers, setCustomers] = useState<CustomerLedger[]>([]);
  const [customer, setCustomer] = useState<CustomerLedger | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [working, setWorking] = useState(false);

  const load = useCallback(async () => {
    if (role !== "CEO") return;
    setLoading(true); setError("");
    try {
      if (customerId) setCustomer(await api.accountCustomer(customerId));
      else {
        const result = await api.accountCustomers(`page=${page}&page_size=25${query ? `&search=${encodeURIComponent(query)}` : ""}`);
        setCustomers(result.results); setCount(result.count);
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Accounts could not be loaded."); }
    finally { setLoading(false); }
  }, [customerId, page, query, role]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), query && !customerId ? 220 : 0); return () => window.clearTimeout(timer); }, [load, query, customerId]);

  async function createCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setWorking(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const created = await api.createAccountCustomer(Object.fromEntries(form));
      setCreateOpen(false);
      router.push(`/accounts/${created.id}`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Customer could not be created."); }
    finally { setWorking(false); }
  }

  async function openReceipt(receipt: IssuedReceipt, print = false) {
    try {
      const blob = await api.downloadAccountReceipt(receipt.id);
      const url = URL.createObjectURL(blob);
      const target = window.open(url, "_blank", "noopener,noreferrer");
      if (print && target) target.addEventListener("load", () => target.print(), { once: true });
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Receipt PDF could not be opened."); }
  }

  async function issueReceipt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!customer) return;
    setWorking(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api.issueAccountReceipt(customer.id, {
        serial_number: String(form.get("serial_number") || ""), receipt_date: String(form.get("receipt_date") || ""),
        amount: String(form.get("amount") || ""), payment_method: String(form.get("payment_method") || "CASH"),
        reference_number: String(form.get("reference_number") || ""), drawn_on: String(form.get("drawn_on") || ""),
        idempotency_key: crypto.randomUUID(),
      });
      setReceiptOpen(false); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Receipt could not be issued."); }
    finally { setWorking(false); }
  }

  async function cancelReceipt(receipt: IssuedReceipt) {
    const reason = window.prompt(`Cancellation reason for receipt ${receipt.serial_number}:`);
    if (!reason?.trim()) return;
    setWorking(true); setError("");
    try { await api.cancelAccountReceipt(receipt.id, reason.trim()); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Receipt could not be cancelled."); }
    finally { setWorking(false); }
  }

  const formError = createOpen || receiptOpen ? error : "";
  const pages = Math.max(1, Math.ceil(count / 25));

  if (role !== "CEO") return <section className="app-card rounded-2xl border p-6"><h1 className="page-title text-xl font-bold">Accounts</h1><p className="page-copy mt-2">Accounts is restricted to the CEO / Super Admin.</p></section>;

  if (customerId) return <><CustomerProfile customer={customer} loading={loading} error={error} onOpenReceipt={openReceipt} onCancel={cancelReceipt} onIssue={() => setReceiptOpen(true)} />{receiptOpen && customer && <AppDialog title="Generate original receipt" close={() => setReceiptOpen(false)} maxWidth="max-w-xl"><ReceiptForm customer={customer} onSubmit={issueReceipt} working={working} error={formError} /></AppDialog>}</>;

  return <section className="space-y-5">
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><p className="page-kicker text-[11px] font-bold uppercase tracking-[.14em]">Accounts</p><h1 className="page-title mt-1 text-2xl font-bold">Customer ledger</h1><p className="page-copy mt-1 text-sm">Permanent property payment records and original receipts.</p></div><button onClick={() => setCreateOpen(true)} className="brand-button focus-ring inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold text-white"><Icon name="plus" className="h-4 w-4" />Add customer</button></div>
    {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
    <div className="app-card overflow-hidden rounded-2xl border"><div className="border-b p-4"><label className="relative block max-w-md"><Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ink-soft)]" /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search name, mobile, project or plot…" className="w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] py-2.5 pl-10 pr-3 text-sm outline-none" /></label></div><div className="overflow-x-auto"><table className="w-full min-w-[860px] text-left text-sm"><thead className="bg-[var(--surface-soft)] text-[11px] uppercase tracking-wide text-[var(--ink-soft)]"><tr><th className="px-4 py-3">Customer</th><th className="px-4 py-3">Property</th><th className="px-4 py-3">Agreed</th><th className="px-4 py-3">Received</th><th className="px-4 py-3">Outstanding</th><th className="px-4 py-3">Due</th><th className="px-4 py-3" /></tr></thead><tbody>{loading ? <tr><td colSpan={7} className="px-4 py-12 text-center text-[var(--ink-soft)]">Loading ledger…</td></tr> : customers.length ? customers.map((item) => <tr key={item.id} className="border-t border-[var(--line)]"><td className="px-4 py-3"><p className="font-semibold">{item.name}</p><p className="text-xs text-[var(--ink-soft)]">{item.customer_id} · {item.mobile}</p></td><td className="px-4 py-3"><p>{item.project || "—"}</p><p className="text-xs text-[var(--ink-soft)]">Plot {item.plot_number || "—"} · {item.plot_size || "—"}</p></td><td className="px-4 py-3">{money(item.total_agreed_amount)}</td><td className="px-4 py-3">{money(item.total_received)}</td><td className="px-4 py-3 font-semibold">{money(item.outstanding_balance)}</td><td className="px-4 py-3">{item.due_date || "—"}</td><td className="px-4 py-3"><Link href={`/accounts/${item.id}`} className="focus-ring rounded-lg px-2 py-1.5 text-sm font-bold text-[var(--brand-strong)]">View</Link></td></tr>) : <tr><td colSpan={7} className="px-4 py-12 text-center text-[var(--ink-soft)]">No customer ledger records found.</td></tr>}</tbody></table></div><div className="flex items-center justify-between border-t px-4 py-3 text-sm text-[var(--ink-soft)]"><span>{count} customer{count === 1 ? "" : "s"}</span><span className="flex items-center gap-2"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border px-3 py-1.5 disabled:opacity-40">Previous</button><span>Page {page} of {pages}</span><button disabled={page >= pages} onClick={() => setPage((value) => value + 1)} className="rounded-lg border px-3 py-1.5 disabled:opacity-40">Next</button></span></div></div>
    {createOpen && <AppDialog title="Add customer ledger" close={() => setCreateOpen(false)} maxWidth="max-w-2xl"><CustomerForm onSubmit={createCustomer} working={working} error={formError} /></AppDialog>}
  </section>;
}

function CustomerProfile({ customer, loading, error, onOpenReceipt, onCancel, onIssue }: { customer: CustomerLedger | null; loading: boolean; error: string; onOpenReceipt: (receipt: IssuedReceipt, print?: boolean) => void; onCancel: (receipt: IssuedReceipt) => void; onIssue: () => void }) {
  if (loading) return <p className="page-copy">Loading customer profile…</p>;
  if (!customer) return <section className="app-card rounded-2xl border p-6"><Link href="/accounts" className="text-sm font-bold text-[var(--brand-strong)]">← Customer ledger</Link><p role="alert" className="mt-4 text-sm text-red-700">{error || "Customer record was not found."}</p></section>;
  return <section className="space-y-5"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><Link href="/accounts" className="text-sm font-bold text-[var(--brand-strong)]">← Customer ledger</Link><p className="page-kicker mt-4 text-[11px] font-bold uppercase tracking-[.14em]">{customer.customer_id}</p><h1 className="page-title mt-1 text-2xl font-bold">{customer.name}</h1><p className="page-copy mt-1 text-sm">{customer.mobile} · {customer.residential_address || "No address recorded"}</p></div><button onClick={onIssue} className="brand-button focus-ring inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold text-white"><Icon name="plus" className="h-4 w-4" />Generate receipt</button></div><div className="grid gap-3 sm:grid-cols-3"><Metric label="Total agreed" value={money(customer.total_agreed_amount)} /><Metric label="Total received" value={money(customer.total_received)} /><Metric label="Outstanding balance" value={money(customer.outstanding_balance)} /></div><div className="grid gap-4 lg:grid-cols-3"><section className="app-card rounded-2xl border p-5 lg:col-span-1"><p className="text-xs font-bold uppercase tracking-wide text-[var(--ink-soft)]">Property details</p><dl className="mt-4 space-y-3 text-sm"><Detail label="Project / location" value={customer.project} /><Detail label="Plot no." value={customer.plot_number} /><Detail label="Plot size" value={customer.plot_size} /><Detail label="Due date" value={customer.due_date || "—"} /><Detail label="Status" value={customer.status.replace("_", " ")} /></dl></section><section className="app-card overflow-hidden rounded-2xl border lg:col-span-2"><div className="border-b px-5 py-4"><h2 className="font-bold">Payment & receipt history</h2><p className="mt-1 text-sm text-[var(--ink-soft)]">Issued receipts remain preserved even if a payment is cancelled.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-[var(--surface-soft)] text-[11px] uppercase tracking-wide text-[var(--ink-soft)]"><tr><th className="px-4 py-3">Receipt</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Amount</th><th className="px-4 py-3">Method</th><th className="px-4 py-3">Status</th><th className="px-4 py-3" /></tr></thead><tbody>{customer.receipts.length ? customer.receipts.map((receipt) => <tr key={receipt.id} className="border-t border-[var(--line)]"><td className="px-4 py-3 font-semibold">{receipt.serial_number}</td><td className="px-4 py-3">{receipt.receipt_date}</td><td className="px-4 py-3">{money(receipt.amount_received)}</td><td className="px-4 py-3">{receipt.payment_method}</td><td className="px-4 py-3"><span className={receipt.status === "ISSUED" ? "text-emerald-700" : "text-red-700"}>{receipt.status}</span></td><td className="px-4 py-3 whitespace-nowrap"><button onClick={() => onOpenReceipt(receipt)} className="mr-3 font-bold text-[var(--brand-strong)]">Download</button><button onClick={() => onOpenReceipt(receipt, true)} className="mr-3 font-bold text-[var(--brand-strong)]">Print</button>{receipt.status === "ISSUED" && <button onClick={() => onCancel(receipt)} className="font-bold text-red-700">Cancel</button>}</td></tr>) : <tr><td colSpan={6} className="px-4 py-10 text-center text-[var(--ink-soft)]">No payments or receipts have been issued.</td></tr>}</tbody></table></div></section></div></section>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="app-card rounded-2xl border p-4"><p className="text-xs font-bold uppercase tracking-wide text-[var(--ink-soft)]">{label}</p><p className="mt-2 text-xl font-bold">{value}</p></div>; }
function Detail({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs text-[var(--ink-soft)]">{label}</dt><dd className="mt-0.5 font-semibold">{value || "—"}</dd></div>; }

function CustomerForm({ onSubmit, working, error }: { onSubmit: (event: FormEvent<HTMLFormElement>) => void; working: boolean; error: string }) { return <form onSubmit={onSubmit} className="space-y-5 pt-5"><p className="text-sm text-[var(--ink-soft)]">Create the permanent profile before recording any payment.</p>{error && <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}<div className="grid gap-4 sm:grid-cols-2"><Field label="Customer name" name="name" required /><Field label="Mobile number" name="mobile" required /><Field label="Project / location" name="project" /><Field label="Plot number" name="plot_number" /><Field label="Plot size" name="plot_size" /><Field label="Total agreed amount" name="total_agreed_amount" type="number" min="0.01" step="0.01" required /><Field label="Due date" name="due_date" type="date" /><label className="sm:col-span-2 text-sm font-semibold">Residential address<textarea name="residential_address" rows={2} className={input} /></label><label className="text-sm font-semibold">Record status<select name="status" defaultValue="ACTIVE" className={input}><option value="ACTIVE">Active</option><option value="ON_HOLD">On hold</option><option value="CLOSED">Closed</option></select></label></div><div className="flex justify-end"><button disabled={working} className="brand-button rounded-xl px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60">{working ? "Saving…" : "Create customer"}</button></div></form>; }
function ReceiptForm({ customer, onSubmit, working, error }: { customer: CustomerLedger; onSubmit: (event: FormEvent<HTMLFormElement>) => void; working: boolean; error: string }) { return <form onSubmit={onSubmit} className="space-y-5 pt-5"><p className="rounded-xl bg-[var(--surface-soft)] px-3 py-2.5 text-sm text-[var(--ink-soft)]">{customer.name} · outstanding balance: <strong className="text-[var(--ink)]">{money(customer.outstanding_balance)}</strong><span className="mt-1 block text-xs">Prefilled: {customer.mobile} · {customer.project || "No project"} · Plot {customer.plot_number || "—"} · {customer.plot_size || "—"}</span></p>{error && <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}<div className="grid gap-4 sm:grid-cols-2"><Field label="Receipt Sr. No." name="serial_number" required /><label className="text-sm font-semibold">Date<input name="receipt_date" type="date" required defaultValue={today()} className={input} /></label><Field label="Receive amount" name="amount" type="number" min="0.01" step="0.01" required /><label className="text-sm font-semibold">Payment method<select name="payment_method" defaultValue="CASH" className={input}><option value="CASH">Cash</option><option value="CHEQUE">Cheque</option><option value="DRAFT">Draft</option><option value="TRANSFER">Bank transfer</option><option value="UPI">UPI</option></select></label><Field label="Cheque / draft / transaction no." name="reference_number" /><Field label="Drawn on" name="drawn_on" /></div><p className="text-xs text-[var(--ink-soft)]">The serial number is entered manually, verified within your company, and permanently preserved with this payment.</p><div className="flex justify-end"><button disabled={working} className="brand-button rounded-xl px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60">{working ? "Issuing…" : "Issue receipt"}</button></div></form>; }
function Field({ label, name, type = "text", required, min, step }: { label: string; name: string; type?: string; required?: boolean; min?: string; step?: string }) { return <label className="text-sm font-semibold">{label}<input name={name} type={type} required={required} min={min} step={step} className={input} /></label>; }
