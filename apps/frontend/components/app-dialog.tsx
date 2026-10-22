"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Icon } from "@/components/icons";
import { createPortal } from "react-dom";
type AppDialogProps = {
  title: string;
  close: () => void;
  children: ReactNode;
  maxWidth?: "max-w-xl" | "max-w-2xl" | "max-w-5xl";
};

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/** A viewport-anchored dialog with scroll locking and predictable keyboard focus. */
export function AppDialog({ title, close, children, maxWidth = "max-w-2xl" }: AppDialogProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef(close);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
  setMounted(true);
}, []);

  useEffect(() => {
    closeRef.current = close;
  }, [close]);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => panelRef.current?.focus());
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, []);

  function containFocus(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab") return;
    const focusable = Array.from(panelRef.current?.querySelectorAll<HTMLElement>(focusableSelector) ?? []);
    if (!focusable.length) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  if (!mounted) return null;
  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto overscroll-contain p-3 pt-16 sm:items-center sm:p-5"
    >
      <button
        type="button"
        aria-label={`Close ${title}`}
        onClick={close}
        className="dialog-backdrop fixed inset-0"
      />

      <section
        ref={panelRef}
        tabIndex={-1}
        onKeyDown={containFocus}
        className={`dialog-panel relative z-[101] my-auto flex max-h-[calc(100dvh-6rem)] w-full flex-col overflow-hidden rounded-2xl bg-white shadow-[0_28px_80px_rgba(34,35,68,.26)] sm:max-h-[calc(100dvh-2.5rem)] ${maxWidth}`}
      >
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-[#eee8f4] bg-white px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="text-[10px] font-bold tracking-[.15em] text-[#805bab]">
              NIPRIX CRM
            </p>
            <h2
              id={titleId}
              className="mt-0.5 truncate text-xl font-bold tracking-tight text-[#222344]"
            >
              {title}
            </h2>
          </div>

          <button
            type="button"
            onClick={close}
            aria-label={`Close ${title}`}
            className="focus-ring flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[#69708a] transition hover:bg-[#f4eff9] hover:text-[#684496]"
          >
            <Icon name="close" className="h-5 w-5" />
          </button>
        </header>

        <div className="min-h-0 overflow-y-auto overscroll-contain px-5 pb-5 sm:px-6 sm:pb-6">
          {children}
        </div>
      </section>
      </div>,
    document.body
  );
}
