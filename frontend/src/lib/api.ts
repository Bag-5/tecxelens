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
