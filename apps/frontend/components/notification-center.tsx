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
        className="notification-trigger focus-ring relative flex h-10 w-10 items-center justify-center rounded-xl border border-transparent transition"
      >
        <Icon name="bell" className="h-[19px] w-[19px]" />
        {unreadCount > 0 && <span className="notification-badge absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 px-1 text-[10px] font-bold">{unreadCount > 99 ? "99+" : unreadCount}</span>}
      </button>
      {isOpen && (
        <section role="dialog" aria-label="Notifications" className="notification-panel absolute right-0 top-[calc(100%+10px)] z-50 w-[min(390px,calc(100vw-1.5rem))] overflow-hidden rounded-2xl border">
          <header className="notification-panel__header flex items-center justify-between border-b px-5 py-4">
            <div><h2 className="notification-panel__title text-sm font-bold">Notifications</h2><p className="notification-panel__copy mt-0.5 text-xs">Your company workspace updates</p></div>
            <button type="button" disabled={!unreadCount || updating} onClick={() => void markAllRead()} className="notification-panel__action focus-ring text-xs font-bold">{updating ? "Saving…" : "Mark all read"}</button>
          </header>
          <div className="max-h-[420px] overflow-y-auto">
            {loading && <div className="space-y-3 p-5"><div className="shimmer h-16 rounded-xl" /><div className="shimmer h-16 rounded-xl" /><div className="shimmer h-16 rounded-xl" /></div>}
            {!loading && error && <div className="p-5"><p className="notification-panel__error rounded-xl p-3 text-sm">{error}</p><button type="button" onClick={() => void load()} className="notification-panel__action focus-ring mt-3 text-sm font-bold">Try again</button></div>}
            {!loading && !error && !items.length && <div className="p-9 text-center"><span className="notification-panel__empty-icon mx-auto flex h-11 w-11 items-center justify-center rounded-2xl"><Icon name="bell" className="h-5 w-5" /></span><p className="notification-panel__title mt-3 text-sm font-bold">You&apos;re all caught up</p><p className="notification-panel__copy mt-1 text-xs leading-5">New assignments and workspace updates will appear here.</p></div>}
            {!loading && !error && items.map((item) => <button type="button" key={item.id} onClick={() => void openNotification(item)} className={`notification-item focus-ring flex w-full gap-3 border-b px-5 py-4 text-left transition ${item.is_read ? "" : "notification-item--unread"}`}>
              <span className="notification-item__symbol mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold">{symbols[item.notification_type]}</span>
              <span className="min-w-0 flex-1"><span className="flex items-start justify-between gap-3"><strong className="notification-item__title text-sm">{item.title}</strong>{!item.is_read && <i className="notification-item__dot mt-1.5 h-2 w-2 shrink-0 rounded-full" />}</span><span className="notification-panel__copy mt-1 block text-xs leading-5">{item.body}</span><time className="notification-panel__time mt-1.5 block text-[11px] font-medium">{relativeTime(item.created_at)}</time></span>
            </button>)}
          </div>
        </section>
      )}
    </div>
  );
}
