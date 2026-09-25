"use client";

import { FormEvent, useState } from "react";
import { FullLogo } from "@/components/brand";
import { Icon } from "@/components/icons";

export function LoginScreen({ onSubmit, error }: { onSubmit: (username: string, password: string) => Promise<void>; error?: string }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); try { await onSubmit(username, password); } finally { setBusy(false); } }
  return (
    <main className="soft-grid min-h-screen bg-[#f6f9fd] p-4 sm:p-8">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-6xl overflow-hidden rounded-[28px] border border-[#dce5ef] bg-white shadow-[0_24px_80px_rgba(16,35,63,.12)] lg:grid-cols-[1.06fr_.94fr]">
        <section className="brand-gradient relative hidden overflow-hidden p-12 text-white lg:flex lg:flex-col">
          <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full border border-white/15" /><div className="absolute -bottom-40 -left-28 h-96 w-96 rounded-full bg-[#ff8a00]/20 blur-2xl" />
          <div className="relative"><div className="mb-16 rounded-2xl bg-white p-3 shadow-xl"><FullLogo className="h-auto w-48" /></div><p className="text-sm font-medium tracking-[.18em] text-sky-100">ENTERPRISE REAL ESTATE CRM</p><h1 className="mt-5 max-w-md text-4xl font-semibold leading-tight tracking-tight">A clearer rhythm for your people and property teams.</h1><p className="mt-5 max-w-md text-base leading-7 text-blue-100">Manage the day with focused attendance tools today, and a CRM foundation ready for every relationship tomorrow.</p></div>
          <div className="relative mt-auto flex items-center gap-3 text-sm text-blue-100"><span className="flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-white/10"><Icon name="shield" className="h-5 w-5" /></span><span>Secure, role-aware workspace</span></div>
        </section>
        <section className="flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-sm"><div className="mb-10 lg:hidden"><FullLogo className="h-auto w-56" /></div><p className="text-sm font-semibold tracking-wide text-[#0869d8]">WELCOME BACK</p><h2 className="mt-2 text-3xl font-semibold tracking-tight text-[#10233f]">Sign in to NIPRIX</h2><p className="mt-3 text-sm leading-6 text-[#60708a]">Use your company credentials to access your secure workspace.</p>
            <form className="mt-8 space-y-5" onSubmit={submit}><label className="block text-sm font-medium text-[#253a59]">Username<input required autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} className="focus-ring mt-2 block w-full rounded-xl border border-[#d9e2ed] bg-white px-4 py-3 text-[#10233f] shadow-sm placeholder:text-[#a7b2c1]" placeholder="Enter your username" /></label><label className="block text-sm font-medium text-[#253a59]">Password<input required minLength={1} autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="focus-ring mt-2 block w-full rounded-xl border border-[#d9e2ed] bg-white px-4 py-3 text-[#10233f] shadow-sm placeholder:text-[#a7b2c1]" placeholder="Enter your password" /></label>
              {error && <p role="alert" className="flex gap-2 rounded-xl bg-[#fff2f3] p-3 text-sm text-[#a72536]"><Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />{error}</p>}<button disabled={busy} className="focus-ring flex w-full items-center justify-center gap-2 rounded-xl bg-[#0869d8] px-4 py-3.5 text-sm font-semibold text-white shadow-[0_10px_18px_rgba(8,105,216,.22)] transition hover:bg-[#075fc2] disabled:opacity-60">{busy ? "Signing in…" : "Sign in securely"}<Icon name="arrow" className="h-4 w-4" /></button></form>
            <p className="mt-8 text-center text-xs leading-5 text-[#8a98ab]">Your access is controlled by your organization&apos;s role and permissions.</p></div>
        </section>
      </div>
    </main>
  );
}
