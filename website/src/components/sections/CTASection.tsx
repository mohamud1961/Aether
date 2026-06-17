"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export function CTASection() {
  return (
    <section className="relative flex items-center justify-center overflow-hidden border-t border-zinc-200 bg-white px-6 py-36 dark:border-zinc-900 dark:bg-black">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_70%_at_50%_100%,rgba(99,102,241,0.15),transparent_62%)]" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-10%" }}
        transition={{ duration: 0.6 }}
        className="text-center"
      >
        <div className="hud-label mb-6 inline-flex rounded-full px-4 py-1.5">READY TO RUN CONTENDERS</div>
        <h2 className="mb-6 text-4xl font-medium tracking-tight text-zinc-950 dark:text-zinc-100 md:text-6xl">Prove your harness before it ships.</h2>
        <p className="mb-10 text-lg text-zinc-700 dark:text-zinc-300">Request access to the Aether experiment factory and promotion pipeline.</p>

        <motion.button
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
          className="group inline-flex items-center gap-3 rounded-md border border-indigo-500/50 bg-indigo-600 px-7 py-3 font-mono text-sm font-semibold tracking-[0.12em] text-white hover:bg-indigo-500"
        >
          JOIN WAITLIST
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </motion.button>
      </motion.div>
    </section>
  );
}
