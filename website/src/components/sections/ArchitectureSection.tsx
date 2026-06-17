"use client";

import { motion } from "framer-motion";

const ARCHITECTURE_LAYERS = [
  {
    level: "01",
    title: "Atomic",
    subtitle: "Contract Guards & Probes",
    description: "Foundational checks that establish truthful execution boundaries.",
    subLevels: [
      "Lifecycle & safe-stop guard",
      "Workspace/path correctness",
      "Interruption & cleanup probe",
      "Result normalization",
    ],
  },
  {
    level: "02",
    title: "Memory",
    subtitle: "Context Engineering",
    description: "Context retention and eviction policy tested across long trajectories.",
    subLevels: ["Working memory integrity", "Context eviction", "Semantic drift monitoring"],
  },
  {
    level: "03",
    title: "Executive",
    subtitle: "Control Logic",
    description: "Planning, dead-end recognition, and bounded recovery for reliable autonomy.",
    subLevels: ["DAG routing & planning", "Dead-end recognition", "Autonomous recovery"],
  },
] as const;

export function ArchitectureSection() {
  return (
    <section id="architecture" className="relative border-y border-zinc-200 bg-white py-24 dark:border-zinc-900 dark:bg-black">
      <div className="mx-auto mb-14 max-w-7xl px-6 md:text-center">
        <div className="hud-label mb-5 inline-flex rounded-full px-4 py-1.5">MEASUREMENT STACK</div>
        <h2 className="mb-5 text-4xl font-medium tracking-tight text-zinc-950 dark:text-zinc-100 md:text-6xl">
          One layer at a time.
        </h2>
        <p className="mx-auto max-w-3xl text-lg text-zinc-700 dark:text-zinc-300">
          Move from Atomic to Executive. Each stage must pass before the next stage leads.
        </p>
      </div>

      <div className="mx-auto max-w-7xl space-y-16 px-6 md:space-y-20">
        {ARCHITECTURE_LAYERS.map((layer, index) => (
          <motion.div
            key={layer.level}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-18%" }}
            transition={{ duration: 0.45 }}
            className="grid gap-6 md:grid-cols-12 md:gap-8"
          >
            <article className="hud-panel rounded-2xl p-6 md:col-span-5 md:sticky md:top-24 md:self-start">
              <div className="mb-3 text-base font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">
                LEVEL {layer.level}
              </div>
              <h3 className="text-3xl font-mono text-zinc-900 dark:text-zinc-100">{layer.title}</h3>
              <p className="mb-4 text-lg font-mono font-semibold tracking-[0.06em] text-zinc-700 dark:text-zinc-300">
                {layer.subtitle}
              </p>
              <p className="text-base leading-relaxed text-zinc-700 dark:text-zinc-300">{layer.description}</p>

              <div className="mt-6 flex gap-2">
                {ARCHITECTURE_LAYERS.map((step, idx) => (
                  <span
                    key={step.level}
                    className={`h-1.5 rounded-full transition-all ${
                      idx === index ? "w-10 bg-indigo-500" : "w-4 bg-zinc-300 dark:bg-zinc-700"
                    }`}
                  />
                ))}
              </div>
            </article>

            <article className="hud-panel rounded-2xl p-6 md:col-span-7">
              <div className="mb-4 text-base font-mono font-semibold tracking-[0.1em] text-zinc-700 dark:text-zinc-200">
                ACTIVE CONTROLS
              </div>
              <ul className="grid gap-3 sm:grid-cols-2">
                {layer.subLevels.map((item) => (
                  <li
                    key={item}
                    className="rounded border border-zinc-200 px-3 py-3 text-base font-mono font-semibold tracking-[0.03em] text-zinc-800 dark:border-zinc-800 dark:text-zinc-200"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </article>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
