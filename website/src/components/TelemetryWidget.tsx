"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Terminal } from "lucide-react";

const TRACE_LOGS = [
  '{ "run_id": "eval_0942", "status": "running", "variant": "sc_b_01" }',
  '{ "event": "tool_call", "tool": "raw_bash", "payload": "ls -la" }',
  '{ "event": "checkpoint", "state": "saved", "tokens": 402 }',
  '{ "event": "failure", "cluster": "recovery_loop_or_retry_spiral" }',
  '{ "event": "halt", "reason": "budget_exhaustion", "token_burn": 15400 }',
  '{ "decision": "hold", "reason": "unstable_trajectory" }',
  '{ "run_id": "eval_0943", "status": "running", "variant": "dag_route_v2" }',
  '{ "event": "tool_call", "tool": "structured_dispatch", "payload": "valid" }',
  '{ "event": "checkpoint", "state": "saved", "tokens": 512 }',
  '{ "event": "success", "cluster": null }',
  '{ "decision": "promote", " Uplift": "+14%" }'
];

export function TelemetryWidget({ className = "" }: { className?: string }) {
  const [logs, setLogs] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setLogs((prev) => {
        const newLogs = [...prev, TRACE_LOGS[currentIndex]];
        if (newLogs.length > 5) return newLogs.slice(1);
        return newLogs;
      });
      setCurrentIndex((prev) => (prev + 1) % TRACE_LOGS.length);
    }, 1200);

    return () => clearInterval(interval);
  }, [currentIndex]);

  return (
    <div className={`rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-black/50 backdrop-blur-xl shadow-2xl overflow-hidden font-mono text-sm ${className}`}>
      <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900">
        <Terminal className="w-4 h-4 text-zinc-500" />
        <span className="text-zinc-600 dark:text-zinc-300 font-semibold">run_events.jsonl</span>
        <div className="ml-auto flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
        </div>
      </div>
      <div className="p-4 flex flex-col gap-2 min-h-[160px] justify-end">
        {logs.map((log, i) => (
          <motion.div
            key={`${i}-${log}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className={`whitespace-pre-wrap word-break 
              ${log.includes('"failure"') || log.includes('"hold"') ? 'text-red-600 dark:text-red-400' : 
                log.includes('"promote"') || log.includes('"success"') ? 'text-green-600 dark:text-green-400' : 
                'text-zinc-600 dark:text-zinc-300'}`}
          >
            {log}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
