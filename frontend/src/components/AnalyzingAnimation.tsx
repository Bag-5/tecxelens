"use client";

export default function AnalyzingAnimation({ phase }: { phase: "uploading" | "analyzing" }) {
  const label = phase === "uploading" ? "Uploading" : "Scanning";

  return (
    <div className="relative flex flex-col items-center justify-center py-10 sm:py-12 md:py-16">
      {/* 3D torus rings */}
      <div className="relative w-32 h-32 sm:w-40 sm:h-40 md:w-48 md:h-48 perspective-[800px]">
        {/* Outer ring */}
        <div className="absolute inset-0 animate-rotate3d">
          <div className="w-full h-full rounded-full border-2 border-indigo-500/60 shadow-[0_0_12px_rgba(99,102,241,0.25)] sm:shadow-[0_0_20px_rgba(99,102,241,0.3)]" />
        </div>
        {/* Middle ring — counter-rotating */}
        <div className="absolute inset-2 animate-rotate3d-reverse">
          <div className="w-full h-full rounded-full border-2 border-cyan-400/50 shadow-[0_0_12px_rgba(34,211,238,0.2)] sm:shadow-[0_0_20px_rgba(34,211,238,0.25)]" />
        </div>
        {/* Inner ring */}
        <div className="absolute inset-4 animate-rotate3d-slow">
          <div className="w-full h-full rounded-full border border-violet-400/40 shadow-[0_0_10px_rgba(167,139,250,0.16)] sm:shadow-[0_0_15px_rgba(167,139,250,0.2)]" />
        </div>

        {/* Scan line sweep */}
        <div className="absolute inset-0 animate-scan-line">
          <div className="w-full h-0.5 sm:h-1 bg-gradient-to-r from-transparent via-indigo-400 to-transparent blur-[1px] sm:blur-sm" />
        </div>

        {/* Center glow */}
        <div className="absolute inset-[30%] animate-pulse-glow">
          <div className="w-full h-full rounded-full bg-indigo-500/20 blur-lg sm:blur-xl" />
        </div>
      </div>

      {/* Label */}
      <div className="mt-8 sm:mt-10 flex items-center gap-3">
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500" />
        </span>
        <span className="text-sm sm:text-lg font-mono text-gray-400 tracking-widest uppercase">
          {label}
          <span className="animate-dots">...</span>
        </span>
      </div>
    </div>
  );
}
