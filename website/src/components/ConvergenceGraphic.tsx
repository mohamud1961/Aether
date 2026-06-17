"use client";

import { motion, useReducedMotion, useScroll, useSpring, useTransform } from "framer-motion";
import { useRef } from "react";

const CHANNELS = [
  { label: "ENVIRONMENT", start: [105, 76], mid: [280, 132], status: "WARN", color: "rgb(16 185 129)" },
  { label: "CONTEXT", start: [190, 46], mid: [322, 122], status: "PASS", color: "rgb(250 204 21)" },
  { label: "TOOLS", start: [790, 76], mid: [620, 132], status: "WARN", color: "rgb(244 63 94)" },
  { label: "MEMORY", start: [704, 46], mid: [575, 122], status: "PASS", color: "rgb(168 85 247)" },
];

export function ConvergenceGraphic() {
  const ref = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = useReducedMotion();

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end center"],
  });

  const rawLock = useTransform(scrollYProgress, [0.06, 0.55], [0, 1]);
  const lockProgress = useSpring(rawLock, { stiffness: 140, damping: 28, mass: 0.35 });

  const opacity = useTransform(scrollYProgress, [0, 0.12, 0.95], [0.2, 1, 0.94]);
  const scale = useTransform(scrollYProgress, [0, 0.3], [0.96, 1]);
  const chaoticOpacity = useTransform(lockProgress, [0, 1], [0.85, 0]);
  const stableOpacity = useTransform(lockProgress, [0, 0.5, 1], [0.2, 0.75, 1]);
  const beamWidth = useTransform(lockProgress, [0, 0.7, 1], [7, 4, 2]);
  const traceLength = useTransform(lockProgress, [0.2, 1], [0, 1]);
  const titleOpacity = useTransform(lockProgress, [0.2, 0.75, 1], [0, 0.8, 1]);
  const titleY = useTransform(lockProgress, [0, 1], [8, 0]);

  return (
    <motion.div
      ref={ref}
      style={{ opacity, scale }}
      className="relative mt-0 hidden h-[380px] w-full max-w-[900px] items-center justify-center md:flex mx-auto"
      aria-hidden
    >
      <div className="pointer-events-none absolute inset-0 rounded-[28px] bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.2),transparent_72%)]" />
      <svg viewBox="0 0 900 310" width="100%" height="100%" className="overflow-visible">
        <defs>
          <filter id="loomSoftGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="loomHardGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="traceGradient" x1="450" y1="172" x2="450" y2="300" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="rgb(99 102 241)" stopOpacity="0.95" />
            <stop offset="100%" stopColor="rgb(139 92 246)" stopOpacity="0.35" />
          </linearGradient>
        </defs>

        <g>
          <line x1="98" y1="172" x2="802" y2="172" stroke="rgb(63 63 70)" strokeWidth="1" strokeDasharray="2 8" opacity="0.4" />
          <line x1="98" y1="196" x2="802" y2="196" stroke="rgb(63 63 70)" strokeWidth="1" strokeDasharray="2 8" opacity="0.26" />
        </g>

        {CHANNELS.map((channel, index) => {
          const [startX, startY] = channel.start;
          const [midX, midY] = channel.mid;
          const anchorX = 450;
          const anchorY = 182;
          const chaosPath = `M ${startX} ${startY} C ${startX + (index < 2 ? 38 : -38)} ${midY - 16}, ${midX} ${midY + 14}, ${anchorX} ${anchorY}`;
          const stablePath = `M ${startX} ${startY} C ${startX + (index < 2 ? 82 : -82)} ${midY + 6}, ${midX} ${midY}, ${anchorX} ${anchorY}`;

          return (
            <g key={channel.label}>
              <motion.path
                d={chaosPath}
                stroke={channel.color}
                strokeWidth="1.6"
                strokeDasharray="4 6"
                fill="none"
                style={{ opacity: 0.6 }}
                initial={{ strokeDashoffset: 0 }}
                animate={{ strokeDashoffset: index < 2 ? -20 : 20 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              />

              <motion.path
                d={stablePath}
                stroke={channel.color}
                strokeWidth="2.2"
                fill="none"
                filter="url(#loomHardGlow)"
                style={{ opacity: stableOpacity }}
                initial={{ pathLength: 0 }}
                whileInView={{ pathLength: 1 }}
                viewport={{ once: true, margin: "-5%" }}
                transition={{ duration: prefersReducedMotion ? 0.01 : 1.35, delay: 0.2 + index * 0.1 }}
              />

              <motion.circle
                r="3"
                fill="#FFF"
                filter="url(#loomHardGlow)"
                style={{ opacity: stableOpacity }}
              >
                <animateMotion
                  dur={`${2 + index * 0.5}s`}
                  repeatCount="indefinite"
                  path={stablePath}
                />
              </motion.circle>

              <text
                x={startX + (index < 2 ? -10 : 10)}
                y={startY - 8}
                textAnchor={index < 2 ? "end" : "start"}
                fill={channel.color}
                className="text-xs font-mono font-semibold tracking-[0.14em]"
              >
                {channel.label}
              </text>
              <text
                x={startX + (index < 2 ? -10 : 10)}
                y={startY + 8}
                textAnchor={index < 2 ? "end" : "start"}
                fill={channel.color}
                className="text-[11px] font-mono font-semibold tracking-[0.12em]"
                opacity={0.8}
              >
                {channel.status}
              </text>
            </g>
          );
        })}

        <motion.g style={{ opacity: stableOpacity }}>
          <polygon
            points="432,161 468,161 478,184 468,206 432,206 422,184"
            fill="rgb(99 102 241)"
            opacity="0.2"
            filter="url(#loomHardGlow)"
          />
          <polygon
            points="432,161 468,161 478,184 468,206 432,206 422,184"
            fill="rgb(24 24 27)"
            stroke="rgb(99 102 241)"
            strokeWidth="1.2"
            filter="url(#loomHardGlow)"
          />
          <line x1="450" y1="161" x2="450" y2="206" stroke="rgb(113 113 122)" strokeWidth="1" strokeDasharray="1 4" />
          <text x="450" y="146" textAnchor="middle" className="fill-zinc-700 dark:fill-zinc-200 text-xs font-mono font-semibold tracking-[0.16em]">
            AETHER
          </text>
        </motion.g>

        <motion.path
          d="M450 184 L450 300"
          fill="none"
          stroke="rgb(99 102 241)"
          strokeLinecap="round"
          style={{ opacity: stableOpacity, strokeWidth: beamWidth, pathLength: traceLength }}
          filter="url(#loomSoftGlow)"
        />
        <motion.path
          d="M450 184 L450 300"
          fill="none"
          stroke="url(#traceGradient)"
          strokeLinecap="round"
          style={{ strokeWidth: beamWidth, pathLength: traceLength }}
          filter="url(#loomHardGlow)"
        />
      </svg>
    </motion.div>
  );
}
