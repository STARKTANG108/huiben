"use client";

import { useEffect, useRef } from "react";

/**
 * Poll while a pipeline job is running.
 * - Skips when tab hidden
 * - Never overlaps in-flight requests
 * - Does not depend on the whole project object (avoids interval thrash)
 */
export function useJobPoll(
  enabled: boolean,
  refresh: () => Promise<unknown>,
  intervalMs = 3000,
) {
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let inFlight = false;

    const tick = async () => {
      if (cancelled || inFlight) return;
      if (
        typeof document !== "undefined" &&
        document.visibilityState === "hidden"
      ) {
        return;
      }
      inFlight = true;
      try {
        await refreshRef.current();
      } catch {
        /* ignore transient poll errors */
      } finally {
        inFlight = false;
      }
    };

    const t = setInterval(() => {
      void tick();
    }, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [enabled, intervalMs]);
}
