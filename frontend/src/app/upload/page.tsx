"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useMagnetic } from "@/hooks/useMagnetic";

import UploadBox from "@/components/UploadBox";
import AnalyzingAnimation from "@/components/AnalyzingAnimation";
import { uploadFile, analyzeFile } from "@/lib/api";

type Phase = "idle" | "uploading" | "analyzing" | "done";

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

export default function UploadPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

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

  const loading = phase === "uploading" || phase === "analyzing";

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
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">Upload Document</h1>
          <p className="mt-1.5 text-sm sm:text-base text-gray-500 dark:text-gray-400">Drop a compliance PDF, TXT, or PPTX to begin analysis</p>
          <p className="mt-2 text-xs sm:text-sm text-gray-500 dark:text-gray-500">Large files or first-time analyses can take a little longer.</p>
        </motion.div>

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
