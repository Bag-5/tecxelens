"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useMagnetic } from "@/hooks/useMagnetic";

import UploadBox from "@/components/UploadBox";
import LinkScanBox from "@/components/LinkScanBox";
import AnalyzingAnimation from "@/components/AnalyzingAnimation";
import { parseLinkInput } from "@/lib/parseLinks";
import {
  uploadFile,
  analyzeFile,
  scanLinks,
  fetchLinkCapabilities,
  type ApiResult,
  type LinkCapabilities,
} from "@/lib/api";

type Phase = "idle" | "uploading" | "analyzing" | "scanning" | "done";
type Mode = "document" | "links";

function MagneticAnalyze({ onClick, label }: { onClick: () => void; label: string }) {
  const ref = useMagnetic<HTMLButtonElement>({ strength: 0.2, radius: 160 });

  return (
    <button
      ref={ref}
      onClick={onClick}
      className="w-full rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition-shadow hover:shadow-indigo-500/30"
    >
      {label}
    </button>
  );
}

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1, delayChildren: 0.05 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

const MODES: { id: Mode; label: string; blurb: string }[] = [
  { id: "document", label: "Document", blurb: "PDF, TXT or PPTX" },
  { id: "links", label: "Links", blurb: "URL reputation" },
];

function ModeToggle({
  mode,
  onChange,
  disabled,
  linksEnabled,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
  disabled: boolean;
  linksEnabled: boolean;
}) {
  return (
    <div
      role="tablist"
      aria-label="Scan type"
      className="mx-auto mb-6 inline-flex rounded-xl border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/[0.04] p-1"
    >
      {MODES.map((m) => {
        const active = mode === m.id;
        // Only the Links tab is gated; a failed capability probe leaves it
        // enabled, because hiding a working feature is worse than showing it.
        const unavailable = m.id === "links" && !linksEnabled;
        return (
          <button
            key={m.id}
            role="tab"
            aria-selected={active}
            disabled={disabled || unavailable}
            title={
              unavailable
                ? "Link scanning is not configured on this deployment"
                : undefined
            }
            onClick={() => onChange(m.id)}
            className={`relative rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              active
                ? "bg-white dark:bg-white/10 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            {m.label}
            {unavailable && (
              <span className="ml-1.5 text-[10px] font-normal uppercase tracking-wide opacity-70">
                unavailable
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export default function UploadPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [mode, setMode] = useState<Mode>("document");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [linkInput, setLinkInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [linksAvailable, setLinksAvailable] = useState(true);
  const [capsReason, setCapsReason] = useState<string | null>(null);
  const busy = useRef(false);

  // Ask once whether this deployment can actually look anything up. A failure
  // leaves the tab enabled: we do not know that it is broken, and hiding the
  // feature would be a worse answer than letting the user try it.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const caps: ApiResult<LinkCapabilities> = await fetchLinkCapabilities();
      if (cancelled) return;
      if (caps.success) {
        setLinksAvailable(caps.data.enabled);
        if (!caps.data.enabled) setCapsReason(caps.data.reason);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleFileSelected = (file: File) => {
    setSelectedFile(file);
    setError(null);
  };

  const handleAnalyze = async () => {
    if (!selectedFile || busy.current) return;
    busy.current = true;
    setError(null);

    setPhase("uploading");
    const uploaded = await uploadFile(selectedFile);
    if (!uploaded.success) {
      setError(uploaded.error);
      setPhase("idle");
      busy.current = false;
      return;
    }

    setPhase("analyzing");
    const result = await analyzeFile(uploaded.data.file_id);
    if (!result.success) {
      setError(result.error);
      setPhase("idle");
      busy.current = false;
      return;
    }

    setPhase("done");
    busy.current = false;

    const resultId = crypto.randomUUID();
    try {
      sessionStorage.setItem(`tecxelens-result:${resultId}`, JSON.stringify(result.data));
      sessionStorage.setItem(`tecxelens-file:${resultId}`, uploaded.data.file_id);
    } catch { /* fallback */ }
    router.push(`/results?result=${resultId}`);
  };

  const handleScanLinks = async () => {
    const { urls } = parseLinkInput(linkInput);
    if (urls.length === 0 || busy.current) return;
    busy.current = true;
    setError(null);

    setPhase("scanning");
    const result = await scanLinks(urls);
    if (!result.success) {
      setError(result.error);
      setPhase("idle");
      busy.current = false;
      return;
    }

    setPhase("done");
    busy.current = false;

    // Same storage keys as the document flow: the results page keys off
    // report_type inside the payload, so it decides which card to render.
    const resultId = crypto.randomUUID();
    try {
      sessionStorage.setItem(`tecxelens-result:${resultId}`, JSON.stringify(result.data));
      sessionStorage.setItem(`tecxelens-file:${resultId}`, result.data.file_id);
    } catch { /* fallback */ }
    router.push(`/results?result=${resultId}`);
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    setError(null);
    // Clear the other mode's pending input so a half-typed URL never gets
    // analysed as a document, or a stale filename survives a switch.
    if (m === "document") setLinkInput("");
    else setSelectedFile(null);
  };

  const loading = phase === "uploading" || phase === "analyzing" || phase === "scanning";
  const parsedLinks = parseLinkInput(linkInput);
  const canScanLinks = parsedLinks.urls.length > 0;

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-4 sm:px-6 py-8 sm:py-10 overflow-hidden">
      <motion.div
        className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[500px] rounded-full bg-indigo-500/5 blur-[120px] pointer-events-none"
        animate={{ scale: [1, 1.1, 1], opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        className="relative w-full max-w-2xl"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={fadeUp} className="text-center mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
            {mode === "document" ? "Upload Document" : "Scan Links"}
          </h1>
          <p className="mt-1.5 text-sm sm:text-base text-gray-500 dark:text-gray-400">
            {mode === "document"
              ? "Drop a compliance PDF, TXT, or PPTX to begin analysis"
              : "Paste the links you want reputation-checked"}
          </p>
          <p className="mt-2 text-xs sm:text-sm text-gray-500 dark:text-gray-500">
            {mode === "document"
              ? "Large files or first-time analyses can take a little longer."
              : "Results are scored separately from document compliance."}
          </p>
        </motion.div>

        <ModeToggle
          mode={mode}
          onChange={switchMode}
          disabled={loading}
          linksEnabled={linksAvailable}
        />

        {!linksAvailable && capsReason === "provider_not_configured" && (
          <p className="mb-5 rounded-lg border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/[0.03] px-4 py-3 text-xs leading-relaxed text-gray-500 dark:text-gray-400">
            Link scanning is switched off on this deployment because no reputation
            provider key is configured. Document analysis is unaffected. Set{" "}
            <code className="font-mono text-[11px]">VIRUSTOTAL_API_KEY</code> on the
            backend and this tab will come back on its own.
          </p>
        )}

        {loading ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
          >
            <AnalyzingAnimation phase={phase} />
          </motion.div>
        ) : (
          <motion.div variants={fadeUp}>
            {mode === "document" ? (
              <>
                <UploadBox onFileSelected={handleFileSelected} disabled={loading} />

                {selectedFile && (
                  <motion.div
                    className="mt-5 sm:mt-6 space-y-4"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: "easeOut" }}
                  >
                    <div className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/[0.04] px-4 py-3">
                      <svg className="w-5 h-5 text-indigo-500 dark:text-indigo-400 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                      </svg>
                      <span className="text-sm text-gray-600 dark:text-gray-300 truncate flex-1 min-w-0">{selectedFile.name}</span>
                      <button onClick={() => setSelectedFile(null)} className="text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-white transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>

                    <MagneticAnalyze onClick={handleAnalyze} label="Analyze" />
                  </motion.div>
                )}
              </>
            ) : (
              <motion.div
                className="space-y-4"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: "easeOut" }}
              >
                <LinkScanBox
                  value={linkInput}
                  onChange={setLinkInput}
                  disabled={loading}
                />
                <MagneticAnalyze
                  onClick={handleScanLinks}
                  label={
                    canScanLinks
                      ? `Scan ${parsedLinks.urls.length} link${parsedLinks.urls.length === 1 ? "" : "s"}`
                      : "Scan Links"
                  }
                />
              </motion.div>
            )}
          </motion.div>
        )}

        {error && (
          <motion.div
            className="mt-5 sm:mt-6 rounded-lg border border-red-500/20 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-300"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {error}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
