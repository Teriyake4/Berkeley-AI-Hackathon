import Link from "next/link";
import { NosMark } from "@/components/NosMark";

const AGENTS = [
  {
    n: "01",
    name: "Transcription",
    accent: "text-clinical-300",
    dot: "bg-clinical-400",
    desc: "Live speech-to-text with paramedic / patient speaker labels.",
  },
  {
    n: "02",
    name: "Extraction",
    accent: "text-clinical-300",
    dot: "bg-clinical-400",
    desc: "Pulls allergies, medications, conditions, and symptoms the moment they're spoken.",
  },
  {
    n: "03",
    name: "Timeline",
    accent: "text-clinical-300",
    dot: "bg-clinical-400",
    desc: "Assembles a GPS-anchored narrative of the entire call.",
  },
  {
    n: "04",
    name: "Safety",
    accent: "text-signal-300",
    dot: "bg-signal-400",
    desc: "Flags missed follow-ups, drug interactions, and NREMT gaps — from stated facts only.",
  },
  {
    n: "05",
    name: "Research",
    accent: "text-clinical-300",
    dot: "bg-clinical-400",
    desc: "Looks up drug interactions and clinical protocols against live sources.",
  },
  {
    n: "06",
    name: "Handoff",
    accent: "text-vitals-400",
    dot: "bg-vitals-400",
    desc: "Generates the structured ED report — the money shot — in one tap.",
  },
];

