export function DoctrineSection() {
  return (
    <section className="relative flex flex-col items-center justify-center overflow-hidden border-t border-zinc-800 bg-black px-6 py-24 text-center text-white">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_65%_at_50%_0%,rgba(99,102,241,0.18),transparent_60%)]" />

      <div className="mx-auto max-w-4xl">
        <div className="hud-label mx-auto mb-7 inline-flex rounded-full px-4 py-1.5">AETHER DOCTRINE</div>
        <blockquote className="mb-10 text-2xl font-medium leading-[1.4] tracking-tight md:text-4xl">
          Measurement before contenders. A terminal-first baseline must exist before richer architecture can be trusted.
        </blockquote>
        <div className="flex flex-wrap justify-center gap-4 text-sm font-mono font-semibold tracking-[0.1em] text-zinc-300">
          <span className="rounded border border-zinc-700 px-3 py-1">01 STRICT TELEMETRY</span>
          <span className="rounded border border-zinc-700 px-3 py-1">02 BASELINE FIRST</span>
          <span className="rounded border border-zinc-700 px-3 py-1">03 ZERO BENCHMARK THEATER</span>
        </div>
      </div>
    </section>
  );
}
