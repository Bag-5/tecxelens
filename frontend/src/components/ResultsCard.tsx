"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform, useMotionValue } from "framer-motion";
import { useTilt } from "@/hooks/useTilt";
import type { Finding as FindingType } from "@/lib/api";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

function severityBadge(severity: string) {
  switch (severity) {
    case "critical":
      return "bg-red-100 text-red-800 ring-red-700/30 dark:bg-red-500/20 dark:text-red-200 dark:ring-red-400/40";
    case "high":
      return "bg-orange-100 text-orange-700 ring-orange-600/20 dark:bg-orange-500/15 dark:text-orange-300 dark:ring-orange-500/30";
    case "medium":
      return "bg-yellow-100 text-yellow-700 ring-yellow-600/20 dark:bg-yellow-500/15 dark:text-yellow-300 dark:ring-yellow-500/30";
    case "low":
      return "bg-green-100 text-green-700 ring-green-600/20 dark:bg-green-500/15 dark:text-green-300 dark:ring-green-500/30";
    default:
      return "bg-gray-100 text-gray-700 ring-gray-500/20 dark:bg-gray-500/15 dark:text-gray-300 dark:ring-gray-500/30";
  }
}

function cvssBadge(severity: string) {
  switch (severity) {
    case "CRITICAL": return "bg-red-900/30 text-red-300 ring-red-500/40";
    case "HIGH": return "bg-red-600/20 text-red-300 ring-red-500/30";
    case "MEDIUM": return "bg-yellow-600/20 text-yellow-300 ring-yellow-500/30";
    case "LOW": return "bg-green-600/20 text-green-300 ring-green-500/30";
    default: return "bg-gray-600/20 text-gray-300 ring-gray-500/30";
  }
}

function cvssColor(score: number | null) {
  if (score === null) return "text-gray-400";
  if (score >= 9.0) return "text-red-300";
  if (score >= 7.0) return "text-orange-300";
  if (score >= 4.0) return "text-yellow-300";
  return "text-green-300";
}

const CIRCUMFERENCE = 502;

