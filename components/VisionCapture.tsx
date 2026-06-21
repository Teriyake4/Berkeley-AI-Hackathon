"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// --- Tunables -------------------------------------------------------------
const BASELINE_INTERVAL_MS = 4000; // fallback capture cadence
const MOTION_SAMPLE_MS = 200; // ~5 motion samples / sec
const DIFF_W = 64; // downscaled diff resolution
const DIFF_H = 48;
const MOTION_THRESHOLD = 12; // mean abs pixel diff considered "moving"
const STILL_THRESHOLD = 5; // below this is "still"
const SUSTAINED_HOLD_MS = 3000; // steady this long → start re-capturing
const SUSTAINED_RECAPTURE_MS = 2000; // re-capture cadence while held steady
const MIN_POST_INTERVAL_MS = 1500; // hard floor between actual POSTs

type Status = "idle" | "monitoring" | "scanning";

interface VisionItem {
  identified: string;
  captureType: string;
  timestamp: string;
}

export function VisionCapture({
  active = true,
  readOnly = false,
  encounterId = "",
  visionItems = [],
}: {
  active?: boolean;
  readOnly?: boolean;
  encounterId?: string;
  visionItems?: VisionItem[];
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const diffCanvasRef = useRef<HTMLCanvasElement>(null);

  const [status, setStatus] = useState<Status>("idle");
  const [streaming, setStreaming] = useState(false);
  const [cameraError, setCameraError] = useState(false);

  // Mutable refs that must not trigger re-renders.
  const streamRef = useRef<MediaStream | null>(null);
  const mountedRef = useRef(true);
  const inFlightRef = useRef(false);
  const lastPostRef = useRef(0);

  // Motion tracking state (refs to avoid re-renders on every sample).
  const prevPixelsRef = useRef<Uint8ClampedArray | null>(null);
  const wasMovingRef = useRef(false);
  const steadySinceRef = useRef<number | null>(null);
  const lastSustainedRef = useRef(0);

  // Timer handles.
  const baselineTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const motionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const setStatusSafe = useCallback((s: Status) => {
    if (mountedRef.current) setStatus(s);
  }, []);

  // --- Capture + POST -----------------------------------------------------
  const captureAndSend = useCallback(async () => {
    if (!mountedRef.current) return;
    if (inFlightRef.current) return; // never more than one in flight
    if (!streamRef.current) return;

    const now = Date.now();
    if (now - lastPostRef.current < MIN_POST_INTERVAL_MS) return; // throttle

    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = 640;
    canvas.height = 480;
    ctx.drawImage(video, 0, 0, 640, 480);

    let dataUrl: string;
    try {
      dataUrl = canvas.toDataURL("image/jpeg", 0.7);
    } catch {
      return; // tainted canvas or other draw failure — bail silently
    }
    const frame_base64 = dataUrl.replace(/^data:image\/jpeg;base64,/, "");

    if (!encounterId) return;

    inFlightRef.current = true;
    lastPostRef.current = now;
    setStatusSafe("scanning");

    try {
      await fetch("/api/vision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ frame_base64, encounterId }),
      });
    } catch {
      // Swallow — the vision.captured event comes back over SSE elsewhere.
    } finally {
      inFlightRef.current = false;
      if (mountedRef.current) {
        // Brief "Sent" feel by returning to monitoring.
        setStatusSafe(streamRef.current ? "monitoring" : "idle");
      }
    }
  }, [encounterId, setStatusSafe]);

  // --- Motion detection sample -------------------------------------------
  const sampleMotion = useCallback(() => {
    if (!mountedRef.current || !streamRef.current) return;
    const video = videoRef.current;
    const diffCanvas = diffCanvasRef.current;
    if (!video || !diffCanvas || video.readyState < 2) return;

    const ctx = diffCanvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    diffCanvas.width = DIFF_W;
    diffCanvas.height = DIFF_H;
    ctx.drawImage(video, 0, 0, DIFF_W, DIFF_H);

    let frame: ImageData;
    try {
      frame = ctx.getImageData(0, 0, DIFF_W, DIFF_H);
    } catch {
      return;
    }
    const cur = frame.data;
    const prev = prevPixelsRef.current;

    if (prev && prev.length === cur.length) {
      let total = 0;
      // Sample luminance-ish (just R channel) every 4th byte to stay cheap.
      let count = 0;
      for (let i = 0; i < cur.length; i += 4) {
        total += Math.abs(cur[i] - prev[i]);
        count++;
      }
      const meanDiff = count > 0 ? total / count : 0;
      const now = Date.now();

      if (meanDiff > MOTION_THRESHOLD) {
        // Currently moving.
        wasMovingRef.current = true;
        steadySinceRef.current = null;
      } else if (meanDiff < STILL_THRESHOLD) {
        // Currently still.
        if (wasMovingRef.current) {
          // "Was moving then went still" transition → primary trigger.
          wasMovingRef.current = false;
          steadySinceRef.current = now;
          lastSustainedRef.current = now;
          void captureAndSend();
        } else if (steadySinceRef.current !== null) {
          // Sustained hold: re-capture on cadence while it stays steady.
          if (
            now - steadySinceRef.current >= SUSTAINED_HOLD_MS &&
            now - lastSustainedRef.current >= SUSTAINED_RECAPTURE_MS
          ) {
            lastSustainedRef.current = now;
            void captureAndSend();
          }
        }
      }
      // Intermediate (between thresholds): hold current state, no action.
    }

    // Store a copy for next comparison.
    prevPixelsRef.current = new Uint8ClampedArray(cur);
  }, [captureAndSend]);

  // --- Lifecycle ----------------------------------------------------------
  // Track true mount/unmount independently of the active toggle.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!active || readOnly) {
      setStreaming(false);
      setStatusSafe("idle");
      return;
    }

    let cancelled = false;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment", width: 640, height: 480 },
          audio: false,
        });
        if (cancelled || !mountedRef.current) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setCameraError(false);
        setStreaming(true);
        setStatusSafe("monitoring");

        baselineTimerRef.current = setInterval(() => {
          void captureAndSend();
        }, BASELINE_INTERVAL_MS);

        motionTimerRef.current = setInterval(() => {
          sampleMotion();
        }, MOTION_SAMPLE_MS);
      } catch {
        if (!mountedRef.current) return;
        setCameraError(true);
        setStreaming(false);
        setStatusSafe("idle");
      }
    };

    void start();

    return () => {
      cancelled = true;
      if (baselineTimerRef.current) clearInterval(baselineTimerRef.current);
      if (motionTimerRef.current) clearInterval(motionTimerRef.current);
      baselineTimerRef.current = null;
      motionTimerRef.current = null;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (videoRef.current) videoRef.current.srcObject = null;
      prevPixelsRef.current = null;
      wasMovingRef.current = false;
      steadySinceRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, readOnly]);

  if (readOnly) {
    return (
      <div className="flex h-full flex-col">
        <h2 className="panel-label mb-3">Vision Captures</h2>
        <div className="flex-1 space-y-2 overflow-y-auto">
          {visionItems.length === 0 && (
            <p className="font-mono text-sm text-[var(--text-faint)]">
              No vision captures in this session.
            </p>
          )}
          {visionItems.map((item, i) => (
            <div
              key={`${item.timestamp}-${i}`}
              className="rounded-lg border border-vitals-400/25 bg-vitals-400/[0.08] p-3 text-sm"
            >
              <span className="font-medium text-vitals-400">{item.identified}</span>
              <span className="ml-2 font-mono text-xs capitalize text-[var(--text-faint)]">
                ({item.captureType})
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="panel-label">Live Camera Feed</h2>
        {active && streaming && (
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-[var(--text-muted)]">
            <span
              className={`inline-block h-2 w-2 animate-pulse rounded-full ${
                status === "scanning" ? "bg-clinical-400" : "bg-vitals-400"
              }`}
            />
            {status === "scanning" ? "Scanning…" : "Monitoring"}
          </span>
        )}
      </div>

      <div className="relative h-40 w-full overflow-hidden rounded-xl border border-[var(--line)] bg-ink-950 sm:h-48">
        {!cameraError ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center px-4 text-center">
            <p className="font-mono text-xs text-[var(--text-faint)]">
              Camera unavailable — demo runs from the injector
            </p>
          </div>
        )}
        {active && streaming && status === "scanning" && (
          <div className="ecg-scanner pointer-events-none absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-transparent via-clinical-400/25 to-transparent" />
        )}
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="text-xs leading-tight text-[var(--text-faint)]">
          Demo uses laptop camera. In the field: chest- or helmet-mounted body cam.
        </p>
        {active && streaming && (
          <button
            type="button"
            onClick={() => void captureAndSend()}
            className="shrink-0 rounded-md border border-[var(--line-strong)] px-2 py-1 text-xs font-medium text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-white"
          >
            Capture now
          </button>
        )}
      </div>

      {/* Hidden working canvases. */}
      <canvas ref={canvasRef} className="hidden" />
      <canvas ref={diffCanvasRef} className="hidden" />
    </div>
  );
}
