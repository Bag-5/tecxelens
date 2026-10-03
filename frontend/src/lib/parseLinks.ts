const SCHEME_RE = /^[a-z][a-z0-9+.-]*:\/\//i;

/** A dotted-numeric token: a bare IPv4 literal such as 8.8.8.8. */
const IPV4_RE = /^\d{1,3}(\.\d{1,3}){3}$/;

/** A bare hostname: at least one label plus an alphabetic TLD, e.g. a.co.uk. */
const HOST_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$/i;

/**
 * The authority portion of a token, with any credentials, port, path, query or
 * fragment removed — so `user:pw@Example.com:8443/x?y#z` reduces to
 * `Example.com`. The token is not a bare host if this does not look like one.
 */
function authorityOf(token: string): string {
  let host = token.split(/[/?#]/, 1)[0];
  const at = host.lastIndexOf("@");
  if (at !== -1) host = host.slice(at + 1);
  const colon = host.lastIndexOf(":");
  if (colon !== -1) host = host.slice(0, colon);
  return host;
}

export interface ParsedLinks {
  urls: string[];
  /** Tokens that looked like a URL but were rejected, with the reason. */
  rejected: { input: string; reason: string }[];
}

/**
 * Client-side parse of pasted link text.
 *
 * This exists purely for immediate feedback on typos. It is NOT the privacy
 * filter and NOT the validator: the server re-normalises, re-checks the scheme
 * and applies the private/internal-address rules regardless of what happens
 * here, so a caller bypassing this function gains nothing.
 */
export function parseLinkInput(raw: string): ParsedLinks {
  const urls: string[] = [];
  const rejected: ParsedLinks["rejected"] = [];
  const seen = new Set<string>();

  for (const token of raw.split(/[\n,;\s]+/)) {
    const trimmed = token.trim();
    if (!trimmed) continue;

    // Only auto-prepend a scheme when the token actually looks like a host.
    // Without this guard, `new URL("https://2")` is interpreted by WHATWG as the
    // IPv4 literal 0.0.0.2, so a stray number in a pasted list would silently
    // become a link and slip past a naive "hostname has a dot" check.
    const hasScheme = SCHEME_RE.test(trimmed);
    const authority = authorityOf(trimmed);
    const looksLikeHost = IPV4_RE.test(authority) || HOST_RE.test(authority);

    if (!hasScheme && !looksLikeHost) {
      rejected.push({
        input: trimmed,
        reason:
          /^\d+(\.\d+)*$/.test(authority)
            ? "not a valid host or IP address"
            : "missing a domain (expected something like example.com)",
      });
      continue;
    }

    const candidate = hasScheme ? trimmed : `https://${trimmed}`;

    let parsed: URL;
    try {
      parsed = new URL(candidate);
    } catch {
      rejected.push({ input: trimmed, reason: "not a valid URL" });
      continue;
    }

    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      rejected.push({
        input: trimmed,
        reason: `only http and https are accepted (got ${parsed.protocol.replace(":", "")})`,
      });
      continue;
    }

    if (!parsed.hostname.includes(".")) {
      rejected.push({ input: trimmed, reason: "missing a domain" });
      continue;
    }

    // Fragments are client-side only and would change the VirusTotal URL id,
    // so two links differing only by fragment would score separately.
    parsed.hash = "";
    const normalised = parsed.toString();
    if (seen.has(normalised)) continue;
    seen.add(normalised);
    urls.push(normalised);
  }

  return { urls, rejected };
}