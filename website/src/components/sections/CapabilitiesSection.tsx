"use client";

import { motion } from "framer-motion";
import { Activity, Beaker, Rocket } from "lucide-react";

export function CapabilitiesSection() {
  const capabilities = [
    {
      icon: <Activity className="h-5 w-5" />,
      title: "Observe & Trace",
      description: "Structured run timelines expose state transitions, branch decisions, and safe-stop evidence.",
      features: ["Durable event telemetry", "Branch/state instrumentation", "Run-to-run comparability"],
    },
    {
      icon: <Beaker className="h-5 w-5" />,
      title: "Evaluate & Score",
      description: "Replay captured traces as deterministic evals and validate contender stability before promotion.",
      features: ["Trajectory-based eval suites", "Failure-mode labeling", "Human adjudication hooks"],
    },
    {
      icon: <Rocket className="h-5 w-5" />,
      title: "Promote With Guardrails",
      description: "Only variants with uplift plus bounded recovery behavior move toward production.",
      features: ["Promotion gates", "Rollback checkpoints", "Controlled rollout policies"],
    },
  ];

  return (
    <section id="capabilities" className="border-b border-zinc-200 bg-white px-6 py-28 dark:border-zinc-900 dark:bg-black">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 max-w-3xl">
          <div className="hud-label mb-5 inline-flex rounded-full px-4 py-1.5">CAPABILITIES</div>
          <h2 className="mb-5 text-4xl font-medium tracking-tight text-zinc-950 dark:text-zinc-100 md:text-5xl">Technical control over autonomous execution.</h2>
          <p className="text-lg text-zinc-700 dark:text-zinc-300">Aether is the proving layer for harness behavior, not a generic chat-agent framework.</p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {capabilities.map((cap, i) => (
            <motion.article
              key={cap.title}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ delay: i * 0.08 }}
              className="hud-panel hud-bracket relative rounded-2xl p-6"
            >
              <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-md border border-indigo-500/35 bg-indigo-500/10 text-indigo-500 dark:text-indigo-300">
                {cap.icon}
              </div>
              <h3 className="mb-3 font-mono text-xl text-zinc-900 dark:text-zinc-100">{cap.title}</h3>
              <p className="mb-5 text-base font-medium leading-relaxed text-zinc-800 dark:text-zinc-200">{cap.description}</p>
              <ul className="space-y-2 text-base font-mono font-semibold tracking-[0.03em] text-zinc-800 dark:text-zinc-200">
                {cap.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2">
                    <span className="h-1 w-1 rounded-full bg-indigo-400" />
                    {feature}
                  </li>
                ))}
              </ul>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}
