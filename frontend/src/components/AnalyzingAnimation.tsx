"use client";

import { useEffect, useRef } from "react";

interface Dot {
  x: number;
  y: number;
  vx: number;
  vy: number;
  alpha: number;
  size: number;
}

export default function AnalyzingAnimation({ phase }: { phase: "uploading" | "analyzing" }) {
  const label = phase === "uploading" ? "Uploading" : "Scanning";
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let dots: Dot[] = [];
    const radius = 72;
    const cx = 96;
    const cy = 96;

    for (let i = 0; i < 12; i++) {
      const angle = Math.random() * Math.PI * 2;
      const r = radius + 8 + Math.random() * 20;
      dots.push({
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        alpha: 0.2 + Math.random() * 0.4,
        size: 1.5 + Math.random() * 2,
      });
    }

    function animate() {
      ctx!.clearRect(0, 0, 192, 192);

      for (const d of dots) {
        const dx = d.x - cx;
        const dy = d.y - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > radius + 35 || dist < radius - 10) {
          const angle = Math.atan2(dy, dx);
          const r = radius + 12 + Math.random() * 18;
          d.x = cx + Math.cos(angle) * r;
          d.y = cy + Math.sin(angle) * r;
        }
        d.x += d.vx;
        d.y += d.vy;
        d.alpha += (Math.random() - 0.5) * 0.02;
        d.alpha = Math.max(0.1, Math.min(0.6, d.alpha));

        ctx!.save();
        ctx!.globalAlpha = d.alpha;
        ctx!.fillStyle = "#818cf8";
        ctx!.beginPath();
        ctx!.arc(d.x, d.y, d.size, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.restore();
      }

      animId = requestAnimationFrame(animate);
    }

    animate();
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative flex flex-col items-center justify-center py-10 sm:py-12 md:py-16">
      <div className="relative w-32 h-32 sm:w-40 sm:h-40 md:w-48 md:h-48 perspective-[800px]">
        <canvas
          ref={canvasRef}
          width={192}
          height={192}
          className="absolute inset-0 w-full h-full pointer-events-none z-10"
          aria-hidden="true"
        />

        <div className="absolute inset-0 animate-rotate3d">
          <div className="w-full h-full rounded-full border-2 border-indigo-500/60 shadow-[0_0_12px_rgba(99,102,241,0.25)] sm:shadow-[0_0_20px_rgba(99,102,241,0.3)]" />
        </div>
        <div className="absolute inset-2 animate-rotate3d-reverse">
          <div className="w-full h-full rounded-full border-2 border-cyan-400/50 shadow-[0_0_12px_rgba(34,211,238,0.2)] sm:shadow-[0_0_20px_rgba(34,211,238,0.25)]" />
        </div>
        <div className="absolute inset-4 animate-rotate3d-slow">
          <div className="w-full h-full rounded-full border border-violet-400/40 shadow-[0_0_10px_rgba(167,139,250,0.16)] sm:shadow-[0_0_15px_rgba(167,139,250,0.2)]" />
        </div>

        <div className="absolute inset-0 animate-scan-line pointer-events-none z-20">
          <div className="w-full h-0.5 sm:h-1 bg-gradient-to-r from-transparent via-indigo-400 to-transparent blur-[1px] sm:blur-sm" />
        </div>

        <div className="absolute inset-[30%] animate-pulse-glow">
          <div className="w-full h-full rounded-full bg-indigo-500/20 blur-lg sm:blur-xl" />
        </div>
      </div>

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
