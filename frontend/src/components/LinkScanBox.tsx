"use client";

import { useRef, useState } from "react";
import { parseLinkInput, type ParsedLinks } from "@/lib/parseLinks";

export type { ParsedLinks };

/**
 * Deliberately mirrors UploadBox: dashed dropzone, click-to-browse, a counter
 * in the corner, and the same ring/muted palette so the two halves of the page
 * read as one control rather than two bolted together.
 *
 * The parser itself lives in @/lib/parseLinks so it can be tested without a
 * DOM and reused by the upload page.
 */

interface LinkScanBoxProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  maxUrls?: number;
}

export default function LinkScanBox({
  value,
  onChange,
  disabled = false,
  maxUrls = 100,
}: LinkScanBoxProps) {
  const [dragging, setDragging] = useState(false);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const parsed = parseLinkInput(value);
  const { urls, rejected } = parsed;
  const overLimit = urls.length > maxUrls;

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const text = e.dataTransfer.getData("text/plain");
    if (text) {
      onChange(value ? `${value.replace(/\s+$/, "")}\n${text}` : text);
    }
  };

  const pasteFromClipboard = async () => {
    if (disabled) return;
    try {
      const text = await navigator.clipboard.readText();
      if (text) onChange(value ? `${value.replace(/\s+$/, "")}\n${text}` : text);
    } catch {
      // Clipboard permission denied; the textarea still accepts Ctrl+V.
      areaRef.current?.focus();
    }
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`relative rounded-2xl border-2 border-dashed transition-colors ${
          dragging
            ? "border-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-500/10"
            : "border-gray-300 dark:border-white/12 bg-gray-50/60 dark:bg-white/[0.03] hover:border-indigo-300 dark:hover:border-white/25"
        } ${disabled ? "opacity-60" : ""}`}
      >
        <textarea
          ref={areaRef}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          placeholder={"Paste or drop links here, one per line:\n\nhttps://example.com/report.pdf\nhttps://vendor-portal.example.org/login"}
          spellCheck={false}
          rows={6}
          aria-label="URLs to scan"
          className="w-full resize-y bg-transparent px-4 pt-4 pb-3 text-sm font-mono text-gray-800 dark:text-gray-200 placeholder:text-gray-400 dark:placeholder-gray-500 focus:outline-none disabled:cursor-not-allowed"
        />

        <div className="flex items-center justify-between gap-3 border-t border-gray-200/70 dark:border-white/8 px-4 py-2.5">
          <button
            type="button"
            onClick={pasteFromClipboard}
            disabled={disabled}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 transition-colors hover:text-indigo-600 dark:hover:text-indigo-400 disabled:opacity-50"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
            </svg>
            Paste
          </button>

          <span
            className={`text-xs tabular-nums ${
              overLimit ? "text-red-600 dark:text-red-400 font-semibold" : "text-gray-400 dark:text-gray-500"
            }`}
          >
            {urls.length} / {maxUrls}
          </span>
        </div>
      </div>

      {overLimit && (
        <p className="text-xs text-red-600 dark:text-red-400">
          {urls.length - maxUrls} link{urls.length - maxUrls === 1 ? "" : "s"} over the
          limit. Remove some, or split them across two scans — the backend also
          caps this.
        </p>
      )}

      {rejected.length > 0 && (
        <details className="rounded-lg border border-amber-500/25 bg-amber-50/70 dark:bg-amber-500/[0.08] px-3 py-2">
          <summary className="cursor-pointer text-xs font-medium text-amber-800 dark:text-amber-300 select-none">
            {rejected.length} entr{rejected.length === 1 ? "y" : "ies"} could not be
            read and will be skipped
          </summary>
          <ul className="mt-2 space-y-1">
            {rejected.slice(0, 8).map((r, i) => (
              <li key={i} className="text-xs text-amber-900/80 dark:text-amber-200/80">
                <span className="font-mono break-all">{r.input}</span>{" "}
                <span className="opacity-70">— {r.reason}</span>
              </li>
            ))}
            {rejected.length > 8 && (
              <li className="text-xs opacity-70">
                …and {rejected.length - 8} more
              </li>
            )}
          </ul>
        </details>
      )}

      <p className="text-xs leading-relaxed text-gray-500 dark:text-gray-400">
        Links are checked against VirusTotal. Private and internal addresses are
        withheld from VirusTotal and reported as unchecked rather than safe.
      </p>
    </div>
  );
}
