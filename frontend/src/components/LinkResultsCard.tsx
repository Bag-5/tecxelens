"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  pollLinkStatus,
  submitLinks,
  type LinkScanResult,
  type LinkVerdictEntry,
} from "@/lib/api";
import DownloadReportButton from "@/components/DownloadReportButton";

const VERDICT_STYLES: Record<string, string> = {
  malicious:
    "bg-red-100 text-red-800 ring-red-700/30 dark:bg-red-500/20 dark:text-red-200 dark:ring-red-400/40",
  suspicious:
    "bg-orange-100 text-orange-700 ring-orange-600/20 dark:bg-orange-500/15 dark:text-orange-300 dark:ring-orange-500/30",
  harmless:
    "bg-green-100 text-green-700 ring-green-600/20 dark:bg-green-500/15 dark:text-green-300 dark:ring-green-500/30",
  unknown:
    "bg-amber-100 text-amber-800 ring-amber-600/25 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-500/30",
  not_scanned:
    "bg-gray-100 text-gray-600 ring-gray-500/20 dark:bg-gray-500/15 dark:text-gray-400 dark:ring-gray-400/30",
};

function verdictBadge(verdict: string) {
  return (
    VERDICT_STYLES[verdict] ??
    "bg-gray-100 text-gray-700 ring-gray-500/20 dark:bg-gray-500/15 dark:text-gray-300 dark:ring-gray-500/30"
  );
}

