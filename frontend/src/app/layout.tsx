import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { ThemeProvider } from "@/lib/theme";
import ThemeToggle from "@/components/ThemeToggle";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TECXE Lens — Compliance Analyzer",
  description: "AI-powered cybersecurity compliance analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var t=localStorage.getItem("tecxe-theme")||"system";if(t==="dark"||(t==="system"&&window.matchMedia("(prefers-color-scheme: dark)").matches))document.documentElement.classList.add("dark")})()`,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col bg-gray-50 dark:bg-[#0a0a0f] text-gray-900 dark:text-gray-200 transition-colors overflow-x-hidden">
        <ThemeProvider>
          <header className="sticky top-0 z-50 border-b border-gray-200/60 dark:border-white/5 bg-white/80 dark:bg-black/40 backdrop-blur-xl transition-colors">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 sm:h-18 flex items-center justify-between gap-3">
              <Link href="/" className="text-base sm:text-lg font-bold tracking-tight shrink-0">
                <span className="text-gray-900 dark:text-white">TECXE</span>{" "}
                <span className="bg-gradient-to-r from-indigo-600 to-cyan-600 dark:from-indigo-400 dark:to-cyan-400 bg-clip-text text-transparent">
                  Lens
                </span>
              </Link>
              <nav className="flex items-center gap-2 sm:gap-4 text-sm">
                <Link
                  href="/upload"
                  className="rounded-full px-3 py-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-white hover:bg-gray-100/80 dark:hover:bg-white/5 transition-colors"
                >
                  Upload
                </Link>
                <ThemeToggle />
              </nav>
            </div>
          </header>
          <main className="flex-1">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
