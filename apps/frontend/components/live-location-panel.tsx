"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api, liveLocationSocketUrl } from "@/lib/api";
import { ApiError, type LiveLocation } from "@/lib/types";

const LiveLocationMap = dynamic(() => import("@/components/live-location-map").then((module) => module.LiveLocationMap), {
  ssr: false,
  loading: () => <div className="h-[300px] animate-pulse rounded-xl bg-[#edf3f8] sm:h-[360px]" />,
});
const STALE_AFTER_MS = 180_000;

function relativeTime(value?: string) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
}
function isUsable(state: LiveLocation) {
  return state.status === "live" && typeof state.latitude === "number" && typeof state.longitude === "number" && Boolean(state.updated_at) && Date.now() - new Date(state.updated_at!).getTime() <= STALE_AFTER_MS;
}

export function LiveLocationPanel({ employeeId }: { employeeId: number }) {
  const [location, setLocation] = useState<LiveLocation>({ status: "unavailable" });
  const [loading, setLoading] = useState(true);
  const [serviceError, setServiceError] = useState(false);
  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    const apply = (next: LiveLocation) => { if (active) setLocation(next); };
    void api.employeeLiveLocation(employeeId).then((state) => { setServiceError(false); apply(state); }).catch((error) => { if (active) { setServiceError(error instanceof ApiError && error.status >= 500); apply({ status: "unavailable" }); } }).finally(() => { if (active) setLoading(false); });
    const connect = () => {
      const url = liveLocationSocketUrl(employeeId);
      if (!url || !active) return;
      socket = new WebSocket(url);
      socket.onmessage = (event) => {
        try { const message = JSON.parse(event.data) as { type?: string; state?: LiveLocation }; if (message.type === "location" && message.state) apply(message.state); } catch { /* Ignore malformed relay data. */ }
      };
      socket.onclose = () => { if (active) retry = window.setTimeout(connect, 10_000); };
    };
    connect();
    const staleTimer = window.setInterval(() => setLocation((current) => current.status !== "live" || isUsable(current) ? current : { status: "unavailable", reason: current.updated_at ? "stale" : "offline" }), 15_000);
    return () => { active = false; if (retry) window.clearTimeout(retry); window.clearInterval(staleTimer); socket?.close(); };
  }, [employeeId]);
  const usable = isUsable(location);
  const mapsUrl = usable ? `https://www.google.com/maps?q=${encodeURIComponent(`${location.latitude},${location.longitude}`)}` : null;
  const openMaps = () => { if (mapsUrl) window.open(mapsUrl, "_blank", "noopener,noreferrer"); };
  const reason = serviceError ? "Location service unavailable" : location.reason === "stale" ? "Location stale" : location.reason === "permission_denied" ? "Location permission not granted" : location.reason === "position_unavailable" ? "Device location unavailable" : location.reason === "timeout" ? "Location request timed out" : location.reason === "missing_coordinates" ? "Location coordinates unavailable" : "Location unavailable";
  return <section className="app-card overflow-hidden rounded-2xl">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#e7edf4] px-5 py-4 sm:px-6">
      <div><p className="text-xs font-bold tracking-[.14em] text-[#0869d8]">CEO ONLY</p><h2 className="mt-1 text-lg font-semibold tracking-tight text-[#10233f]">Live location</h2></div>
      <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-bold ${usable ? "bg-[#e9f7f0] text-[#168460]" : "bg-[#f2f5f8] text-[#718198]"}`}><i className={`h-2 w-2 rounded-full ${usable ? "bg-[#20aa77]" : "bg-[#a4b0bf]"}`} />{usable ? "LIVE" : reason.toUpperCase()}</span>
    </div>
    <div className="grid gap-6 p-5 lg:grid-cols-[minmax(0,1fr)_260px] sm:p-6">
      {usable ? <LiveLocationMap latitude={location.latitude!} longitude={location.longitude!} onOpen={openMaps} /> : <div className="flex min-h-[300px] items-center justify-center rounded-xl border border-dashed border-[#cedae6] bg-[#f8fbfd] p-7 text-center sm:min-h-[360px]"><div><span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#eaf3fb] text-xl text-[#0869d8]">⌖</span><h3 className="mt-4 font-semibold text-[#203756]">{loading ? "Checking live status…" : reason}</h3><p className="mt-2 max-w-xs text-sm leading-6 text-[#718198]">{serviceError ? "The temporary live-location service cannot be reached. Check the configured Redis service." : location.reason === "permission_denied" ? "The employee has not granted browser location permission. The browser will be asked again while attendance remains active, where supported." : location.reason === "stale" ? "No recent location update was received." : "The employee is not currently sharing a location during an active attendance session."}</p></div></div>}
      <aside className="space-y-4"><div className="rounded-xl bg-[#f7faff] p-4"><p className="text-xs font-medium text-[#718198]">Attendance</p><p className="mt-1 text-sm font-semibold text-[#203756]">{usable ? "Checked in" : "Not live"}</p></div><div className="grid grid-cols-2 gap-3 lg:grid-cols-1"><div><p className="text-xs font-medium text-[#718198]">Last updated</p><p className="mt-1 text-sm font-semibold text-[#203756]">{usable ? relativeTime(location.updated_at) : "—"}</p></div><div><p className="text-xs font-medium text-[#718198]">Accuracy</p><p className="mt-1 text-sm font-semibold text-[#203756]">{usable ? `±${Math.round(location.accuracy ?? 0)}m` : "—"}</p></div></div><button disabled={!mapsUrl} onClick={openMaps} className="focus-ring w-full rounded-xl bg-[#0869d8] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#075dbd] disabled:bg-[#d6e0ea] disabled:text-[#718198]">Open in Google Maps ↗</button><p className="text-xs leading-5 text-[#8291a4]">Click the map or open the latest reported position in Google Maps.</p></aside>
    </div>
  </section>;
}