function ScoreRing({ score, riskLevel }: { score: number; riskLevel: string }) {
  const ref = useRef<SVGCircleElement>(null);

  const meta =
    score >= 90 ? { color: "#22c55e" }
      : score >= 75 ? { color: "#06b6d4" }
        : score >= 50 ? { color: "#eab308" }
          : score >= 25 ? { color: "#f97316" }
            : { color: "#ef4444" };

  useEffect(() => {
    const offset = CIRCUMFERENCE - (score / 100) * CIRCUMFERENCE;
    if (ref.current) ref.current.style.strokeDashoffset = String(offset);
  }, [score]);

  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => Math.round(v));
  const spring = useSpring(count, { stiffness: 60, damping: 20 });

  useEffect(() => {
    spring.set(score);
  }, [score, spring]);

  const [displayScore, setDisplayScore] = useState(0);
  useEffect(() => {
    const unsub = rounded.on("change", setDisplayScore);
    return unsub;
  }, [rounded]);

  return (
    <div className={`flex flex-col items-center transition-all duration-700`}>
      <div className="relative w-32 h-32 sm:w-40 sm:h-40 md:w-48 md:h-48">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 180 180">
          <circle cx="90" cy="90" r="80" fill="none" stroke="currentColor" strokeWidth="6" className="text-gray-200 dark:text-white/5" />
          <circle ref={ref} cx="90" cy="90" r="80" fill="none" stroke={meta.color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE} strokeDashoffset={CIRCUMFERENCE}
            className="transition-all duration-1000 ease-out"
            style={{ filter: `drop-shadow(0 0 8px ${meta.color}66)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 dark:text-white">{displayScore}</span>
          <span className="mt-1 text-xs font-semibold uppercase tracking-widest" style={{ color: meta.color }}>{riskLevel}</span>
        </div>
      </div>
    </div>
  );
}

const findingsStagger = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.15 },
  },
};

const findingItem = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

function TiltCard({ children }: { children: React.ReactNode }) {
  const ref = useTilt<HTMLDivElement>({ maxTilt: 4, scale: 1.01, speed: 300 });
  return (
    <div ref={ref} className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/[0.03] p-4 sm:p-5 shadow-[0_1px_0_rgba(255,255,255,0.02)]">
      {children}
    </div>
  );
}

interface Props {
  overallScore: number;
  riskLevel: string;
  findings: FindingType[];
  summary: string;
}

export default function ResultsCard({ overallScore, riskLevel, findings, summary }: Props) {
  const grouped = SEVERITY_ORDER.reduce<Record<string, FindingType[]>>(
    (acc, s) => { acc[s] = findings.filter((f) => f.severity === s); return acc; }, {}
  );

  return (
    <div className="space-y-8 sm:space-y-10">
      <ScoreRing score={overallScore} riskLevel={riskLevel} />

      <motion.div
        className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4"
        variants={{
          hidden: { opacity: 0 },
          show: { opacity: 1, transition: { staggerChildren: 0.06, delayChildren: 0.1 } },
        }}
        initial="hidden"
        animate="show"
      >
        {[
          { label: "Total Findings", value: findings.length, cl: "text-gray-900 dark:text-white" },
          { label: "Critical", value: grouped.critical?.length || 0, cl: "text-red-700 dark:text-red-300" },
          { label: "High", value: grouped.high?.length || 0, cl: "text-orange-600 dark:text-orange-400" },
          { label: "Medium", value: grouped.medium?.length || 0, cl: "text-yellow-600 dark:text-yellow-400" },
          { label: "Low", value: grouped.low?.length || 0, cl: "text-green-600 dark:text-green-400" },
        ].map((item) => (
          <motion.div
            key={item.label}
            variants={{
              hidden: { opacity: 0, y: 16 },
              show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" as const } },
            }}
            className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/[0.04] p-4 sm:p-5 text-center transition-all duration-300 hover:bg-gray-50 dark:hover:bg-white/[0.07] hover:border-gray-300 dark:hover:border-white/20 hover:scale-[1.02]"
          >
            <p className="text-sm text-gray-500 dark:text-gray-400 uppercase tracking-wide">{item.label}</p>
            <p className={`text-2xl sm:text-3xl font-bold mt-1 ${item.cl}`}>{item.value}</p>
          </motion.div>
        ))}
      </motion.div>

      {findings.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Findings</h2>
          <motion.div
            className="space-y-3 sm:space-y-4"
            variants={findingsStagger}
            initial="hidden"
            animate="show"
          >
            {SEVERITY_ORDER.flatMap((severity) =>
              (grouped[severity] || []).map((f, i) => (
                <motion.div key={`${severity}-${i}`} variants={findingItem}>
                  <TiltCard>
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-3">
                      <h3 className="font-semibold text-gray-900 dark:text-white text-lg sm:text-base leading-tight">{f.title}</h3>
                      <span className={`shrink-0 self-start inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${severityBadge(f.severity)}`}>
                        {f.severity}
                      </span>
                    </div>

                    {f.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 leading-relaxed">{f.description}</p>
                    )}

                    {f.recommendation && (
                      <div className="rounded-lg bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 px-4 py-3 mb-3">
                        <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 mb-1">Recommendation</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{f.recommendation}</p>
                      </div>
                    )}

                    {f.cves && f.cves.length > 0 && (
                      <div className="mb-3">
                        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">Known Vulnerabilities (NVD)</p>
                        <div className="space-y-1.5">
                          {f.cves.map((cve) => (
                            <div key={cve.id} className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-md bg-gray-50 dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 px-3 py-2">
                              <span className={`text-xs font-mono font-bold ${cvssColor(cve.cvss_score)}`}>
                                {cve.cvss_score !== null ? cve.cvss_score.toFixed(1) : "--"}
                              </span>
                              <div className="flex-1 min-w-0">
                                <a
                                  href={`https://nvd.nist.gov/vuln/detail/${cve.id}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs font-mono font-medium text-indigo-600 dark:text-indigo-400 hover:underline truncate block"
                                >
                                  {cve.id}
                                </a>
                                <p className="text-[11px] text-gray-500 dark:text-gray-400 truncate">{cve.description}</p>
                              </div>
                              <span className={`self-start sm:self-auto shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset ${cvssBadge(cve.severity)}`}>
                                {cve.severity}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {f.references && f.references.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {f.references.map((ref, ri) => (
                          <span key={ri} className="inline-flex items-center gap-1 rounded-md border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/[0.04] px-2.5 py-1 text-[11px] text-gray-500 dark:text-gray-400 max-w-full">
                            <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                            </svg>
                            <span className="truncate">
                              {ref.document.split("\\").pop()?.replace(/\.(pdf|pptx|txt)$/i, "")} — {ref.section}
                            </span>
                          </span>
                        ))}
                      </div>
                    )}
                  </TiltCard>
                </motion.div>
              ))
            )}
          </motion.div>
        </div>
      )}

      {summary && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Executive Summary</h2>
            <span className="rounded-full border border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10 px-2.5 py-0.5 text-[10px] font-medium tracking-wider text-indigo-600 dark:text-indigo-300 uppercase">AI</span>
          </div>
          <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/[0.03] p-5 sm:p-6 text-gray-600 dark:text-gray-300 text-sm leading-relaxed transition-all hover:border-gray-300 dark:hover:border-white/20">
            {summary}
          </div>
        </motion.div>
      )}
    </div>
  );
}
