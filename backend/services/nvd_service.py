import re
from datetime import datetime

import httpx

from core.config import NVD_API_KEY

TECH_KEYWORDS = [
    "openssl", "tls", "apache", "windows", "smb", "ssh", "ssl",
    "nginx", "linux", "mysql", "postgresql", "mongodb", "docker",
    "kubernetes", "python", "node.js", "java", ".net", "iis",
    "active directory", "ldap", "kerberos", "oauth", "saml",
    "vpn", "openvpn", "ipsec", "wpa", "wep", "bluetooth", "usb",
    "bios", "uefi", "tpm", "hsm", "pki", "x.509", "openssh",
    "tomcat", "nginx", "redis", "elasticsearch", "rabbitmq",
    "nginx", "haproxy", "curl", "wget", "bash", "powershell",
    "macos", "android", "ios", "chrome", "firefox", "edge",
    "safari", "exchange", "sharepoint", "sql server", "oracle",
]

_cache: dict[str, list[dict]] = {}


def _has_tech_keyword(text: str) -> str | None:
    lower = text.lower()
    for kw in TECH_KEYWORDS:
        if kw in lower:
            return kw
    return None


def _parse_cve(item: dict) -> dict | None:
    try:
        cve = item.get("cve", {})
        cve_id = cve.get("id", "")

        descriptions = cve.get("descriptions", [])
        description = ""
        for d in descriptions:
            if d.get("lang") == "en":
                description = d.get("value", "")
                break

        metrics = cve.get("metrics", {})
        cvss_data = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                cvss_data = metrics[key][0].get("cvssData", {})
                break

        cvss_score = None
        severity = "UNKNOWN"
        if cvss_data:
            cvss_score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity", "UNKNOWN")

        published = cve.get("published", "")
        if published:
            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                published = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        return {
            "id": cve_id,
            "description": description[:200],
            "cvss_score": cvss_score,
            "published": published[:10] if published else "",
            "severity": severity,
        }
    except Exception:
        return None


async def search_cves(keyword: str, top_k: int = 3) -> list[dict]:
    keyword_lower = keyword.strip().lower()

    if keyword_lower in _cache:
        return _cache[keyword_lower][:top_k]

    api_keys_to_try = [NVD_API_KEY] if NVD_API_KEY else [""]
    if NVD_API_KEY:
        api_keys_to_try.append("")

    for api_key in api_keys_to_try:
        try:
            params = {
                "keywordSearch": keyword,
                "resultsPerPage": 10,
            }
            headers = {"User-Agent": "TECXE-Lens/1.0"}
            if api_key:
                headers["apiKey"] = api_key

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://services.nvd.nist.gov/rest/json/cves/2.0",
                    params=params,
                    headers=headers,
                )

            if resp.status_code != 200:
                continue

            data = resp.json()
            vulnerabilities = data.get("vulnerabilities", [])

            results: list[dict] = []
            for item in vulnerabilities:
                parsed = _parse_cve(item)
                if parsed:
                    results.append(parsed)
                    if len(results) >= top_k:
                        break

            _cache[keyword_lower] = results
            return results

        except Exception:
            continue

    _cache[keyword_lower] = []
    return []


def extract_tech_keywords(text: str) -> list[str]:
    lower = text.lower()
    found: set[str] = set()
    for kw in TECH_KEYWORDS:
        if kw in lower:
            found.add(kw)
    return sorted(found)
