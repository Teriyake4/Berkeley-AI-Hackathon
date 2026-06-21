"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Speaker } from "@/types/events";

type Mode = "idle" | "deepgram" | "webspeech";

interface DeepgramWord {
  speaker?: number;
  word: string;
}

interface DeepgramResult {
  type: string;
  is_final: boolean;
  channel?: {
    alternatives?: Array<{
      transcript: string;
      words?: DeepgramWord[];
    }>;
  };
}

export function LiveMic({
  active,
  onTranscript,
}: {
  active: boolean;
  onTranscript: (text: string, speaker: Speaker) => void;
}) {
  const [listening, setListening] = useState(false);
  const [mode, setMode] = useState<Mode>("idle");
  const [error, setError] = useState<string | null>(null);
  // Maps Deepgram speaker index → our speaker label. Can be toggled during demo.
  const [speakerMap, setSpeakerMap] = useState<Record<number, Speaker>>({ 0: "paramedic", 1: "patient" });

  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  const stopAll = useCallback(() => {
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.close();
    }
    recognitionRef.current?.stop();
    recorderRef.current = null;
    streamRef.current = null;
    socketRef.current = null;
    recognitionRef.current = null;
    setListening(false);
    setMode("idle");
  }, []);

  // Stop when parent deactivates
  useEffect(() => {
    if (!active && listening) stopAll();
  }, [active, listening, stopAll]);

  // ── Deepgram path ──────────────────────────────────────────────────────────

  const startDeepgram = useCallback(async (key: string) => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone permission denied.");
      return;
    }
    streamRef.current = stream;

    const params = new URLSearchParams({
      model: "nova-2",
      smart_format: "true",
      diarize: "true",
      punctuate: "true",
      interim_results: "false",
      language: "en-US",
    });

    const socket = new WebSocket(
      `wss://api.deepgram.com/v1/listen?${params}`,
      ["token", key]
    );
    socketRef.current = socket;

    socket.onopen = () => {
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && socket.readyState === WebSocket.OPEN) {
          socket.send(e.data);
        }
      };

      recorder.start(250); // 250ms chunks for low-latency
      setListening(true);
      setMode("deepgram");
      setError(null);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as DeepgramResult;
        if (data.type !== "Results" || !data.is_final) return;

        const alt = data.channel?.alternatives?.[0];
        if (!alt?.transcript?.trim()) return;

        // Determine speaker from first word's diarization index
        const speakerIndex = alt.words?.[0]?.speaker ?? 0;
        const speaker = speakerMap[speakerIndex] ?? "unknown";

        onTranscript(alt.transcript.trim(), speaker);
      } catch {
        /* ignore parse errors */
      }
    };

    socket.onerror = () => {
      setError("Deepgram connection error. Falling back to Web Speech.");
      stopAll();
      startWebSpeech();
    };

    socket.onclose = () => {
      if (listening) setError("Deepgram disconnected.");
      setListening(false);
      setMode("idle");
    };
  }, [listening, onTranscript, speakerMap, stopAll]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Web Speech fallback ────────────────────────────────────────────────────

  const startWebSpeech = useCallback(() => {
    const SR = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SR) {
      setError("Web Speech API not supported. Try Chrome.");
      return;
    }

    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognitionRef.current = recognition;

    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      const last = event.results[event.results.length - 1];
      if (last.isFinal) {
        const text = last[0].transcript.trim();
        if (text) onTranscript(text, "unknown");
      }
    };

    recognition.onerror = () => setError("Web Speech recognition error.");
    recognition.onend = () => {
      if (listening) recognition.start(); // auto-restart
    };

    recognition.start();
    setListening(true);
    setMode("webspeech");
    setError(null);
  }, [listening, onTranscript]);

  // ── Start: try Deepgram, fall back to Web Speech ───────────────────────────

  const start = useCallback(async () => {
    setError(null);

    try {
      const res = await fetch("/api/deepgram");
      if (res.ok) {
        const { key } = await res.json() as { key?: string };
        if (key) {
          await startDeepgram(key);
          return;
        }
      }
    } catch {
      /* Deepgram endpoint unavailable — fall through */
    }

    startWebSpeech();
  }, [startDeepgram, startWebSpeech]);

  const swapSpeakers = useCallback(() => {
    setSpeakerMap((prev) => ({
      ...prev,
      0: prev[0] === "paramedic" ? "patient" : "paramedic",
      1: prev[1] === "patient" ? "paramedic" : "patient",
    }));
  }, []);

  if (!active) return null;

  return (
    <div className="flex items-center gap-3">
      {!listening ? (
        <button
          onClick={start}
          className="flex items-center gap-2 rounded-lg bg-signal-500 px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-transform hover:-translate-y-0.5"
        >
          <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
          Start Mic
        </button>
      ) : (
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 font-mono text-[11px] font-medium text-vitals-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-vitals-400" />
            {mode === "deepgram" ? "Deepgram" : "Web Speech"}
          </span>
          {mode === "deepgram" && (
            <button
              onClick={swapSpeakers}
              title="Swap doctor / patient speaker assignment"
              className="rounded-md border border-[var(--line-strong)] px-2 py-1 text-xs text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-white"
            >
              Swap speakers
            </button>
          )}
          <button
            onClick={stopAll}
            className="rounded-lg border border-[var(--line-strong)] px-3 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-white"
          >
            Stop
          </button>
        </div>
      )}
      {error && <span className="font-mono text-xs text-signal-300">{error}</span>}
    </div>
  );
}

type SpeechRecognitionCtor = new () => {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
};

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

interface SpeechRecognitionEventLike {
  results: SpeechRecognitionResultLike[];
}

declare global {
  interface Window {
    SpeechRecognition: SpeechRecognitionCtor;
    webkitSpeechRecognition: SpeechRecognitionCtor;
  }
}
