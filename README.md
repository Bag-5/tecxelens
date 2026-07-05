# TECXE Lens

**Compliance document analyzer** — upload a policy or security document and receive a structured compliance assessment with severity-graded findings, regulatory references, and CVE enrichment.

TECXE Lens processes PDF documents through a deterministic rule engine, cross-references findings against a local knowledge base of cybersecurity frameworks, enriches technical vulnerabilities from the National Vulnerability Database (NVD), and generates an explanatory AI report — all without letting AI make any compliance decisions.

---

## Architecture

```
┌─────────────┐     ┌─────────────────────────────────────┐     ┌───────────┐
│   PDF Upload │────▶│          Analysis Pipeline           │────▶│  Results   │
└─────────────┘     │                                     │     └───────────┘
                    │  Rule Engine → Knowledge Engine       │
                    │  → NVD Enrichment → AI Report         │
                    └─────────────────────────────────────┘
```

**Pipeline stages:**
1. **Rule Engine** — Deterministic keyword matching against configurable rules (Weak Password Policy, MFA Not Enforced, Shared Accounts, Log Retention, Weak Authentication). No AI involvement.
2. **Knowledge Engine** — Searches a local library of regulatory PDFs (Ghanaian acts, ISO 27001, CIS Controls, NIST CSF) for per-finding references.
3. **NVD Enrichment** — Extracts technology keywords from findings and queries the NVD REST API 2.0 for relevant CVEs with CVSS scores.
4. **AI Report** — OpenRouter-powered narrative summary and recommendations. Receives findings and references as context but never makes compliance decisions.

**Compliance score:**
- Starts at 100, subtracts weighted penalties per finding
- Critical = 30, High = 20, Medium = 10, Low = 5
- Clamped 0–100, AI never calculates scores

---

## Tech Stack

| Layer      | Technology                                              |
|------------|---------------------------------------------------------|
| Backend    | Python 3.12, FastAPI, uvicorn, pypdf, httpx             |
| Frontend   | Next.js 15 (App Router), TypeScript, Tailwind CSS v4    |
| AI         | OpenRouter API (primary + fallback model)               |
| External   | NVD REST API 2.0                                        |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- An [OpenRouter API key](https://openrouter.ai/keys) (required for AI reports)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

Create `backend/.env`:

```env
OPENROUTER_API_KEY=sk-or-...
NVD_API_KEY=your-nvd-key      # optional, for higher rate limits
```

Start the server:

```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**.

---

## Deployment

### Vercel frontend

- Set the project root to `frontend/`
- Add `NEXT_PUBLIC_API_URL` in the Vercel environment variables and point it at the Render backend URL
- Build command: `npm run build`
- Install command: `npm install`

### Railway backend

- Use `backend/` as the service root
- Railway will pick up `backend/railway.toml`
- Optional env vars:
  - `FRONTEND_ORIGIN` to lock CORS to your frontend domain
  - `OPENROUTER_API_KEY` for AI reports
  - `NVD_API_KEY` for higher NVD rate limits

---

## Configuration

The `.env` file at `backend/.env` supports these variables:

| Variable                    | Required | Default                                    | Description                          |
|-----------------------------|----------|--------------------------------------------|--------------------------------------|
| `OPENROUTER_API_KEY`        | Yes      | —                                          | OpenRouter API key                   |
| `OPENROUTER_MODEL`          | No       | `openai/gpt-oss-20b:free`                  | Primary AI model                     |
| `OPENROUTER_FALLBACK_MODEL` | No       | `google/gemma-4-26b-a4b-it:free`           | Fallback if primary fails            |
| `API_VERSION`               | No       | `v1`                                       | API version string                   |
| `NVD_API_KEY`               | No       | —                                          | NVD API key (higher rate limits)     |

---

## Knowledge Base

Regulatory documents live under `backend/knowledge/`:

```
knowledge/
├── ghana/
│   ├── 1992 Constitution of Ghana.pdf
│   ├── Cybersecurity-Act-2020-Act-1038.pdf
│   ├── Data-Protection-Act-2012-Act-843.pdf
│   └── Electronic-Transactions-Act-772.pdf
└── international/
    ├── CIS_Controls_v8_Guide.pdf
    ├── ISO 27001-2022 rm.pdf
    └── NIST.CSWP.29.pdf
```

To add new standards, drop PDFs into the appropriate subdirectory and restart the server. The knowledge engine indexes all PDFs on startup and caches them in memory.

---

## API Endpoints

| Method | Path                    | Description                         |
|--------|-------------------------|-------------------------------------|
| GET    | `/health`               | Health check                        |
| POST   | `/upload`               | Upload a PDF (returns `file_id`)    |
| POST   | `/analyze`              | Analyze a previously uploaded file  |
| GET    | `/knowledge/search?q=`  | Search the knowledge base           |

### POST `/analyze`

Request body:

```json
{ "file_id": "uuid-from-upload" }
```

Response:

```json
{
  "summary": "The document shows adequate password policies...",
  "overall_score": 82,
  "risk_level": "Good",
  "findings": [
    {
      "title": "Weak Password Policy",
      "severity": "high",
      "description": "...",
      "recommendation": "...",
      "references": [
        { "document": "ghana/Cybersecurity-Act-2020-Act-1038.pdf", "section": "section 35" }
      ],
      "cves": [
        {
          "id": "CVE-2023-1234",
          "description": "...",
          "cvss_score": 7.5,
          "published": "2023-01-01",
          "severity": "HIGH"
        }
      ]
    }
  ]
}
```

---

## Risk Levels

| Score      | Label       |
|------------|-------------|
| 90–100     | Excellent   |
| 75–89      | Good        |
| 50–74      | Medium      |
| 25–49      | Poor        |
| 0–24       | Critical    |

---

## Custom Rules

Rules are defined in `backend/core/rules.py`. Each rule specifies:

- `keywords` — terms that trigger the finding
- `negations` — terms that suppress it (e.g., mentions of "MFA" suppress "MFA Not Enforced")
- `severity` — critical, high, medium, or low
- `reference` — regulatory identifier

---

## License

MIT
