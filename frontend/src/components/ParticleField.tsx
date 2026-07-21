"use client";

import { useEffect, useRef } from "react";

const BINARY = ["0", "1"];
const NODE_RADIUS = 3;

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  char: string;
  size: number;
  alpha: number;
  life: number;
  maxLife: number;
}

export default function ParticleField({ count = 20 }: { count?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let nodes: Node[] = [];
    let w = 0;
    let h = 0;

    function resize() {
      w = canvas!.width = window.innerWidth;
      h = canvas!.height = window.innerHeight;
    }

    function spawn() {
      const x = Math.random() * w;
      const y = -10 - Math.random() * 40;
      const maxLife = 500 + Math.random() * 500;
      nodes.push({
        x, y,
        vx: (Math.random() - 0.5) * 0.3,
        vy: 0.15 + Math.random() * 0.25,
        char: BINARY[Math.floor(Math.random() * BINARY.length)],
        size: 10 + Math.random() * 4,
        alpha: 0,
        life: 0,
        maxLife,
      });
    }

    function animate() {
      ctx!.clearRect(0, 0, w, h);

      if (nodes.length < count && Math.random() < 0.08) spawn();

      for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i];
        n.life++;
        n.x += n.vx;
        n.y += n.vy;

        const fadeIn = Math.min(n.life / 100, 1);
        const fadeOut = Math.max(1 - (n.life - n.maxLife + 100) / 100, 0);
        n.alpha = fadeIn * fadeOut;

        if (n.life > n.maxLife || n.y > h + 20) {
          nodes.splice(i, 1);
          continue;
        }

        ctx!.save();
        ctx!.globalAlpha = n.alpha * 0.25;
        ctx!.fillStyle = "#818cf8";
        ctx!.font = `${n.size}px "JetBrains Mono", "Fira Code", monospace`;
        ctx!.textAlign = "center";
        ctx!.textBaseline = "middle";
        ctx!.fillText(n.char, n.x, n.y);
        ctx!.restore();

        ctx!.save();
        ctx!.globalAlpha = n.alpha * 0.15;
        ctx!.fillStyle = "#818cf8";
        ctx!.beginPath();
        ctx!.arc(n.x, n.y + 20, 1.5, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.restore();
      }

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            const alpha = (1 - dist / 150) * 0.08;
            ctx!.save();
            ctx!.globalAlpha = alpha;
            ctx!.strokeStyle = "#818cf8";
            ctx!.lineWidth = 0.5;
            ctx!.beginPath();
            ctx!.moveTo(nodes[i].x, nodes[i].y);
            ctx!.lineTo(nodes[j].x, nodes[j].y);
            ctx!.stroke();
            ctx!.restore();
          }
        }
      }

      animId = requestAnimationFrame(animate);
    }

    resize();
    window.addEventListener("resize", resize);
    for (let i = 0; i < count; i++) spawn();
    animate();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, [count]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      aria-hidden="true"
    />
  );
}