function label(verdict: string) {
  return verdict.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/** Strips the scheme and any trailing slash so long URLs stay scannable. */
function prettyUrl(url: string) {
  return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
}

function formatDate(unixSeconds: number) {
  if (!unixSeconds) return null;
  return new Date(unixSeconds * 1000).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function LinkRow({ link }: { link: LinkVerdictEntry }) {
  const analysed = formatDate(link.last_analysis_date);
  const categories = Object.values(link.categories ?? {});

  return (
    <li className="rounded-xl border border-gray-200 dark:border-white/8 bg-white dark:bg-white/[0.03] px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {link.permalink ? (
            <a
              href={link.permalink}
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex items-start gap-1.5 min-w-0"
            >
              <span className="font-mono text-xs sm:text-sm break-all text-gray-800 dark:text-gray-200 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                {prettyUrl(link.url)}
              </span>
              <svg
                className="w-3 h-3 mt-0.5 shrink-0 text-gray-400 group-hover:text-indigo-500"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                />
              </svg>
            </a>
          ) : (
            <span className="font-mono text-xs sm:text-sm break-all text-gray-800 dark:text-gray-200">
              {prettyUrl(link.url)}
            </span>
          )}
          {analysed && (
            <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
              Last analysed {analysed}
            </p>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${verdictBadge(
            link.verdict
          )}`}
        >
          {label(link.verdict)}
        </span>
      </div>

      {link.source === "lookup" && (
        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
          <span>
            <span className="font-semibold text-red-600 dark:text-red-400">
              {link.malicious}
            </span>{" "}
            malicious
          </span>
          <span>
            <span className="font-semibold text-orange-600 dark:text-orange-400">
              {link.suspicious}
            </span>{" "}
            suspicious
          </span>
          <span>
            <span className="font-semibold text-green-600 dark:text-green-400">
              {link.harmless}
            </span>{" "}
            harmless
          </span>
          {link.reputation !== 0 && <span>reputation {link.reputation}</span>}
        </div>
      )}

      {link.source === "filtered" && (
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Withheld as a private or internal address — never sent to VirusTotal.
        </p>
      )}

      {link.source === "queued" && (
        <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
          No existing VirusTotal record. Unchecked is not the same as safe.
        </p>
      )}

      {categories.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {[...new Set(categories)].slice(0, 6).map((c) => (
            <span
              key={c}
              className="rounded-md bg-gray-100 dark:bg-white/[0.07] px-2 py-0.5 text-[11px] text-gray-600 dark:text-gray-300"
            >
              {c}
            </span>
          ))}
        </div>
      )}
    </li>
  );
}

interface Props {
  result: LinkScanResult;
}

export default function LinkResultsCard({ result }: Props) {
  const [links, setLinks] = useState<LinkVerdictEntry[]>(result.links);
  const [polling, setPolling] = useState(false);
  const [statusNote, setStatusNote] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scored = useMemo(
    () => links.filter((l) => l.source !== "filtered"),
    [links]
  );
  const flagged = useMemo(
    () => links.filter((l) => l.severity !== "none" && l.verdict !== "unknown"),
    [links]
  );
  const unknown = useMemo(
    () => links.filter((l) => l.verdict === "unknown"),
    [links]
  );
  const withheld = result.filtered_count;

  useEffect(() => {
    setLinks(result.links);
  }, [result.links]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    []
  );

  const runScan = useCallback(async () => {
    if (polling) return;
    setPolling(true);
    setStatusNote("Requesting analysis…");
    const submitted = await submitLinks(unknown.map((l) => l.url));
    if (!submitted.success) {
      setStatusNote(submitted.error);
      setPolling(false);
      return;
    }
    if (submitted.data.granted === 0) {
      setStatusNote(
        submitted.data.reason === "rate_limited"
          ? "VirusTotal's submission quota is full right now. Try again in a minute or two."
          : "Nothing needed submitting — those links are already known to VirusTotal."
      );
      setPolling(false);
      return;
    }
    setStatusNote(
      `Queued ${submitted.data.granted} link${submitted.data.granted === 1 ? "" : "s"} for fresh analysis. VirusTotal usually takes a few minutes.`
    );
    timer.current = setTimeout(async () => {
      const status = await pollLinkStatus(unknown.map((l) => l.url));
      setPolling(false);
      if (!status.success) {
        setStatusNote(status.error);
        return;
      }
      setLinks((prev) =>
        prev.map((p) => status.data.links.find((n) => n.url === p.url) ?? p)
      );
      const stillUnknown = status.data.links.filter((l) => l.verdict === "unknown").length;
      setStatusNote(
        stillUnknown === 0
          ? "Analysis complete — verdicts below are now final."
          : `${stillUnknown} still pending. Check again in a few minutes.`
      );
    }, 5000);
  }, [polling, unknown]);

  return (
    <div className="space-y-6">
      {/* Score */}
      <div className="rounded-2xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/[0.03] p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
              Link Risk Score
            </p>
            <p className="mt-1 text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white tabular-nums">
              {result.overall_score}
              <span className="text-lg font-medium text-gray-400 dark:text-gray-500">
                /100
              </span>
            </p>
            <p className="mt-1 text-sm font-medium text-gray-600 dark:text-gray-300">
              {result.risk_level}
            </p>
          </div>
          <DownloadReportButton
            fileId={result.file_id}
            filename="link_risk_report.pdf"
          />
        </div>

        <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Links", value: links.length },
            { label: "Checked", value: scored.length },
            { label: "Flagged", value: flagged.length, warn: flagged.length > 0 },
            { label: "Withheld", value: withheld },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-xl bg-gray-50 dark:bg-white/[0.04] px-3 py-2.5"
            >
              <p className="text-xs text-gray-500 dark:text-gray-400">{s.label}</p>
              <p
                className={`text-xl font-bold tabular-nums ${
                  s.warn
                    ? "text-red-600 dark:text-red-400"
                    : "text-gray-900 dark:text-white"
                }`}
              >
                {s.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      {result.quota_exhausted && (
        <div className="rounded-xl border border-amber-500/25 bg-amber-50 dark:bg-amber-500/[0.08] px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          VirusTotal&apos;s rate limit was reached, so some links could not be
          checked. They are reported as unchecked rather than clean — re-run the
          scan in a minute to complete them.
        </div>
      )}

      {result.truncated_count > 0 && (
        <div className="rounded-xl border border-amber-500/25 bg-amber-50 dark:bg-amber-500/[0.08] px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          {result.truncated_count} link{result.truncated_count === 1 ? "" : "s"} past
          the per-scan limit were not processed. Split the list to scan them all.
        </div>
      )}

      {withheld > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/[0.03] px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
          {withheld} link{withheld === 1 ? " was" : "s were"} withheld as private or
          internal addresses and never sent to VirusTotal. That is a privacy
          safeguard, not a clean bill of health.
        </div>
      )}

      {/* Summary */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
          Summary
        </h2>
        <p className="mt-2 text-sm sm:text-base leading-relaxed text-gray-700 dark:text-gray-300">
          {result.summary}
        </p>
      </div>

      {/* Findings */}
      {result.findings.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
            Flagged Links
          </h2>
          <div className="mt-3 space-y-3">
            {result.findings.map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="rounded-xl border border-red-500/20 bg-red-50/60 dark:bg-red-500/[0.07] px-4 py-3"
              >
                <p className="text-sm font-semibold text-gray-900 dark:text-white">
                  {f.title}
                </p>
                <p className="mt-1.5 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                  {f.description}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                  <span className="font-semibold">Recommendation: </span>
                  {f.recommendation}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Unknown / submit */}
      {unknown.length > 0 && (
        <div className="rounded-xl border border-amber-500/25 bg-amber-50/60 dark:bg-amber-500/[0.07] px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                {unknown.length} link{unknown.length === 1 ? "" : "s"} not yet known to
                VirusTotal
              </p>
              <p className="mt-0.5 text-xs text-amber-800/80 dark:text-amber-300/80">
                Submitting adds {unknown.length} public URL
                {unknown.length === 1 ? "" : "s"} to VirusTotal&apos;s shared dataset.
              </p>
            </div>
            <button
              onClick={runScan}
              disabled={polling}
              className="shrink-0 inline-flex items-center gap-2 rounded-full bg-amber-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {polling && (
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {polling ? "Working…" : "Check these now"}
            </button>
          </div>
          {statusNote && (
            <p className="mt-2.5 text-xs text-amber-900/80 dark:text-amber-200/80">
              {statusNote}
            </p>
          )}
        </div>
      )}

      {/* Full table */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
          Scanned Links
        </h2>
        <ul className="mt-3 space-y-2.5">
          {links.map((link) => (
            <LinkRow key={link.url} link={link} />
          ))}
        </ul>
      </div>
    </div>
  );
}