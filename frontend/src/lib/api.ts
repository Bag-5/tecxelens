// Backend location comes only from NEXT_PUBLIC_API_URL; nothing is hardcoded
// here. Next.js inlines NEXT_PUBLIC_* at build time, so this must be defined as
// a project environment variable before building or deploying, and changing it
// requires a rebuild rather than just a restart.
//
// Failing loudly beats silently defaulting to some host: a baked-in fallback
// either points at a decommissioned backend or quietly sends document contents
// somewhere unintended, and both failures look like "the app is just broken".
const _raw = process.env.NEXT_PUBLIC_API_URL;

if (!_raw) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set. Add it to the deployment environment " +
      "(it is inlined at build time, so rebuild after changing it)."
  );
}

export const BASE_URL = _raw.replace(/\/+$/, "");

export interface UploadResult {
  file_id: string;
  filename: string;
  status: string;
}

export interface FindingRef {
  document: string;
  section: string;
}

export interface CveEntry {
  id: string;
  description: string;
  cvss_score: number | null;
  published: string;
  severity: string;
}

export interface Finding {
  title: string;
  severity: string;
  reference?: string;
  description: string;
  recommendation: string;
  references: FindingRef[];
  cves: CveEntry[];
}

export interface AnalyzeResult {
  summary: string;
  overall_score: number;
  risk_level: string;
  findings: Finding[];
}

/**
 * Where a verdict came from. `filtered` means the privacy filter withheld the
 * URL from VirusTotal entirely, so "clean" and "never sent" stay distinguishable
 * on the surface.
 */
export type LinkSource = "lookup" | "queued" | "filtered";

export type LinkVerdict =
  | "malicious"
  | "suspicious"
  | "harmless"
  | "unknown"
  | "not_scanned";

export interface LinkVerdictEntry {
  url: string;
  verdict: LinkVerdict;
  /** critical | high | medium | low | none */
  severity: string;
  malicious: number;
  suspicious: number;
  harmless: number;
  undetected: number;
  timeout: number;
  categories: Record<string, string>;
  reputation: number;
  /** Unix seconds; 0 when VirusTotal has never analysed the URL. */
  last_analysis_date: number;
  permalink: string;
  source: LinkSource;
}

/**
 * Reuses the document result shape so the existing results page, findings list
 * and PDF download button work unchanged. `overall_score` is a *link* risk
 * score here, which is why `report_type` is carried alongside it.
 */
export interface LinkScanResult extends AnalyzeResult {
  report_type: "links";
  links: LinkVerdictEntry[];
  filtered_count: number;
  truncated_count: number;
  quota_exhausted: boolean;
  file_id: string;
}

/** Polling response: verdicts only, no AI prose and no report rewrite. */
export interface LinkStatusResult {
  links: LinkVerdictEntry[];
  link_risk_score: number;
  link_risk_level: string;
  checked_count: number;
  filtered_count: number;
  truncated_count: number;
  quota_exhausted: boolean;
  max_urls: number;
}

export interface LinkSubmitResult {
  /** Keyed by URL, each value the provider's job id. */
  submitted: Record<string, { url: string; job_id: string }>;
  granted: number;
  deferred: number;
  reason: string | null;
}

/**
 * Whether this deployment can actually perform link lookups. Checked on load so
 * an unconfigured provider is explained up front instead of returning a wall of
 * "unknown" verdicts that would look like a clean scan.
 */
export interface LinkCapabilities {
  enabled: boolean;
  provider: string;
  max_urls: number;
  submission_enabled: boolean;
  reason: string | null;
}

export type ApiResult<T> =
  | { success: true; data: T }
  | { success: false; error: string };

async function request<T>(
  url: string,
  init?: RequestInit
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${BASE_URL}${url}`, {
      ...init,
      signal: AbortSignal.timeout(120_000),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const detail = body?.detail || res.statusText || `HTTP ${res.status}`;
      return { success: false, error: detail };
    }

    const data: T = await res.json();
    return { success: true, data };
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      return {
        success: false,
        error: "Analysis is taking longer than expected. Please keep this tab open and try again in a moment.",
      };
    }
    if (err instanceof TypeError && err.message === "Failed to fetch") {
      return { success: false, error: "Network error — is the backend running?" };
    }
    const msg = err instanceof Error ? err.message : "Unknown error";
    return { success: false, error: msg };
  }
}

export async function uploadFile(file: File): Promise<ApiResult<UploadResult>> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResult>("/upload", { method: "POST", body: form });
}

export async function analyzeFile(fileId: string): Promise<ApiResult<AnalyzeResult>> {
  return request<AnalyzeResult>("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId }),
  });
}

/** One POST helper for all three link endpoints: they share a request body. */
function postLinks<T>(url: string, urls: string[], enrich = false): Promise<ApiResult<T>> {
  return request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls, enrich }),
  });
}

/**
 * Read once per page load. Deliberately tolerant: a failure here must not break
 * the document flow, so the caller treats an error as "unknown" and leaves the
 * Links tab enabled rather than hiding a feature that might be fine.
 */
export async function fetchLinkCapabilities(): Promise<ApiResult<LinkCapabilities>> {
  return request<LinkCapabilities>("/capabilities");
}

export async function scanLinks(urls: string[]): Promise<ApiResult<LinkScanResult>> {
  return postLinks<LinkScanResult>("/scan-links", urls, true);
}

/** Poll for verdicts on URLs that were previously unknown or submitted. */
export async function pollLinkStatus(urls: string[]): Promise<ApiResult<LinkStatusResult>> {
  return postLinks<LinkStatusResult>("/scan-links/status", urls, false);
}

/**
 * Ask VirusTotal to analyse unknown URLs. Returns immediately with job ids;
 * poll `pollLinkStatus` after a delay to collect the verdicts.
 */
export async function submitLinks(urls: string[]): Promise<ApiResult<LinkSubmitResult>> {
  return postLinks<LinkSubmitResult>("/scan-links/submit", urls, false);
}
