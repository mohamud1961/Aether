"use client";

import { motion } from "framer-motion";

export function ProblemSection() {
  return (
    <section id="problem" className="relative min-h-screen py-32 px-6 flex items-center justify-center bg-zinc-50 dark:bg-black border-y border-zinc-200 dark:border-zinc-900">
      <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent,rgba(0,0,0,0.02),transparent)] dark:bg-[linear-gradient(to_bottom,transparent,rgba(255,255,255,0.02),transparent)] -z-10" />
      
      <div className="max-w-5xl w-full grid md:grid-cols-2 gap-16 items-center">
        <motion.div 
          initial={{ opacity: 0, x: -50 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: "-20%" }}
          transition={{ duration: 0.8 }}
        >
          <h2 className="text-3xl md:text-5xl font-medium tracking-tight text-black dark:text-white mb-6">
            Intelligence is a commodity. <br />
            <span className="text-zinc-500 mt-2 block">Orchestration is a craft.</span>
          </h2>
          <div className="space-y-6 text-zinc-600 dark:text-zinc-400 font-light text-lg">
            <p>
              Underlying foundation models are incredibly capable, yet autonomous agents frequently fail in production. Why? Because the harness surrounding the model lacks robustness.
            </p>
            <p>
              Failure is rarely an intelligence issue—it is an orchestration failure. Context windows degrade, execution paths diverge, and unrecoverable states trap the agent.
            </p>
            <p className="text-black dark:text-zinc-200 font-normal">
              Aether changes the paradigm from prompt engineering to harness engineering.
            </p>
          </div>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, margin: "-20%" }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="relative h-[400px] rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex pl-8 pt-8 overflow-hidden shadow-xl dark:shadow-none"
        >
          <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.03)_1px,transparent_1px)] dark:bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_10%,transparent_100%)]" />
          
          <div className="relative z-10 w-full h-full flex flex-col gap-4">
            <div className="flex gap-2">
              <div className="w-3 h-3 rounded-full bg-red-100 dark:bg-red-500/20 border border-red-500 flex items-center justify-center">
                <div className="w-1 h-1 rounded-full bg-red-500" />
              </div>
              <span className="text-xs font-mono text-zinc-500 mt-[1px]">State: Unrecoverable</span>
            </div>
            
            <div className="mt-4 space-y-4 font-mono text-sm">
              <div className="flex text-zinc-500 dark:text-zinc-600">
                <span className="w-8 shrink-0 text-zinc-400 dark:text-zinc-700">01</span>
                <span>Initialize Context Pool... OK</span>
              </div>
              <div className="flex text-zinc-500 dark:text-zinc-600">
                <span className="w-8 shrink-0 text-zinc-400 dark:text-zinc-700">02</span>
                <span>Execute Step 4 / 20... OK</span>
              </div>
              <div className="flex text-amber-600 dark:text-zinc-300">
                <span className="w-8 shrink-0 text-zinc-400 dark:text-zinc-700">03</span>
                <span>Observation Parse Error... Retrying</span>
              </div>
              <div className="flex text-red-600 dark:text-red-400">
                <span className="w-8 shrink-0 text-zinc-400 dark:text-zinc-700">04</span>
                <span>FATAL: Context Eviction Threshold Reached.</span>
              </div>
              <div className="flex text-red-600/50 dark:text-red-400/50">
                <span className="w-8 shrink-0 text-zinc-400 dark:text-zinc-700">05</span>
                <span>Halt. Agent trapped in hallucinated loop.</span>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
