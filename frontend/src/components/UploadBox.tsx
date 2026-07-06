"use client";

import { useCallback, useRef, useState } from "react";

interface Props {
  onFileSelected: (file: File) => void;
  disabled: boolean;
}

export default function UploadBox({ onFileSelected, disabled }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      if (disabled) return;
      const allowed = [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      ];
      const name = file.name.toLowerCase();
      const matchesAllowedExtension =
        name.endsWith(".pdf") || name.endsWith(".txt") || name.endsWith(".pptx");

      if (!allowed.includes(file.type) && !matchesAllowedExtension) {
        alert("Please upload a PDF, TXT, or PPTX file.");
        return;
      }
      onFileSelected(file);
    },
    [onFileSelected, disabled]
  );

  return (
    <div
      onDragOver={(e) => {
        if (!disabled) {
          e.preventDefault();
          setDragOver(true);
        }
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
      }}
      onClick={() => {
        if (!disabled) inputRef.current?.click();
      }}
      className={`relative rounded-xl p-14 text-center transition-all overflow-hidden ${
        disabled
          ? "border border-gray-200 dark:border-white/5 bg-gray-100 dark:bg-white/5 cursor-not-allowed opacity-50"
          : dragOver
            ? "border-2 border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 cursor-pointer shadow-[0_0_30px_rgba(99,102,241,0.15)]"
            : "border border-gray-300 dark:border-white/10 bg-white dark:bg-white/[0.03] cursor-pointer hover:border-gray-400 dark:hover:border-white/20 hover:bg-gray-50 dark:hover:bg-white/[0.06]"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        disabled={disabled}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      <svg
        className={`mx-auto h-10 w-10 ${disabled ? "text-gray-400 dark:text-gray-600" : "text-gray-400 dark:text-gray-500"}`}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
        />
      </svg>
      <p className="mt-3 text-base font-medium text-gray-700 dark:text-gray-300">
        Drop your document here or click to browse
      </p>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-500">.pdf, .txt, .pptx</p>
    </div>
  );
}