const FLOW = [
  { k: "Scene arrival", v: "Mic and camera go live the moment you reach the patient." },
  { k: "Live capture", v: "Speech, vitals, telemetry, and what the camera sees merge into one picture." },
  { k: "Real-time safety", v: "Six agents cross-check every stated fact as the call unfolds." },
  { k: "Handoff", v: "One tap turns a messy scene into a clean report for the receiving ED." },
];

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-ink-900 text-[var(--text)]">
      {/* Atmosphere */}
      <div className="pointer-events-none absolute inset-0 bg-aurora" />
      <div className="pointer-events-none absolute inset-0 bg-grid [mask-image:radial-gradient(80%_60%_at_50%_0%,black,transparent)]" />

      {/* ── Nav ─────────────────────────────────────────────────────── */}
      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Link href="/" className="flex items-center gap-2.5">
          <NosMark size={30} />
          <span className="font-display text-xl font-extrabold tracking-tight">Nos</span>
        </Link>
        <nav className="flex items-center gap-2 text-sm">
          <Link
            href="/logs"
            className="rounded-lg px-3.5 py-2 font-medium text-[var(--text-muted)] transition-colors hover:text-white"
          >
            Sessions
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg bg-signal-500 px-4 py-2 font-semibold text-white shadow-glow transition-transform hover:-translate-y-0.5"
          >
            Open console
          </Link>
        </nav>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-10 pt-12 sm:pt-20">
        <p className="animate-rise panel-label flex items-center gap-2" style={{ animationDelay: "0ms" }}>
          <span className="inline-block h-1.5 w-1.5 animate-glow-pulse rounded-full bg-signal-500" />
          Real-time clinical copilot · EMS
        </p>

        <h1
          className="animate-rise mt-5 max-w-4xl font-display text-5xl font-extrabold leading-[0.98] tracking-tight sm:text-7xl"
          style={{ animationDelay: "80ms" }}
        >
          Nothing gets lost
          <br />
          between the{" "}
          <span className="bg-gradient-to-r from-signal-400 to-signal-600 bg-clip-text text-transparent">
            scene
          </span>{" "}
          and the{" "}
          <span className="bg-gradient-to-r from-clinical-300 to-clinical-500 bg-clip-text text-transparent">
            ED
          </span>
          .
        </h1>

        <p
          className="animate-rise mt-6 max-w-2xl text-lg leading-relaxed text-[var(--text-muted)]"
          style={{ animationDelay: "160ms" }}
        >
          Nos is a real-time AI teammate for paramedics. It listens to the scene, watches
          the patient, builds a live clinical picture, flags safety risks the instant they
          appear, and hands the emergency department a complete, structured report.
        </p>

        <div
          className="animate-rise mt-9 flex flex-wrap items-center gap-3"
          style={{ animationDelay: "240ms" }}
        >
          <Link
            href="/dashboard"
            className="group inline-flex items-center gap-2 rounded-xl bg-signal-500 px-6 py-3.5 font-semibold text-white shadow-glow transition-transform hover:-translate-y-0.5"
          >
            Open the console
            <span className="transition-transform group-hover:translate-x-0.5">→</span>
          </Link>
          <Link
            href="/logs"
            className="inline-flex items-center gap-2 rounded-xl border border-[var(--line-strong)] px-6 py-3.5 font-semibold text-[var(--text)] transition-colors hover:bg-white/5"
          >
            Replay a session
          </Link>
        </div>

        {/* ECG hero strip */}
        <div
          className="animate-rise relative mt-14 overflow-hidden rounded-2xl border border-[var(--line)] bg-ink-850/70 backdrop-blur"
          style={{ animationDelay: "320ms" }}
        >
          <div className="flex items-center justify-between border-b border-[var(--line)] px-5 py-3">
            <span className="panel-label">Encounter · live monitor</span>
            <span className="flex items-center gap-2 font-mono text-xs text-vitals-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-vitals-400" />
              SINUS RHYTHM
            </span>
          </div>
          <div className="relative h-36 sm:h-44">
            <svg
              viewBox="0 0 1200 200"
              preserveAspectRatio="none"
              className="h-full w-full"
            >
              <path
                d="M0 100 H180 l20 0 l14 -54 l22 108 l18 -120 l16 130 l14 -64 H520 l16 0 l14 -50 l22 100 l18 -110 l16 120 l14 -60 H980 l20 0 l14 -40 l18 70 l16 -30 H1200"
                fill="none"
                stroke="#ff4536"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="ecg-trace"
              />
            </svg>
            <div className="ecg-scanner pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-transparent via-clinical-400/15 to-transparent" />
          </div>
        </div>
      </section>

      {/* ── Mission ─────────────────────────────────────────────────── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-20">
        <div className="grid gap-12 md:grid-cols-[0.85fr_1.15fr] md:items-start">
          <div>
            <p className="panel-label">Why we built this</p>
            <h2 className="mt-3 font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
              Critical detail, spoken once, gone by the hospital doors.
            </h2>
          </div>
          <div className="space-y-5 text-lg leading-relaxed text-[var(--text-muted)]">
            <p>
              Paramedics make life-or-death calls while doing ten things at once. An
              allergy mentioned at the door, a blood thinner buried in the history, the
              exact minute chest pain started — said aloud, then lost in the rush of the
              transport.
            </p>
            <p>
              <span className="font-semibold text-white">Our mission is simple:</span>{" "}
              capture everything that is said and seen on scene, reason over it in real
              time with a team of specialized agents, and deliver the receiving ED a
              perfect handoff — so no detail dies in the back of an ambulance.
            </p>
          </div>
        </div>
      </section>

      {/* ── Agent workforce ─────────────────────────────────────────── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-12">
        <div className="flex items-end justify-between gap-6">
          <div>
            <p className="panel-label">A collaborative AI workforce</p>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight sm:text-4xl">
              Six specialists, one shift.
            </h2>
          </div>
          <p className="hidden max-w-xs text-sm text-[var(--text-faint)] sm:block">
            Each agent reacts to clinical events on a shared bus — no orchestrator, no
            bottleneck.
          </p>
        </div>

        <div className="mt-9 grid gap-px overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--line)] sm:grid-cols-2 lg:grid-cols-3">
          {AGENTS.map((a) => (
            <div
              key={a.n}
              className="group relative bg-ink-850 p-6 transition-colors hover:bg-ink-800"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs tracking-widest text-[var(--text-faint)]">
                  {a.n}
                </span>
                <span className={`h-2 w-2 rounded-full ${a.dot} shadow-[0_0_10px_2px_currentColor] ${a.accent}`} />
              </div>
              <h3 className={`mt-4 font-display text-lg font-bold ${a.accent}`}>{a.name}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">{a.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Flow ────────────────────────────────────────────────────── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-16">
        <p className="panel-label">From scene to handoff</p>
        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FLOW.map((s, i) => (
            <div key={s.k} className="relative rounded-2xl border border-[var(--line)] bg-ink-850 p-5">
              <span className="font-mono text-xs text-clinical-400">0{i + 1}</span>
              <h3 className="mt-2 font-display text-base font-bold text-white">{s.k}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-muted)]">{s.v}</p>
              {i < FLOW.length - 1 && (
                <span className="absolute -right-2 top-1/2 hidden -translate-y-1/2 text-[var(--text-faint)] lg:block">
                  →
                </span>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── Safety principle ────────────────────────────────────────── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-12">
        <div className="relative overflow-hidden rounded-3xl border border-signal-500/25 bg-gradient-to-br from-signal-500/10 via-ink-850 to-ink-850 p-8 sm:p-12">
          <div className="absolute -right-10 -top-10 h-44 w-44 rounded-full bg-signal-500/10 blur-3xl" />
          <p className="panel-label text-signal-300">Defensible by design</p>
          <h2 className="mt-3 max-w-3xl font-display text-2xl font-bold leading-snug tracking-tight sm:text-3xl">
            Nos only flags what was actually said, written on a label, or seen by the
            camera — never an inference from age alone.
          </h2>
          <div className="mt-7 grid gap-4 sm:grid-cols-3">
            {[
              { t: "Missed follow-up", d: "Chest pain at 0:00, not revisited in 3 minutes." },
              { t: "Stated med + context", d: "Warfarin on board with new chest pain." },
              { t: "Vision cross-check", d: "Aspirin vial scanned on a patient already on warfarin." },
            ].map((c) => (
              <div key={c.t} className="rounded-xl border border-[var(--line)] bg-ink-900/60 p-4">
                <h3 className="font-display text-sm font-bold text-white">{c.t}</h3>
                <p className="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────────── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-20 text-center">
        <h2 className="mx-auto max-w-2xl font-display text-3xl font-extrabold tracking-tight sm:text-5xl">
          See the workforce run a call.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-[var(--text-muted)]">
          Launch the console and replay a scripted ambulance scenario — transcript,
          timeline, safety flags, and handoff, all live.
        </p>
        <Link
          href="/dashboard"
          className="mt-8 inline-flex items-center gap-2 rounded-xl bg-signal-500 px-7 py-4 font-semibold text-white shadow-glow transition-transform hover:-translate-y-0.5"
        >
          Open the console →
        </Link>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <footer className="relative z-10 border-t border-[var(--line)] bg-ink-950/60">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-6 py-8 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2.5">
            <NosMark size={24} />
            <span className="font-display font-bold">Nos</span>
            <span className="text-sm text-[var(--text-faint)]">
              · Built at the UC Berkeley AI Hackathon
            </span>
          </div>
          <p className="text-xs text-[var(--text-faint)]">
            Demo only — not for clinical use. Does not provide medical advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
