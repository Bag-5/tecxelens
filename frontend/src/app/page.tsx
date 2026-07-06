import Link from "next/link";

export default function Home() {
  return (
    <div className="relative flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] px-4 sm:px-6 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-indigo-100/60 via-white to-cyan-100/40 dark:from-indigo-950/60 dark:via-black dark:to-cyan-950/40 animate-gradient-shift" />

      <div className="absolute top-1/4 left-1/4 w-48 sm:w-72 md:w-96 h-48 sm:h-72 md:h-96 rounded-full bg-indigo-400/20 dark:bg-indigo-500/10 blur-[80px] sm:blur-[100px] md:blur-[120px] animate-pulse-glow" />
      <div className="absolute bottom-1/4 right-1/4 w-44 sm:w-64 md:w-80 h-44 sm:h-64 md:h-80 rounded-full bg-cyan-400/20 dark:bg-cyan-500/10 blur-[60px] sm:blur-[80px] md:blur-[100px] animate-pulse-glow" style={{ animationDelay: "1s" }} />

      <div className="relative text-center max-w-xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 dark:border-indigo-500/20 bg-indigo-100 dark:bg-indigo-500/5 px-4 py-1.5 text-[11px] sm:text-xs text-indigo-700 dark:text-indigo-300 mb-4 sm:mb-6">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-500 dark:bg-indigo-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-600 dark:bg-indigo-500" />
          </span>
          AI-Powered Security Analysis
        </div>

        <h1 className="text-[2.5rem] sm:text-5xl md:text-6xl font-bold tracking-tight">
          <span className="text-gray-900 dark:text-white">TECXE</span>{" "}
          <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-cyan-600 dark:from-indigo-400 dark:via-violet-400 dark:to-cyan-400 bg-clip-text text-transparent">
            Lens
          </span>
        </h1>

        <p className="mt-4 sm:mt-5 text-sm sm:text-base text-gray-500 dark:text-gray-400 leading-relaxed max-w-prose mx-auto">
          Upload a compliance document and get instant AI-driven findings,
          risk scores, and remediation reports — no configuration needed.
        </p>

        <Link
          href="/upload"
          className="group mt-7 sm:mt-8 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 px-6 sm:px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40 hover:scale-[1.02]"
        >
          Start Analysis
          <svg className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
          </svg>
        </Link>
      </div>
    </div>
  );
}
