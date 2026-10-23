"use client";

import Image from "next/image";
import { FormEvent, useState } from "react";
import { FullLogo } from "@/components/brand";
import { Icon } from "@/components/icons";
import { ThemeToggle } from "@/components/theme-toggle";

function PartnerBranding({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-center justify-center gap-2 rounded-2xl bg-white p-2.5 shadow-xl ${compact ? "max-w-[340px]" : "w-fit"}`}>
      <FullLogo className={compact ? "h-auto w-24" : "h-auto w-28"} />
      <span aria-hidden="true" className="text-lg font-light text-[#0869d8]">∞</span>
      <Image src="/brand/paramshiv-logo.png" alt="Paramshiv Urban Real Estate" width={1880} height={836} priority className={compact ? "h-auto w-[122px] object-contain" : "h-auto w-[145px] object-contain"} />
    </div>
  );
}

export function LoginScreen({ onSubmit, error }: { onSubmit: (username: string, password: string) => Promise<void>; error?: string }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try { await onSubmit(username, password); } finally { setBusy(false); }
  }

  return (
    <main className="soft-grid relative min-h-screen bg-[#f8f7fc] p-4 sm:p-7 lg:p-8">
      <div className="absolute right-5 top-5 z-10 sm:right-8 sm:top-8"><ThemeToggle /></div>
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-6xl overflow-hidden rounded-[32px] border border-[#e3ddeb] bg-white shadow-[0_28px_90px_rgba(23,35,63,.14)] lg:grid-cols-[1.08fr_.92fr]">
        <section className="brand-gradient relative hidden overflow-hidden p-12 text-white lg:flex lg:flex-col">
          <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full border border-white/15" />
          <div className="absolute right-[12%] top-[38%] h-40 w-40 rounded-full bg-[#cbb3e8]/25 blur-3xl" />
          <div className="absolute -bottom-40 -left-28 h-96 w-96 rounded-full bg-[#d88858]/20 blur-2xl" />
          <div className="relative">
            <div className="animate-[page-enter_.55s_ease-out_both]"><PartnerBranding /></div>
            <p className="mt-16 text-xs font-bold tracking-[.2em] text-[#dac9ef]">ENTERPRISE REAL ESTATE CRM</p>
            <h1 className="mt-5 max-w-md text-[42px] font-semibold leading-[1.1] tracking-tight">A beautifully focused rhythm for every property conversation.</h1>
            <p className="mt-5 max-w-md text-base leading-7 text-[#e7dcf4]">A secure command center for leads, site visits, teams, and the work that moves your business forward.</p>
          </div>
          <div className="relative mt-auto flex items-center gap-3 text-sm text-[#e7dcf4]"><span className="flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-white/10"><Icon name="shield" className="h-5 w-5" /></span><span>Secure, role-aware workspace</span></div>
        </section>
        <section className="flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-sm">
            <div className="mb-10 animate-[page-enter_.45s_ease-out_both] lg:hidden"><PartnerBranding compact /></div>
            <div className="card-enter"><p className="text-xs font-bold tracking-[.18em] text-[#805bab]">WELCOME BACK</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-[#17233f]">Sign in to NIPRIX</h2>
            <p className="mt-3 text-sm leading-6 text-[#66738d]">Use your company credentials to access your secure workspace.</p></div>
            <form className="mt-8 space-y-5" onSubmit={submit}>
              <label className="block text-sm font-semibold text-[#293754]">Username<input required autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} className="focus-ring mt-2 block w-full rounded-xl border border-[#ded8e8] bg-[#fcfbfd] px-4 py-3 text-[#17233f] shadow-sm placeholder:text-[#9ba3b4] transition focus:border-[#b59bd7] focus:bg-white" placeholder="Enter your username" /></label>
              <label className="block text-sm font-semibold text-[#293754]">Password<input required minLength={1} autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="focus-ring mt-2 block w-full rounded-xl border border-[#ded8e8] bg-[#fcfbfd] px-4 py-3 text-[#17233f] shadow-sm placeholder:text-[#9ba3b4] transition focus:border-[#b59bd7] focus:bg-white" placeholder="Enter your password" /></label>
              {error && <p role="alert" className="flex gap-2 rounded-xl bg-[#fff4f5] p-3 text-sm text-[#a3344a]"><Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />{error}</p>}
              <button disabled={busy} className="brand-button focus-ring flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Signing in…" : "Sign in securely"}<Icon name="arrow" className="h-4 w-4" /></button>
            </form>
            <p className="mt-8 text-center text-xs leading-5 text-[#8991a2]">Your access is controlled by your organization&apos;s role and permissions.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
