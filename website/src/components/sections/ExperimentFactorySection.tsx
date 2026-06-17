"use client";

import { motion } from "framer-motion";
import { TelemetryWidget } from "@/components/TelemetryWidget";
import { CheckCircle, Database, GitMerge, ServerCog } from "lucide-react";

export function ExperimentFactorySection() {
  return (
    <section className="relative overflow-hidden border-b border-zinc-200 bg-zinc-50 px-6 py-28 dark:border-zinc-900 dark:bg-zinc-950/40">
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(rgba(24,24,27,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(24,24,27,0.04)_1px,transparent_1px)] bg-[size:34px_34px] dark:bg-[linear-gradient(rgba(244,244,245,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(244,244,245,0.03)_1px,transparent_1px)]" />

      <div className="mx-auto flex max-w-6xl flex-col items-center gap-14 lg:flex-row">
        <div className="lg:w-1/2">
          <div className="hud-label mb-7 inline-flex items-center gap-2 rounded-full px-4 py-1.5">
            <ServerCog className="h-3 w-3" />
            FACTORY LOOP
          </div>

          <h2 className="mb-6 text-4xl font-medium tracking-tight text-zinc-950 dark:text-zinc-100 md:text-5xl">
            Continuous promotion for harness contenders.
          </h2>
          <p className="mb-8 text-lg leading-relaxed text-zinc-700 dark:text-zinc-300">
            Aether executes contender variants head-to-head, clusters failure trajectories, and escalates only candidates with
            stable uplift and bounded recovery behavior.
          </p>

          <div className="space-y-5">
            <div className="hud-panel rounded-xl p-4">
              <h4 className="mb-2 flex items-center gap-2 font-mono text-base font-semibold tracking-[0.06em] text-zinc-900 dark:text-zinc-100">
                <Database className="h-4 w-4" />
                01 BATCHED EXECUTION
              </h4>
              <p className="text-base font-medium text-zinc-700 dark:text-zinc-300">Variants run under identical TerminalBench constraints and budget caps.</p>
            </div>
            <div className="hud-panel rounded-xl p-4">
              <h4 className="mb-2 flex items-center gap-2 font-mono text-base font-semibold tracking-[0.06em] text-zinc-900 dark:text-zinc-100">
                <GitMerge className="h-4 w-4" />
                02 FAILURE CLUSTERING
              </h4>
              <p className="text-base font-medium text-zinc-700 dark:text-zinc-300">Each trajectory is grouped into explicit operational classes, not anecdotal summaries.</p>
            </div>
            <div className="hud-panel rounded-xl p-4">
              <h4 className="mb-2 flex items-center gap-2 font-mono text-base font-semibold tracking-[0.06em] text-zinc-900 dark:text-zinc-100">
                <CheckCircle className="h-4 w-4" />
                03 MATHEMATICAL PROMOTION
              </h4>
              <p className="text-base font-medium text-zinc-700 dark:text-zinc-300">Promotion requires measured uplift plus recovery and safe-stop evidence.</p>
            </div>
          </div>
        </div>

        <div className="relative w-full lg:w-1/2">
          <motion.div initial={{ opacity: 0, scale: 0.97 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}>
            <TelemetryWidget className="absolute -bottom-11 -right-4 z-20 w-full md:w-[390px]" />

            <div className="hud-panel relative z-10 rounded-2xl p-6">
              <div className="mb-5 flex justify-between text-sm font-mono font-semibold tracking-[0.12em] text-zinc-600 dark:text-zinc-300">
                <span>CONTENDER PASS RATES</span>
                <span className="telemetry-pass">PROMOTABLE</span>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="mb-1 flex justify-between text-sm font-mono font-semibold">
                    <span className="text-zinc-900 dark:text-zinc-100">sc_b_01 baseline</span>
                    <span className="text-zinc-700 dark:text-zinc-300">22%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-900">
                    <motion.div className="h-full bg-zinc-500" initial={{ width: 0 }} whileInView={{ width: "22%" }} transition={{ duration: 0.7 }} />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex justify-between text-sm font-mono font-semibold">
                    <span className="text-zinc-900 dark:text-zinc-100">vf_pc_02 layered_logic</span>
                    <span className="telemetry-warn">41%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-900">
                    <motion.div className="h-full bg-amber-400" initial={{ width: 0 }} whileInView={{ width: "41%" }} transition={{ duration: 0.8, delay: 0.1 }} />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex justify-between text-sm font-mono font-semibold">
                    <span className="text-zinc-900 dark:text-zinc-100">dag_route_v2 apex</span>
                    <span className="telemetry-pass">78%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-900">
                    <motion.div className="h-full bg-emerald-400" initial={{ width: 0 }} whileInView={{ width: "78%" }} transition={{ duration: 0.9, delay: 0.2 }} />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
