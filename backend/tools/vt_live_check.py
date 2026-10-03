import httpx

BASE = "https://bag5.pythonanywhere.com"
O = {"Origin": "https://tecxelens.vercel.app"}

print("=== your URL, live against VirusTotal ===")
r = httpx.post(f"{BASE}/scan-links", json={"urls": ["https://www.sailup.io"]}, timeout=90, headers=O)
print("  HTTP", r.status_code)
d = r.json()
print(f"  score: {d['overall_score']} ({d['risk_level']})  findings: {len(d['findings'])}  "
      f"quota_exhausted: {d['quota_exhausted']}  filtered: {d['filtered_count']}")

for l in d["links"]:
    print(f"    {l['url']}")
    print(f"      verdict={l['verdict']}  severity={l['severity']}  source={l['source']}")
    print(f"      malicious={l['malicious']} suspicious={l['suspicious']} "
          f"harmless={l['harmless']} undetected={l['undetected']}")
    if l.get("categories"):
        print(f"      categories={l['categories']}")
    if l.get("permalink"):
        print(f"      permalink={l['permalink']}")
    if l.get("last_analysis_date"):
        print(f"      last analysed={l['last_analysis_date']}")

print()
print("  summary:", d["summary"])

if d["findings"]:
    print()
    print("  findings:")
    for f in d["findings"]:
        print(f"    [{f['severity']}] {f['title']}")
        print(f"        {f['description'][:220]}")
else:
    print()
    print("  findings: none")

print()
print("=== privacy filter still enforced WITH a live provider ===")
r2 = httpx.post(
    f"{BASE}/scan-links",
    json={"urls": ["http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/"]},
    timeout=90,
    headers=O,
)
d2 = r2.json()
print(f"  filtered_count={d2['filtered_count']}  score={d2['overall_score']} ({d2['risk_level']})")
for l in d2["links"]:
    print(f"    {l['url']}  ->  {l['verdict']} / {l['source']}")
print("  summary:", d2["summary"][:200])
