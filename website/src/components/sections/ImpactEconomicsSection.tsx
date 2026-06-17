"use client";

import { motion } from "framer-motion";

const FAILURE_LOG = [
  { t: "00:12", msg: "syntax_invalid", status: "FAIL" },
  { t: "00:17", msg: "auto_retry=true", status: "WARN" },
  { t: "00:33", msg: "loop_detected", status: "FAIL" },
  { t: "01:42", msg: "budget_guard_missing", status: "FAIL" },
];

const GOVERNED_LOG = [
  { t: "00:12", msg: "syntax_invalid", status: "WARN" },
  { t: "00:13", msg: "remediation_patch_applied", status: "PASS" },
  { t: "00:19", msg: "checkpoint_restored", status: "PASS" },
  { t: "00:24", msg: "trace_stable", status: "PASS" },
];

function statusClass(status: "PASS" | "WARN" | "FAIL") {
  if (status === "PASS") return "telemetry-pass";
  if (status === "WARN") return "telemetry-warn";
  return "telemetry-fail";
}

export function ImpactEconomicsSection() {
  return (
    <section className="relative border-b border-zinc-200 bg-white px-6 py-28 dark:border-zinc-900 dark:bg-black">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_85%_80%_at_50%_0%,rgba(99,102,241,0.12),transparent_58%)]" />

      <div className="mx-auto mb-16 flex max-w-6xl flex-col items-center text-center">
        <div className="hud-label mb-6 inline-flex items-center gap-2 rounded-full px-4 py-1.5">
          IMPACT ECONOMICS
        </div>
        <h2 className="mb-5 text-4xl font-medium tracking-tight text-zinc-950 dark:text-zinc-100 md:text-5xl">
          What an unlocked trace costs.
        </h2>
        <p className="max-w-3xl text-lg leading-relaxed text-zinc-700 dark:text-zinc-300">
          Same task. Same model. Different harness governance. One path burns tokens in retry spirals; the other uses bounded
          remediation and terminates on defensible evidence.
        </p>
      </div>

      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-2">
        <motion.article
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-10%" }}
          className="hud-panel hud-bracket relative rounded-2xl p-6"
        >
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-sm font-mono font-semibold tracking-[0.14em] text-zinc-600 dark:text-zinc-300">MODE A</div>
              <h3 className="mt-1 text-xl font-mono text-zinc-900 dark:text-zinc-100">NAKED AGENT</h3>
            </div>
            <span className="rounded border border-rose-400/40 px-2 py-1 text-sm font-mono font-semibold tracking-[0.1em] telemetry-fail">UNBOUNDED</span>
          </div>

          <div className="mb-5 grid grid-cols-3 gap-2 text-center">
            <div className="rounded border border-zinc-200 px-2 py-2 dark:border-zinc-800">
              <div className="text-sm font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">STEPS</div>
              <div className="mt-1 font-mono text-lg telemetry-fail">405</div>
            </div>
            <div className="rounded border border-zinc-200 px-2 py-2 dark:border-zinc-800">
              <div className="text-sm font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">TOKEN LOSS</div>
              <div className="mt-1 font-mono text-lg telemetry-fail">1.4M</div>
            </div>
            <div className="rounded border border-zinc-200 px-2 py-2 dark:border-zinc-800">
              <div className="text-sm font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">SAFE STOP</div>
              <div className="mt-1 font-mono text-lg telemetry-fail">MISSING</div>
            </div>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-zinc-950/95 p-4 text-sm dark:border-zinc-800">
            <div className="mb-3 font-mono font-semibold tracking-[0.12em] text-zinc-400">EVENT LOG</div>
            <div className="space-y-2 font-mono text-zinc-300">
              {FAILURE_LOG.map((row) => (
                <div key={`${row.t}-${row.msg}`} className="flex items-center justify-between border-b border-zinc-800/60 pb-2 last:border-b-0 last:pb-0">
                  <span className="text-zinc-400">{row.t}</span>
                  <span>{row.msg}</span>
                  <span className={statusClass(row.status as "PASS" | "WARN" | "FAIL")}>{row.status}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.article>

        <motion.article
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-10%" }}
          transition={{ delay: 0.1 }}
          className="hud-panel hud-bracket relative rounded-2xl p-6"
        >
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-sm font-mono font-semibold tracking-[0.14em] text-zinc-600 dark:text-zinc-300">MODE B</div>
              <h3 className="mt-1 text-xl font-mono text-zinc-900 dark:text-zinc-100">AETHER-GOVERNED</h3>
            </div>
            <span className="rounded border border-emerald-400/40 px-2 py-1 text-sm font-mono font-semibold tracking-[0.1em] telemetry-pass">BOUNDED</span>
          </div>

          <div className="mb-5 grid grid-cols-3 gap-2 text-center">
            <div className="rounded border border-zinc-200 px-2 py-2 dark:border-zinc-800">
              <div className="text-sm font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">STEPS</div>
              <div className="mt-1 font-mono text-lg telemetry-pass">13</div>
            </div>
            <div className="rounded border border-zinc-200 px-2 py-2 dark:border-zinc-800">
              <div className="text-sm font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">TOKENS</div>
              <div className="mt-1 font-mono text-lg telemetry-pass">4,120</div>
            </div>
            <div className="rounded border border-zinc-200 px-2 py-2 dark:border-zinc-800">
              <div className="text-sm font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">SAFE STOP</div>
              <div className="mt-1 font-mono text-lg telemetry-pass">PROVEN</div>
            </div>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-zinc-950/95 p-4 text-sm dark:border-zinc-800">
            <div className="mb-3 font-mono font-semibold tracking-[0.12em] text-zinc-400">EVENT LOG</div>
            <div className="space-y-2 font-mono text-zinc-300">
              {GOVERNED_LOG.map((row) => (
                <div key={`${row.t}-${row.msg}`} className="flex items-center justify-between border-b border-zinc-800/60 pb-2 last:border-b-0 last:pb-0">
                  <span className="text-zinc-400">{row.t}</span>
                  <span>{row.msg}</span>
                  <span className={statusClass(row.status as "PASS" | "WARN" | "FAIL")}>{row.status}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.article>
      </div>
    </section>
  );
}
