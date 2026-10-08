"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ReminderPreference } from "@/lib/types";

export function ReminderPreferences() {
  const [preferences, setPreferences] = useState<ReminderPreference | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void api.reminderPreferences()
      .then(setPreferences)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Reminder preferences could not be loaded."));
  }, []);

  async function save() {
    if (!preferences) return;
    setSaving(true);
    setError("");
    try {
      setPreferences(await api.updateReminderPreferences(preferences));
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preferences could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  if (!preferences && !error) return <p className="text-sm text-[#60708a]">Loading reminder preferences…</p>;

  return <section>
    <p className="text-sm font-medium text-[#0869d8]">REMINDER PREFERENCES</p>
    <h1 className="mt-1 text-3xl font-semibold tracking-tight text-[#10233f]">Choose how work stays visible.</h1>
    <p className="mt-2 max-w-2xl text-sm leading-6 text-[#60708a]">In-app reminders are delivered through your notification center while the workspace is open.</p>
    {error && <p role="alert" className="mt-5 rounded-xl border border-[#f0c7cd] bg-[#fffafb] p-4 text-sm text-[#9a5860]">{error}</p>}
    {preferences && <div className="app-card mt-6 max-w-2xl rounded-2xl p-5 sm:p-7">
      <div className="space-y-5">
        <Toggle label="Upcoming follow-up reminders" detail="Notify you before scheduled follow-ups." checked={preferences.upcoming_follow_up_reminders_enabled} change={(checked) => setPreferences({ ...preferences, upcoming_follow_up_reminders_enabled: checked })} />
        <Toggle label="Overdue follow-up reminders" detail="Alert you when a follow-up remains overdue." checked={preferences.overdue_follow_up_reminders_enabled} change={(checked) => setPreferences({ ...preferences, overdue_follow_up_reminders_enabled: checked })} />
        <Toggle label="Overdue task reminders" detail="Prepare an in-app event when a task becomes overdue." checked={preferences.overdue_task_reminders_enabled} change={(checked) => setPreferences({ ...preferences, overdue_task_reminders_enabled: checked })} />
        <Toggle label="Daily summary preference" detail="Saved for a future, configured summary delivery channel." checked={preferences.daily_summary_enabled} change={(checked) => setPreferences({ ...preferences, daily_summary_enabled: checked })} />
        <label className="block max-w-xs text-sm font-semibold text-[#405773]">Reminder lead time (minutes)<input type="number" min="0" max="1440" value={preferences.reminder_lead_minutes} onChange={(event) => setPreferences({ ...preferences, reminder_lead_minutes: Number(event.target.value) })} className="focus-ring mt-2 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm" /></label>
      </div>
      <div className="mt-7 flex items-center justify-between"><span className="text-sm text-[#168460]">{saved ? "Saved." : ""}</span><button disabled={saving} onClick={() => void save()} className="focus-ring rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : "Save preferences"}</button></div>
    </div>}
  </section>;
}

function Toggle({ label, detail, checked, change }: { label: string; detail: string; checked: boolean; change: (checked: boolean) => void }) {
  return <label className="flex cursor-pointer items-start justify-between gap-4"><span><span className="block text-sm font-semibold text-[#405773]">{label}</span><span className="mt-1 block text-sm text-[#718198]">{detail}</span></span><input type="checkbox" checked={checked} onChange={(event) => change(event.target.checked)} className="focus-ring mt-1 h-5 w-5 accent-[#0869d8]" /></label>;
}
