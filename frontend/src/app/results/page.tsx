"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

import ResultsCard from "@/components/ResultsCard";
import LinkResultsCard from "@/components/LinkResultsCard";
import DownloadReportButton from "@/components/DownloadReportButton";
import type { AnalyzeResult, LinkScanResult } from "@/lib/api";

function Skeleton() {
  return (
    <div className="max-w-4xl mx-auto mt-10 sm:mt-12 px-4 sm:px-6 pb-16 animate-pulse space-y-8">
      <div className="flex justify-center"><div className="w-36 h-36 sm:w-44 sm:h-44 rounded-full bg-gray-200 dark:bg-white/10" /></div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        {[1, 2, 3, 4, 5].map((i) => <div key={i} className="h-20 sm:h-24 rounded-xl bg-gray-200 dark:bg-white/10" />)}
      </div>
      {[1, 2].map((i) => <div key={i} className="h-40 sm:h-48 rounded-xl bg-gray-200 dark:bg-white/10" />)}
    </div>
  );
}

function ResultsContent() {
  const params = useSearchParams();

  const resultId = params.get("result");
  const urlData = params.get("data");

  let rawData: string | null = null;
  let fileId: string | null = null;
  let fromUrl = false;

  if (resultId) {
    try {
      rawData = sessionStorage.getItem(`tecxelens-result:${resultId}`);
      fileId = sessionStorage.getItem(`tecxelens-file:${resultId}`);
    } catch { /* private/restricted mode */ }
  }
  if (!rawData && urlData) {
    rawData = urlData;
    fromUrl = true;
  }

  if (!rawData) {
    return (
      <div className="max-w-4xl mx-auto mt-16 sm:mt-20 px-4 sm:px-6 text-center">
        <p className="text-gray-500 dark:text-gray-400 mb-4">No analysis data found.</p>
        <Link href="/upload" className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 font-medium">Upload a document</Link>
      </div>
    );
  }

  let data: AnalyzeResult | LinkScanResult;
  try {
    data = JSON.parse(fromUrl ? decodeURIComponent(rawData) : rawData);
  } catch {
    return (
      <div className="max-w-4xl mx-auto mt-16 sm:mt-20 px-4 sm:px-6 text-center">
        <p className="text-gray-500 dark:text-gray-400">Could not load results. Please try again.</p>
        <div className="mt-4">
          <Link href="/upload" className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 font-medium">Go back to upload</Link>
        </div>
      </div>
    );
  }

  // A link scan and a document scan share the summary/score/findings shape but
  // differ in score meaning and in the per-URL table, so they get different
  // cards. Keying off report_type keeps the stored payload self-describing.
  const isLinkReport =
    (data as LinkScanResult).report_type === "links" &&
    Array.isArray((data as LinkScanResult).links);

  return (
    <div className="max-w-4xl mx-auto mt-8 sm:mt-12 px-4 sm:px-6 pb-16">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-semibold text-gray-900 dark:text-white">
          {isLinkReport ? "Link Risk Report" : "Analysis Results"}
        </h1>
        <div className="flex items-center gap-3">
          {/* LinkResultsCard renders its own download button, since the PDF it
              serves is a link report rather than a compliance report. */}
          {fileId && !isLinkReport && <DownloadReportButton fileId={fileId} />}
          <Link href="/upload" className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 font-medium">
            {isLinkReport ? "Scan more links" : "Analyze another"}
          </Link>
        </div>
      </div>

      {isLinkReport ? (
        <LinkResultsCard result={data as LinkScanResult} />
      ) : (
        <ResultsCard
          overallScore={data.overall_score}
          riskLevel={data.risk_level}
          findings={data.findings}
          summary={data.summary}
        />
      )}
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<Skeleton />}>
      <ResultsContent />
    </Suspense>
  );
}
