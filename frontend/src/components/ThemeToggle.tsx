"use client";

import { useTheme } from "@/lib/theme";

const icons: Record<string, React.ReactNode> = {
  system: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h3m-3 4h3m-3 4h3M6 4h12a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Zm0 0V3m0 1v0ZM3 18h18" />
    </svg>
  ),
  light: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
    </svg>
  ),
  dark: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
    </svg>
  ),
};

export default function ThemeToggle() {
  const { resolved, theme, cycle } = useTheme();
  const label = theme === "system" ? `Auto (${resolved})` : theme;

  return (
    <button
      onClick={cycle}
      title={`Theme: ${theme} (click to cycle)`}
      aria-label={`Theme selector, current ${label}`}
      className="flex items-center gap-1.5 rounded-full border border-gray-200 dark:border-white/10 px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
    >
      {icons[theme]}
      <span className="capitalize">{label}</span>
    </button>
  );
}
