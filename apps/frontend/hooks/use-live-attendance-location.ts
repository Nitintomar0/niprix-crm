"use client";

import { useCallback, useEffect, useRef } from "react";
import { api } from "@/lib/api";

const SEND_INTERVAL_MS = 60_000;
const PERMISSION_RETRY_MS = 60 * 60_000;

/** Silent sender only: it intentionally exposes no coordinates or location UI. */
export function useLiveAttendanceLocation(active: boolean) {
  const watchId = useRef<number | null>(null);
  const retryId = useRef<number | null>(null);
  const lastAttemptAt = useRef(0);
  const lastStatusAt = useRef(0);
  const stopped = useRef(true);
  const stop = useCallback(() => {
    stopped.current = true;
    if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
    if (retryId.current !== null) window.clearInterval(retryId.current);
    watchId.current = null; retryId.current = null; lastAttemptAt.current = 0; lastStatusAt.current = 0;
  }, []);
  const start = useCallback(() => {
    stop();
    if (!navigator.geolocation) return;
    stopped.current = false;
    const report = (status: "permission_denied" | "position_unavailable" | "timeout" | "missing_coordinates") => {
      if (stopped.current || Date.now() - lastStatusAt.current < SEND_INTERVAL_MS) return;
      lastStatusAt.current = Date.now();
      void api.reportLiveLocationStatus(status).catch(() => undefined);
    };
    const send = (position: GeolocationPosition) => {
      if (stopped.current || Date.now() - lastAttemptAt.current < SEND_INTERVAL_MS) return;
      const { latitude, longitude, accuracy } = position.coords;
      if (![latitude, longitude, accuracy].every(Number.isFinite)) { report("missing_coordinates"); return; }
      lastAttemptAt.current = Date.now();
      void api.submitLiveLocation({ latitude, longitude, accuracy }).catch(() => undefined);
    };
    const onError = (error: GeolocationPositionError) => {
      report(error.code === error.PERMISSION_DENIED ? "permission_denied" : error.code === error.TIMEOUT ? "timeout" : "position_unavailable");
    };
    const request = () => {
      if (stopped.current) return;
      navigator.geolocation.getCurrentPosition(send, onError, { enableHighAccuracy: false, maximumAge: 30_000, timeout: 15_000 });
    };
    request();
    watchId.current = navigator.geolocation.watchPosition(send, onError, { enableHighAccuracy: false, maximumAge: 30_000, timeout: 15_000 });
    // Browser policies decide whether a denied permission may be prompted again.
    retryId.current = window.setInterval(request, PERMISSION_RETRY_MS);
  }, [stop]);
  useEffect(() => { if (active) start(); else stop(); return stop; }, [active, start, stop]);
  return { start, stop };
}
