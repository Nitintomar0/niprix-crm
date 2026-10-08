"use client";
/* eslint-disable react-hooks/set-state-in-effect -- API state resolves asynchronously. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/icons";
import { api } from "@/lib/api";
import type { Notification } from "@/lib/types";

const symbols: Record<Notification["notification_type"], string> = {
  LEAD_ASSIGNED: "●",
  FOLLOW_UP_ASSIGNED: "◷",
  FOLLOW_UP_REMINDER: "◷",
  TASK_ASSIGNED: "✓",
  ATTENDANCE: "●",
  LEAVE_REQUEST: "◫",
  INVENTORY: "⌂",
  RAW_DATA: "↗",
  SYSTEM: "✦",
};

function relativeTime(value: string) {
  const elapsed = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.round(elapsed / 60_000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function NotificationCenter() {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState(false);
  const initialized = useRef(false);
  const knownNotificationIds = useRef<Set<number>>(new Set());

  function announceFollowUpReminder(item: Notification) {
    if (item.notification_type !== "FOLLOW_UP_REMINDER") return;
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(item.title, { body: item.body, tag: `niprix-notification-${item.id}` });
    }
    const AudioContextConstructor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextConstructor) return;
    const context = new AudioContextConstructor();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(660, context.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(880, context.currentTime + 0.12);
    gain.gain.setValueAtTime(0.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.28);
    oscillator.connect(gain).connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.3);
    window.setTimeout(() => void context.close(), 400);
  }

  const load = useCallback(async () => {
    try {
      setError("");
      const [notifications, unread] = await Promise.all([
        api.notifications(),
        api.notificationUnreadCount(),
      ]);
      if (initialized.current) {
        notifications.results.filter((item) => !knownNotificationIds.current.has(item.id) && !item.is_read).forEach(announceFollowUpReminder);
      }
      initialized.current = true;
      knownNotificationIds.current = new Set(notifications.results.map((item) => item.id));
      setItems(notifications.results);
      setUnreadCount(unread.count);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Notifications could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(interval);
  }, [load]);

  async function openNotification(item: Notification) {
    setIsOpen(false);
    if (!item.is_read) {
      setItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, is_read: true } : entry));
      setUnreadCount((current) => Math.max(0, current - 1));
      try {
        await api.markNotificationRead(item.id);
      } catch {
        void load();
      }
    }
    if (item.href.startsWith("/")) router.push(item.href);
  }

  async function markAllRead() {
    if (!unreadCount) return;
    setUpdating(true);
    try {
      await api.markAllNotificationsRead();
      setItems((current) => current.map((item) => ({ ...item, is_read: true })));
      setUnreadCount(0);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not mark notifications as read.");
    } finally {
      setUpdating(false);
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={unreadCount ? `${unreadCount} unread notifications` : "Notifications"}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        onClick={() => {
          const next = !isOpen;
          setIsOpen(next);
          if (next) void load();
        }}
        className="focus-ring relative flex h-10 w-10 items-center justify-center rounded-xl border border-transparent text-[#526984] transition hover:border-[#e0e8f1] hover:bg-[#f5f8fc] hover:text-[#0869d8]"
      >
        <Icon name="bell" className="h-[19px] w-[19px]" />
        {unreadCount > 0 && <span className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 border-white bg-[#ff8a00] px-1 text-[10px] font-bold text-white">{unreadCount > 99 ? "99+" : unreadCount}</span>}
      </button>
      {isOpen && (
        <section role="dialog" aria-label="Notifications" className="absolute right-0 top-[calc(100%+10px)] z-50 w-[min(390px,calc(100vw-1.5rem))] overflow-hidden rounded-2xl border border-[#e1e9f2] bg-white shadow-[0_20px_48px_rgba(16,35,63,.16)]">
          <header className="flex items-center justify-between border-b border-[#edf1f6] px-5 py-4">
            <div><h2 className="text-sm font-bold text-[#10233f]">Notifications</h2><p className="mt-0.5 text-xs text-[#718198]">Your company workspace updates</p></div>
            <button type="button" disabled={!unreadCount || updating} onClick={() => void markAllRead()} className="focus-ring text-xs font-bold text-[#0869d8] disabled:text-[#a6b3c3]">{updating ? "Saving…" : "Mark all read"}</button>
          </header>
          <div className="max-h-[420px] overflow-y-auto">
            {loading && <div className="space-y-3 p-5"><div className="shimmer h-16 rounded-xl" /><div className="shimmer h-16 rounded-xl" /><div className="shimmer h-16 rounded-xl" /></div>}
            {!loading && error && <div className="p-5"><p className="rounded-xl bg-[#fff5f5] p-3 text-sm text-[#a72536]">{error}</p><button type="button" onClick={() => void load()} className="focus-ring mt-3 text-sm font-bold text-[#0869d8]">Try again</button></div>}
            {!loading && !error && !items.length && <div className="p-9 text-center"><span className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-[#eaf4ff] text-[#0869d8]"><Icon name="bell" className="h-5 w-5" /></span><p className="mt-3 text-sm font-bold text-[#253a59]">You&apos;re all caught up</p><p className="mt-1 text-xs leading-5 text-[#718198]">New assignments and workspace updates will appear here.</p></div>}
            {!loading && !error && items.map((item) => <button type="button" key={item.id} onClick={() => void openNotification(item)} className={`focus-ring flex w-full gap-3 border-b border-[#f0f3f7] px-5 py-4 text-left transition hover:bg-[#f8fbff] ${item.is_read ? "" : "bg-[#f1f7ff]"}`}>
              <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${item.is_read ? "bg-[#f0f4f8] text-[#718198]" : "bg-[#dceeff] text-[#0869d8]"}`}>{symbols[item.notification_type]}</span>
              <span className="min-w-0 flex-1"><span className="flex items-start justify-between gap-3"><strong className="text-sm text-[#253a59]">{item.title}</strong>{!item.is_read && <i className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#0869d8]" />}</span><span className="mt-1 block text-xs leading-5 text-[#60708a]">{item.body}</span><time className="mt-1.5 block text-[11px] font-medium text-[#8a98aa]">{relativeTime(item.created_at)}</time></span>
            </button>)}
          </div>
        </section>
      )}
    </div>
  );
}
