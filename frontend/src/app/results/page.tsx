"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

import ResultsCard from "@/components/ResultsCard";
import type { AnalyzeResult, Finding } from "@/lib/api";

function Skeleton() {
  return (
    <div className="max-w-3xl mx-auto mt-12 px-4 pb-16 animate-pulse space-y-8">
      <div className="flex justify-center"><div className="w-44 h-44 rounded-full bg-gray-200 dark:bg-white/10" /></div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => <div key={i} className="h-24 rounded-xl bg-gray-200 dark:bg-white/10" />)}
      </div>
      {[1, 2].map((i) => <div key={i} className="h-40 rounded-xl bg-gray-200 dark:bg-white/10" />)}
    </div>
  );
}

function ResultsContent() {
  const params = useSearchParams();

  const rawData = params.get("data");

  if (!rawData) {
    return (
      <div className="max-w-3xl mx-auto mt-20 px-4 text-center">
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
      <div className="max-w-3xl mx-auto mt-20 px-4 text-center">
        <p className="text-gray-500 dark:text-gray-400">Could not load results. Please try again.</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto mt-12 px-4 pb-16">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Analysis Results</h1>
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
