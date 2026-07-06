"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

import ResultsCard from "@/components/ResultsCard";
import type { AnalyzeResult, Finding } from "@/lib/api";

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
  const rawData =
    (resultId ? sessionStorage.getItem(`tecxelens-result:${resultId}`) : null) ||
    params.get("data");

  if (!rawData) {
    return (
      <div className="max-w-4xl mx-auto mt-16 sm:mt-20 px-4 sm:px-6 text-center">
        <p className="text-gray-500 dark:text-gray-400 mb-4">No analysis data found.</p>
        <Link href="/upload" className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 font-medium">Upload a document</Link>
      </div>
    );
  }

  let data: AnalyzeResult;
  try {
    data = JSON.parse(decodeURIComponent(rawData));
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

  return (
    <div className="max-w-4xl mx-auto mt-8 sm:mt-12 px-4 sm:px-6 pb-16">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-semibold text-gray-900 dark:text-white">Analysis Results</h1>
        <Link href="/upload" className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 font-medium">Analyze another</Link>
      </div>
      <ResultsCard overallScore={data.overall_score} riskLevel={data.risk_level} findings={data.findings} summary={data.summary} />
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
