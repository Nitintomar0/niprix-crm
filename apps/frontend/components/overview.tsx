import Link from "next/link";
import { Icon } from "@/components/icons";
import type { User } from "@/lib/types";

export function Overview({ user }: { user: User }) {
  return (
    <section>
      <p className="text-sm font-medium text-[#0869d8]">WORKSPACE OVERVIEW</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-[#10233f]">Welcome back, {user.username}.</h1>
      <p className="mt-2 text-sm text-[#60708a]">Your NIPRIX workspace brings people, attendance, and future CRM activity into one focused place.</p>
      <div className="mt-7 grid gap-5 lg:grid-cols-[1.25fr_.75fr]">
        <div className="brand-gradient relative overflow-hidden rounded-2xl p-7 text-white shadow-[0_16px_34px_rgba(6,58,138,.16)] sm:p-9">
          <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full border border-white/10" /><div className="absolute -bottom-20 right-14 h-48 w-48 rounded-full bg-[#ff8700]/25 blur-2xl" />
          <div className="relative"><span className="inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold">TODAY&apos;S FOCUS</span><h2 className="mt-5 max-w-lg text-3xl font-semibold tracking-tight">Keep your workday on track.</h2><p className="mt-3 max-w-lg text-sm leading-6 text-blue-100">Check your status, record time, and review your recent attendance from one dedicated view.</p><Link href="/attendance" className="focus-ring mt-7 inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-bold text-[#075ec0] shadow-lg transition hover:bg-[#f3f9ff]">Open my attendance<Icon name="arrow" className="h-4 w-4" /></Link></div>
        </div>
        <div className="app-card rounded-2xl p-6 sm:p-7"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#eff6fe] text-[#0869d8]"><Icon name="sparkle" className="h-5 w-5" /></span><h2 className="mt-5 text-xl font-semibold tracking-tight text-[#203756]">Built to grow with you</h2><p className="mt-3 text-sm leading-6 text-[#718198]">People, leads, follow-ups, and insights are being prepared as connected NIPRIX workspaces.</p><p className="mt-6 text-xs font-semibold tracking-[.12em] text-[#8a98aa]">ENTERPRISE CRM FOUNDATION</p></div>
      </div>
    </section>
  );
}
