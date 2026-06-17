"use client";

import { motion } from "framer-motion";
import { ConvergenceGraphic } from "@/components/ConvergenceGraphic";

const BOOT_METRICS = [
  { key: "RUN MODE", value: "AUTONOMOUS" },
  { key: "VALIDATION", value: "PROOF-FIRST" },
  { key: "ORCHESTRATION", value: "SELF-GOVERNED" },
];

export function HeroSection() {
  return (
    <section className="relative flex min-h-[82vh] flex-col items-center justify-start overflow-hidden px-6 pb-0 pt-2 md:pt-3">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_90%_80%_at_50%_20%,rgba(99,102,241,0.16),transparent_58%),radial-gradient(ellipse_70%_50%_at_50%_105%,rgba(139,92,246,0.12),transparent_70%)]" />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgba(24,24,27,0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgba(24,24,27,0.05)_1px,transparent_1px)] bg-[size:46px_46px] dark:bg-[linear-gradient(to_right,rgba(244,244,245,0.06)_1px,transparent_1px),linear-gradient(to_bottom,rgba(244,244,245,0.05)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_72%_62%_at_50%_45%,#000_30%,transparent_100%)]" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
        className="relative z-10 mt-1 flex w-full max-w-6xl flex-col items-center text-center md:mt-2"
      >
        <div className="hud-label mb-6 inline-flex items-center gap-3 rounded-full px-4 py-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 trace-glow" />
          AUTONOMOUS EXPERIMENT FACTORY
        </div>

        <h1 className="mb-3 bg-gradient-to-b from-indigo-500 via-indigo-600 to-violet-700 bg-clip-text text-[8vw] font-bold leading-none tracking-[-0.04em] text-transparent sm:text-[84px]">
          AETHER
        </h1>

        <h2 className="mb-4 max-w-4xl text-2xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-100 md:text-4xl px-4">
          Autonomous evaluation suite for agents.
        </h2>

        <p className="mb-8 max-w-2xl text-base leading-relaxed text-zinc-800 dark:text-zinc-300 md:text-lg px-6">
          Aether runs agent variants automatically, groups repeated failures, and promotes only runs that are stable and clearly verifiable.
        </p>

        <div className="mb-7 grid w-full max-w-4xl gap-3 sm:grid-cols-3">
          {BOOT_METRICS.map((metric) => (
            <div key={metric.key} className="hud-panel hud-bracket relative rounded-xl px-4 py-3 text-left">
              <div className="text-xs font-mono font-semibold tracking-[0.16em] text-zinc-600 dark:text-zinc-300">{metric.key}</div>
              <div className="mt-1 text-base font-mono font-semibold tracking-[0.06em] text-zinc-900 dark:text-zinc-100">{metric.value}</div>
            </div>
          ))}
        </div>

        <motion.button
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
          className="rounded-md border border-indigo-500/50 bg-indigo-600 px-8 py-3 font-mono text-sm font-semibold tracking-[0.14em] text-white transition-colors hover:bg-indigo-500"
        >
          REQUEST EARLY ACCESS
        </motion.button>
      </motion.div>

      <ConvergenceGraphic />
    </section>
  );
}
