# LegalEase

LegalEase is a polished, college-project MVP for plain-language legal document review. It demonstrates the complete presentation flow:

> Login or demo access -> upload a PDF/DOCX -> validate and extract text -> find important clauses -> classify risk -> show highlighted source text beside explanations -> download a PDF report.

The results are deliberately and visibly labelled as **informational, not legal advice**.

## What is included

- A presentation-ready, responsive HTML/CSS/JavaScript interface - no frontend build step.
- A Python REST backend (`server.py`) with login, registration and one-click demo access.
- PDF text extraction (`pypdf`) and DOCX structured parsing (DOCX XML).
- A dependable local NLP-style rule engine for liability, indemnity, termination, penalties, renewal, confidentiality, payment and governing-law clauses.
- Source-text highlights linked to risk cards, clear plain-English guidance, loading/error states, and a PDF report download.
- A seeded **Northstar Service Partner Agreement** so the demonstration works as soon as the app opens.
- SQLite for immediate local use plus a MySQL 8-ready relational model in `database/schema.mysql.sql`.
- Logical document isolation: every document read is filtered by the signed-in `user_id`.
- Demonstration RBAC roles (`member`, `admin`), safe password hashing, restrictive security headers, strict PDF/DOCX checks, a 10 MB limit, and a small malware-validation gateway placeholder.

## Run locally

### 1. Use Python 3.10+

Open a terminal in this folder. For a normal Python installation, create a virtual environment (recommended) and install the two document/report packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Configure (optional)

Copy `.env.example` to `.env` if you want to keep local settings nearby. The lightweight demo intentionally reads its few deployment variables from the environment rather than requiring an extra package:

```powershell
$env:LEGALEASE_PORT = "8000"
$env:ANALYSIS_MODE = "local"
```

### 3. Start the application

```powershell
python server.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and select **Try the live demo**. No password is needed for the demo workspace.

The first run creates `data/legalease.db` and per-user upload folders under `data/uploads/`. They are excluded from version control.

## Demo script

1. Open the home page and click **Try the live demo**.
2. Point out the dashboard, private-workspace note, and the seeded agreement.
3. Open the agreement. Explain that the left side is the extracted source text and the right side translates each detected clause into plain language.
4. Click **Indemnity** or **Termination**. The matching original wording is highlighted and scrolled into view.
5. Download the PDF report.
6. Return to the dashboard, upload a real text-based PDF or DOCX, and explain that the same REST flow performs file checks, parsing, analysis and storage.

## REST endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/auth/register` | Create a member account |
| `POST /api/auth/login` | Sign in |
| `POST /api/auth/demo` | Start the seeded demo workspace |
| `GET /api/dashboard` | Return only the signed-in user’s dashboard and documents |
| `POST /api/documents` | Validate, store, extract and analyze a PDF/DOCX upload |
| `POST /api/documents/demo` | Copy the analysis-ready sample agreement into the current account |
| `GET /api/documents/{id}` | Return one owner-scoped document and its source text |
| `GET /api/documents/{id}/report` | Generate a downloadable PDF report |
| `GET /api/admin/audit` | Demonstrates admin-only RBAC enforcement |

All authenticated endpoints expect `Authorization: Bearer <token>`. The browser app handles that automatically.

## How it meets the presentation architecture

| Presentation concept | MVP implementation |
| --- | --- |
| HTML / CSS frontend | Responsive vanilla HTML, CSS and JavaScript in `web/` |
| Python backend | Dependency-light threaded Python HTTP server in `server.py` |
| RESTful API | JSON endpoints shown above |
| NLP / AI engine | Transparent deterministic NLP-style clause engine; a stable local fallback for live demos without network/API credentials |
| OCR / text extraction | Selectable PDF extraction and DOCX structured parsing. A scanned PDF receives a clear “enable an OCR provider” message rather than inventing text. |
| MySQL database | MySQL 8 schema supplied; SQLite uses matching table ownership locally |
| RBAC | Member/admin roles and an admin-only endpoint |
| TLS/SSL | HTTPS deployment toggle (`SECURE_COOKIES`) and headers; terminate TLS at a reverse proxy in production |
| Malware scanning | File size/type/signature gateway placeholder; replace with ClamAV or a managed scanning service for production |
| Data isolation / sandboxing | Per-user database filters and storage folders; no document endpoint reads by ID alone |

## Deployment notes and honest limitations

### Publish a shareable URL with Render

This project is ready for a Render Web Service through the included `render.yaml` file. Render is a better fit than Vercel for this MVP because LegalEase needs a continuously running Python backend for document extraction, analysis, and PDF report generation.

1. Put this project in a GitHub repository (do not add `.env` or anything inside `data/uploads/`).
2. In Render, choose **New +** -> **Blueprint**, connect the repository, and select it.
3. Render reads `render.yaml`, installs the requirements, checks `/api/health`, and starts `python server.py` on its assigned `PORT`.
4. After the deployment is live, copy the generated `https://...onrender.com` address. That is the working link to submit.

For a classroom submission, the free Render plan is usually sufficient. Its filesystem may reset after a service restart, so uploaded files and newly created accounts are temporary. The built-in demo agreement is recreated automatically, ensuring the key presentation flow remains available. Use a persistent disk or managed MySQL/object storage before treating it as a long-term production service.

This is an MVP designed for a college demonstration, not a production legal platform. The local analyzer is explainable and reliable for its known clause patterns, but it is not a lawyer and should never be presented as one. It does **not** call an external AI provider by default, which keeps the demo fast, repeatable and credential-free.

For a production evolution:

1. Replace SQLite with MySQL using the provided schema and a parameterized database driver/ORM.
2. Put the app behind HTTPS (for example, Nginx/Caddy) and enable `SECURE_COOKIES=true`.
3. Run an actual antivirus scanner asynchronously before extraction, and use object storage with encryption-at-rest.
4. Add an approved OCR provider for image-only PDFs and an audited LLM workflow with redaction, guardrails and human review.
5. Move tokens to secure HTTP-only cookies or a managed identity provider, add expiry/refresh, rate limiting and audit logging.

## Project layout

```text
server.py                    Python server, security checks, extraction, analysis and reporting
web/index.html               Application shell
web/styles.css               Presentation-ready styling
web/app.js                   Frontend interactions and API client
database/schema.mysql.sql    MySQL-ready data model
data/sample-service-partner-agreement.txt
requirements.txt             Optional packages for a normal Python installation
.env.example                 Deployment configuration reference
```
