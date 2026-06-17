"use client";

import { motion } from "framer-motion";
import { Code2, Database, Terminal } from "lucide-react";

export function UseCasesSection() {
  const cases = [
    {
      icon: <Terminal className="h-5 w-5" />,
      title: "Workspace & Terminal",
      desc: "Bound command execution and detect unrecoverable CLI loops before they consume budget.",
    },
    {
      icon: <Database className="h-5 w-5" />,
      title: "Deep Research",
      desc: "Stress-test long-horizon context behavior and eviction policy under realistic trace depth.",
    },
    {
      icon: <Code2 className="h-5 w-5" />,
      title: "Code Generation",
      desc: "Enforce write-build-test-recover loops where promotion requires deterministic verification.",
    },
  ];

  return (
    <section id="use-cases" className="relative overflow-hidden bg-zinc-100 px-6 py-28 dark:bg-zinc-950/55">
      <div className="mx-auto max-w-5xl">
        <div className="mb-14 text-center">
          <div className="hud-label mb-5 inline-flex rounded-full px-4 py-1.5">OPERATIONAL DOMAINS</div>
          <h2 className="text-3xl font-medium tracking-tight text-zinc-950 dark:text-zinc-100 md:text-5xl">Designed for brittle, high-cost orchestration.</h2>
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          {cases.map((item, i) => (
            <motion.article
              key={item.title}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ delay: i * 0.08 }}
              className="hud-panel rounded-2xl p-6"
            >
              <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-md border border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-200">
                {item.icon}
              </div>
              <h4 className="mb-3 font-mono text-lg text-zinc-900 dark:text-zinc-100">{item.title}</h4>
              <p className="text-base font-medium leading-relaxed text-zinc-800 dark:text-zinc-200">{item.desc}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}
