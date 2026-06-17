"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

export function Header() {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between border-b border-zinc-200 bg-white/85 px-6 py-3 dark:border-zinc-800 dark:bg-zinc-950/85 backdrop-blur-md">
      <div className="flex items-center gap-2 font-mono text-base font-semibold tracking-wide text-zinc-950 dark:text-white">
        <div className="w-5 h-5 bg-black dark:bg-white rounded flex items-center justify-center">
          <div className="w-2 h-2 bg-white dark:bg-black rounded-sm" />
        </div>
        AETHER
      </div>

      <nav className="hidden md:flex gap-6 text-[15px] font-semibold text-zinc-600 dark:text-zinc-300">
        <a href="#problem" className="hover:text-black dark:hover:text-white transition-colors">Philosophy</a>
        <a href="#capabilities" className="hover:text-black dark:hover:text-white transition-colors">Capabilities</a>
        <a href="#architecture" className="hover:text-black dark:hover:text-white transition-colors">Architecture</a>
        <a href="#use-cases" className="hover:text-black dark:hover:text-white transition-colors">Use Cases</a>
      </nav>

      <div className="flex items-center gap-4">
        {resolvedTheme && (
          <button
            onClick={() => setTheme(isDark ? "light" : "dark")}
            className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors text-zinc-600 dark:text-zinc-400"
            aria-label="Toggle theme"
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        )}
        <button className="rounded-full bg-black px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200">
          Join Waitlist
        </button>
      </div>
    </header>
  );
}
