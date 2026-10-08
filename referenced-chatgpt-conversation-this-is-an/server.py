"""LegalEase - a dependency-light demonstration backend.

Run with: python server.py
The app uses SQLite locally, mirrors a MySQL-ready schema in database/schema.mysql.sql,
and exposes a small REST API consumed by the vanilla HTML/CSS/JavaScript frontend.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

try:
    from pypdf import PdfReader
except ImportError:  # The interface still runs; PDF extraction reports a helpful error.
    PdfReader = None

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:
    colors = None


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "legalease.db"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Cloud hosts conventionally inject PORT and require binding to every interface.
# LEGALEASE_* remains available for an explicit local override.
HOST = os.getenv("LEGALEASE_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("LEGALEASE_PORT", "8000")))
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() == "true"
ANALYSIS_MODE = os.getenv("ANALYSIS_MODE", "local").lower()

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
SESSIONS: dict[str, dict] = {}
SESSION_LOCK = threading.Lock()


SAMPLE_CONTRACT = """SERVICE PARTNER AGREEMENT

This Service Partner Agreement (the \"Agreement\") is entered into between Northstar Retail Pvt. Ltd. (\"Company\") and Studio Atlas (\"Service Partner\") on 1 October 2026.

1. SERVICES AND PAYMENT
The Service Partner will provide product-design services described in the approved statement of work. The Company will pay approved invoices within 45 days of receipt. The Company may withhold payment for work it reasonably believes is incomplete.

2. CONFIDENTIALITY
Each party must keep the other party's non-public business, customer and technical information confidential during this Agreement and for two years after it ends. Information that is publicly available through no fault of the receiving party is excluded.

3. LIABILITY
The Service Partner's total liability for any claim connected with this Agreement is limited to the fees paid under this Agreement during the previous three months. The Company will not be liable for indirect, special, punitive or consequential damages.

4. INDEMNITY
The Service Partner shall indemnify, defend and hold harmless the Company, its affiliates and their officers from all claims, losses, liabilities, costs and expenses, including reasonable legal fees, arising from any alleged infringement or breach by the Service Partner. This obligation is unlimited.

5. TERM, RENEWAL AND TERMINATION
This Agreement starts on the effective date and continues for 12 months. It will automatically renew for successive 12-month periods unless either party gives 60 days' written notice before the end of the current term. The Company may terminate this Agreement immediately, in its sole discretion, if it believes the Service Partner has breached any obligation. The Service Partner may terminate only after giving 90 days' written notice.

6. LATE DELIVERY PENALTY
If a deliverable is late, the Company may charge a penalty of 2% of the monthly fees for each week of delay, without limiting any other remedies available to the Company.

7. GOVERNING LAW
This Agreement is governed by the laws of India. Courts in Bengaluru will have exclusive jurisdiction.
"""

RULES = {
    "liability": {
        "label": "Liability", "patterns": [r"\bliabilit(?:y|ies)\b", r"consequential damages", r"limitation of liability"],
        "plain": "This sets the financial responsibility each side may have if something goes wrong.",
        "watch": "Check whether the cap applies fairly to both sides and whether important losses are excluded.",
        "next": "Compare the liability cap with the value and risk of the work.",
    },
    "indemnity": {
        "label": "Indemnity", "patterns": [r"\bindemnif", r"hold harmless", r"defend and hold"],
        "plain": "This can make one side pay or defend the other side against certain third-party claims.",
        "watch": "Broad or unlimited indemnity can create costs that are hard to predict.",
        "next": "Ask who is covered, which claims apply, and whether there is a sensible limit.",
    },
    "termination": {
        "label": "Termination", "patterns": [r"\bmay terminate", r"\bterminat", r"end this agreement", r"written notice"],
        "plain": "This explains how and when either side can end the agreement.",
        "watch": "Unequal notice periods or one-sided immediate termination can reduce your flexibility.",
        "next": "Check the notice period, cure opportunity, and any work or payments due after termination.",
    },
    "penalty": {
        "label": "Penalty", "patterns": [r"\bpenalt", r"late fee", r"liquidated damages", r"charge .*%"],
        "plain": "This creates an extra financial consequence if a stated obligation is not met.",
        "watch": "A percentage that repeats weekly or sits alongside other remedies can add up quickly.",
        "next": "Confirm the calculation, any maximum amount, and whether delays outside your control are excluded.",
    },
    "renewal": {
        "label": "Renewal", "patterns": [r"automatic(?:ally)? renew", r"successive.*period", r"renewal"],
        "plain": "This says what happens when the original contract period ends.",
        "watch": "Automatic renewal may lock you in unless you cancel within a fixed window.",
        "next": "Calendar the non-renewal deadline and check whether price or terms can change on renewal.",
    },
    "confidentiality": {
        "label": "Confidentiality", "patterns": [r"\bconfidential", r"non-public", r"keep.*information"],
        "plain": "This controls how private business information may be used, shared and protected.",
        "watch": "Look for a clear definition, reasonable exclusions, and a practical time limit.",
        "next": "Confirm that the information you need to use is covered by reasonable exceptions.",
    },
    "payment": {
        "label": "Payment", "patterns": [r"\bpayment", r"\binvoice", r"\bfees?\b", r"withhold payment"],
        "plain": "This describes when payment is due and any conditions that can delay it.",
        "watch": "Long payment windows or broad withholding rights can affect cash flow.",
        "next": "Confirm due dates, acceptance criteria, taxes, and a process for disputed invoices.",
    },
    "governing_law": {
        "label": "Governing law", "patterns": [r"governed by", r"jurisdiction", r"courts? in"],
        "plain": "This identifies the law and courts that will handle disputes.",
        "watch": "A distant or exclusive court can make a dispute more expensive to manage.",
        "next": "Make sure the chosen forum is workable for both parties.",
    },
}

HIGH_SIGNALS = [
    r"\bunlimited\b", r"sole discretion", r"immediately", r"without notice", r"all claims",
    r"all losses", r"any and all", r"without limiting", r"exclusive jurisdiction", r"may withhold",
]
MEDIUM_SIGNALS = [r"automatically renew", r"\b60 days?\b", r"\b90 days?\b", r"penalty", r"withhold payment", r"previous three months"]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('member', 'admin')),
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL,
              filename TEXT NOT NULL,
              stored_path TEXT,
              mime_type TEXT NOT NULL,
              extracted_text TEXT NOT NULL,
              summary TEXT NOT NULL,
              analysis_json TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'ready',
              engine TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_documents_owner_created ON documents(user_id, created_at DESC);
            """
        )
        existing = db.execute("SELECT id FROM users WHERE email = ?", ("demo@legalease.local",)).fetchone()
        if not existing:
            cursor = db.execute(
                "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                ("Aarav Mehta", "demo@legalease.local", hash_password("demo-only"), "member", utcnow()),
            )
            demo_user_id = cursor.lastrowid
        else:
            demo_user_id = existing["id"]
        seed_demo_document(db, demo_user_id)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algorithm, salt_hex, digest_hex = stored.split("$", 2)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 210_000)
        return hmac.compare_digest(computed.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def seed_demo_document(db: sqlite3.Connection, user_id: int) -> None:
    existing = db.execute("SELECT id FROM documents WHERE user_id = ? AND filename = ?", (user_id, "Northstar Service Partner Agreement")).fetchone()
    if existing:
        # Keep the starter document in sync with improvements to the local review rules.
        analysis = analyze_text(SAMPLE_CONTRACT)
        db.execute("UPDATE documents SET extracted_text = ?, summary = ?, analysis_json = ?, engine = ? WHERE id = ?",
                   (SAMPLE_CONTRACT, analysis["summary"], json.dumps(analysis), "Local NLP fallback", existing["id"]))
        return
    analysis = analyze_text(SAMPLE_CONTRACT)
    db.execute(
        """INSERT INTO documents (id, user_id, filename, stored_path, mime_type, extracted_text, summary, analysis_json, engine, created_at)
           VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), user_id, "Northstar Service Partner Agreement", "text/plain", SAMPLE_CONTRACT,
         analysis["summary"], json.dumps(analysis), "Local NLP fallback", utcnow()),
    )


def severity_for(category: str, excerpt: str) -> tuple[str, int, list[str]]:
    base = {"indemnity": 54, "penalty": 52, "termination": 43, "liability": 42, "renewal": 40,
            "payment": 38, "confidentiality": 30, "governing_law": 30}.get(category, 35)
    matched_high = [signal for signal in HIGH_SIGNALS if re.search(signal, excerpt, re.IGNORECASE)]
    matched_medium = [signal for signal in MEDIUM_SIGNALS if re.search(signal, excerpt, re.IGNORECASE)]
    score = min(96, base + len(matched_high) * 18 + len(matched_medium) * 8)
    if score >= 72:
        return "High", score, [re.sub(r"\\b|\\s\*", "", m) for m in matched_high[:2]]
    if score >= 48:
        return "Medium", score, [re.sub(r"\\b|\\s\*", "", m) for m in (matched_high + matched_medium)[:2]]
    return "Low", score, ["standard clause language"]


def paragraph_spans(text: str) -> list[tuple[int, int, str]]:
    spans = []
    for match in re.finditer(r"[^\n](?:.*?)(?=\n\s*\n|\Z)", text, re.DOTALL):
        start, end = match.span()
        value = text[start:end].strip()
        if value:
            leading = len(match.group(0)) - len(match.group(0).lstrip())
            spans.append((start + leading, start + leading + len(value), value))
    if not spans and text.strip():
        spans.append((0, len(text.strip()), text.strip()))
    return spans


def clean_excerpt(value: str, max_length: int = 440) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= max_length else value[:max_length].rsplit(" ", 1)[0] + "..."


def focused_clause_span(start: int, paragraph: str, match: re.Match | None, category: str) -> tuple[int, int, str]:
    """Use a sentence-sized source range when two clause types share one section."""
    if not match or category not in {"termination", "renewal"}:
        return start, start + len(paragraph), paragraph
    before_match = paragraph[:match.start()]
    sentence_breaks = list(re.finditer(r"[.!?]\s+", before_match))
    relative_start = sentence_breaks[-1].end() if sentence_breaks else 0
    # A heading can precede the first sentence. Drop it when we can identify the first sentence after it.
    if relative_start == 0 and "\n" in before_match:
        relative_start = before_match.rfind("\n") + 1
    after_match = paragraph[match.end():]
    ending = re.search(r"[.!?](?:\s|$)", after_match)
    relative_end = match.end() + (ending.end() if ending else len(after_match))
    excerpt = paragraph[relative_start:relative_end].strip()
    leading = len(paragraph[relative_start:relative_end]) - len(paragraph[relative_start:relative_end].lstrip())
    return start + relative_start + leading, start + relative_start + leading + len(excerpt), excerpt


def analyze_text(text: str) -> dict:
    """Deterministic NLP-style fallback suitable for a reliable offline classroom demo."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    spans = paragraph_spans(normalized)
    clauses = []
    used_ranges: set[tuple[int, int]] = set()

    for category, rule in RULES.items():
        found = None
        for start, end, paragraph in spans:
            pattern_match = next((re.search(pattern, paragraph, re.IGNORECASE) for pattern in rule["patterns"] if re.search(pattern, paragraph, re.IGNORECASE)), None)
            if pattern_match:
                found = focused_clause_span(start, paragraph, pattern_match, category)
                break
        if found is None:
            keyword_match = next((re.search(pattern, normalized, re.IGNORECASE) for pattern in rule["patterns"]), None)
            if keyword_match:
                start = max(0, normalized.rfind("\n", 0, keyword_match.start()) + 1)
                end = min(len(normalized), normalized.find("\n", keyword_match.end()) if normalized.find("\n", keyword_match.end()) != -1 else len(normalized))
                found = (start, end, normalized[start:end].strip())
        if not found:
            continue
        start, end, excerpt = found
        if (start, end) in used_ranges:
            continue
        used_ranges.add((start, end))
        severity, score, signals = severity_for(category, excerpt)
        clauses.append({
            "id": category,
            "category": category,
            "title": rule["label"],
            "risk": severity,
            "score": score,
            "source_start": start,
            "source_end": end,
            "excerpt": clean_excerpt(excerpt),
            "plain_english": rule["plain"],
            "why_it_matters": rule["watch"],
            "next_step": rule["next"],
            "signals": signals,
            "missing": False,
        })

    clauses.sort(key=lambda item: (-item["score"], item["source_start"]))
    present = {item["category"] for item in clauses}
    if "confidentiality" not in present:
        clauses.append({
            "id": "confidentiality-missing", "category": "confidentiality", "title": "Confidentiality", "risk": "Medium",
            "score": 50, "source_start": None, "source_end": None, "excerpt": "No clearly labelled confidentiality provision was detected.",
            "plain_english": "The document does not appear to set clear rules for handling confidential information.",
            "why_it_matters": "Sensitive commercial or personal information may not be protected by a specific written obligation.",
            "next_step": "Confirm whether a separate confidentiality agreement or data-protection clause is needed.",
            "signals": ["missing clause"], "missing": True,
        })

    high = sum(1 for clause in clauses if clause["risk"] == "High")
    medium = sum(1 for clause in clauses if clause["risk"] == "Medium")
    low = sum(1 for clause in clauses if clause["risk"] == "Low")
    coverage = min(100, max(35, 100 - high * 13 - medium * 6 + low * 2))
    summary = (
        f"LegalEase identified {len(clauses)} clauses to review: {high} high-risk, {medium} medium-risk and {low} low-risk. "
        "Use this informational summary to prepare questions before obtaining professional advice."
    )
    return {"clauses": clauses, "summary": summary, "score": coverage, "counts": {"high": high, "medium": medium, "low": low},
            "mode": "Local NLP fallback" if ANALYSIS_MODE != "ai" else "AI-assisted review"}


def parse_docx(file_path: Path) -> str:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(file_path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = []
    for paragraph in root.iter(namespace + "p"):
        words = [node.text for node in paragraph.iter(namespace + "t") if node.text]
        if words:
            paragraphs.append("".join(words))
    return "\n\n".join(paragraphs)


def extract_text(file_path: Path, suffix: str) -> str:
    if suffix == ".docx":
        return parse_docx(file_path)
    if suffix == ".pdf":
        if PdfReader is None:
            raise ValueError("PDF support is unavailable. Install the packages in requirements.txt and restart the app.")
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            raise ValueError("This PDF is encrypted. Upload an unlocked copy for this demonstration.")
        content = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        if len(content.strip()) < 40:
            raise ValueError("No selectable text was found. This looks like a scanned PDF; enable an OCR provider for it.")
        return content
    raise ValueError("Only PDF and DOCX files are supported.")


def to_document(row: sqlite3.Row, detailed: bool = False) -> dict:
    analysis = json.loads(row["analysis_json"])
    result = {
        "id": row["id"], "filename": row["filename"], "mime_type": row["mime_type"], "status": row["status"],
        "summary": row["summary"], "analysis": analysis, "engine": row["engine"], "created_at": row["created_at"],
    }
    if detailed:
        result["text"] = row["extracted_text"]
    return result


def make_report(document: dict) -> bytes:
    if colors is None:
        raise ValueError("PDF reporting is unavailable. Install the packages in requirements.txt and restart the app.")
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    title = ParagraphStyle("LegalEaseTitle", parent=styles["Title"], textColor=colors.HexColor("#112A46"), fontSize=24, leading=29)
    eyebrow = ParagraphStyle("Eyebrow", parent=styles["Normal"], textColor=colors.HexColor("#138A7E"), fontSize=9, leading=12, spaceAfter=7)
    clause_title = ParagraphStyle("ClauseTitle", parent=styles["Heading3"], textColor=colors.HexColor("#112A46"), spaceAfter=5)
    body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontSize=9.5, leading=14, textColor=colors.HexColor("#26364A"))
    note = ParagraphStyle("Note", parent=body, backColor=colors.HexColor("#FFF6E8"), borderColor=colors.HexColor("#F4B860"), borderWidth=0.5, borderPadding=8)
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    analysis = document["analysis"]
    story = [Paragraph("LEGALEASE | INFORMATIONAL REVIEW", eyebrow), Paragraph("Legal document review report", title), Spacer(1, 7)]
    story.append(Paragraph(f"<b>Document:</b> {escape_pdf(document['filename'])}<br/><b>Prepared:</b> {datetime.now().strftime('%d %b %Y, %I:%M %p')}<br/><b>Analysis engine:</b> {escape_pdf(document['engine'])}", body))
    story += [Spacer(1, 12), Paragraph("This report is an informational aid, not legal advice. Consult a qualified legal professional before signing or acting on a document.", note), Spacer(1, 14)]
    count = analysis["counts"]
    cards = [[f"{analysis['score']}\nReview score", f"{count['high']}\nHigh priority", f"{count['medium']}\nMedium priority", f"{len(analysis['clauses'])}\nReview items"]]
    table = Table(cards, colWidths=[42*mm]*4, rowHeights=[21*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#EAF5F3")), ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor("#112A46")),
        ("ALIGN", (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#B8DDDA")),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 10),
    ]))
    story += [table, Spacer(1, 15), Paragraph("Executive summary", styles["Heading2"]), Paragraph(escape_pdf(document["summary"]), body), Spacer(1, 12), Paragraph("Clause-by-clause review", styles["Heading2"])]
    for index, clause in enumerate(analysis["clauses"], 1):
        risk_color = {"High": "#B42318", "Medium": "#B54708", "Low": "#18794E"}.get(clause["risk"], "#112A46")
        content = [Paragraph(f"{index}. {escape_pdf(clause['title'])} <font color='{risk_color}'>- {escape_pdf(clause['risk']).upper()} PRIORITY</font>", clause_title)]
        content.append(Paragraph(f"<b>What it says:</b> {escape_pdf(clause['excerpt'])}", body))
        content.append(Paragraph(f"<b>In plain language:</b> {escape_pdf(clause['plain_english'])}", body))
        content.append(Paragraph(f"<b>What to check:</b> {escape_pdf(clause['why_it_matters'])}", body))
        content.append(Paragraph(f"<b>Suggested next step:</b> {escape_pdf(clause['next_step'])}", body))
        content.append(Spacer(1, 9))
        story.append(KeepTogether(content))
    doc.build(story)
    return output.getvalue()


def escape_pdf(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_multipart(content_type: str, body: bytes) -> dict[str, dict]:
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type, re.IGNORECASE)
    if not match:
        raise ValueError("The upload form did not include a multipart boundary.")
    boundary = (match.group(1) or match.group(2)).encode("utf-8")
    fields: dict[str, dict] = {}
    for piece in body.split(b"--" + boundary):
        piece = piece.strip(b"\r\n")
        if not piece or piece == b"--" or b"\r\n\r\n" not in piece:
            continue
        header_blob, value = piece.split(b"\r\n\r\n", 1)
        header_text = header_blob.decode("utf-8", "replace")
        disposition = next((line for line in header_text.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'\bname="([^"]+)"', disposition)
        if not name_match:
            continue
        filename_match = re.search(r'\bfilename="([^"]*)"', disposition)
        fields[name_match.group(1)] = {"filename": filename_match.group(1) if filename_match else None, "content": value.rstrip(b"\r\n"), "headers": header_text}
    return fields


class LegalEaseHandler(BaseHTTPRequestHandler):
    server_version = "LegalEase/1.0"

    def log_message(self, format: str, *args) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} - {format % args}")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # Keep the local demonstration responsive to UI changes without a hard refresh.
        # A production build can replace this with fingerprinted static assets and long-lived caching.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, message: str, status: int = 400, hint: str | None = None) -> None:
        payload = {"error": message}
        if hint:
            payload["hint"] = hint
        self.send_json(payload, status)

    def read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_UPLOAD_BYTES + 1_000_000:
            raise ValueError("The request is too large. Documents must be 10 MB or smaller.")
        return self.rfile.read(length)

    def read_json(self) -> dict:
        try:
            return json.loads(self.read_body().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Please send valid JSON.")

    def current_user(self) -> dict | None:
        token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            return None
        with SESSION_LOCK:
            return SESSIONS.get(token)

    def require_user(self) -> dict | None:
        user = self.current_user()
        if not user:
            self.send_error_json("Sign in to continue.", HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def issue_session(self, row: sqlite3.Row) -> dict:
        token = secrets.token_urlsafe(32)
        user = {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]}
        with SESSION_LOCK:
            SESSIONS[token] = user
        return {"token": token, "user": user, "security": {"secure_cookie_ready": SECURE_COOKIES}}

    def find_owned_document(self, document_id: str, user_id: int) -> sqlite3.Row | None:
        # Ownership is always part of the lookup: application-level logical data isolation.
        with get_db() as db:
            return db.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id)).fetchone()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            return self.send_json({"status": "ok", "service": "LegalEase", "analysis_mode": ANALYSIS_MODE})
        if path == "/api/me":
            user = self.require_user()
            return self.send_json({"user": user}) if user else None
        if path == "/api/dashboard":
            user = self.require_user()
            if not user:
                return
            with get_db() as db:
                documents = db.execute("SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)).fetchall()
            items = [to_document(row) for row in documents]
            counts = {"documents": len(items), "high": sum(item["analysis"]["counts"]["high"] for item in items),
                      "clauses": sum(len(item["analysis"]["clauses"]) for item in items)}
            return self.send_json({"user": user, "documents": items, "stats": counts, "informational_notice": "LegalEase provides informational review, not legal advice."})
        if path == "/api/documents":
            user = self.require_user()
            if not user:
                return
            with get_db() as db:
                rows = db.execute("SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)).fetchall()
            return self.send_json({"documents": [to_document(row) for row in rows]})
        if path.startswith("/api/documents/") and path.endswith("/report"):
            user = self.require_user()
            if not user:
                return
            document_id = path.split("/")[3]
            row = self.find_owned_document(document_id, user["id"])
            if not row:
                return self.send_error_json("Document not found.", HTTPStatus.NOT_FOUND)
            try:
                content = make_report(to_document(row, detailed=True))
            except ValueError as error:
                return self.send_error_json(str(error), HTTPStatus.SERVICE_UNAVAILABLE)
            filename = re.sub(r"[^A-Za-z0-9._-]+", "-", row["filename"]).strip("-") or "LegalEase-report"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="LegalEase-{filename}.pdf"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            return self.wfile.write(content)
        if path.startswith("/api/documents/"):
            user = self.require_user()
            if not user:
                return
            document_id = path.rsplit("/", 1)[-1]
            row = self.find_owned_document(document_id, user["id"])
            return self.send_json({"document": to_document(row, detailed=True)}) if row else self.send_error_json("Document not found.", HTTPStatus.NOT_FOUND)
        if path == "/api/admin/audit":
            user = self.require_user()
            if not user:
                return
            if user["role"] != "admin":
                return self.send_error_json("This view requires the admin role.", HTTPStatus.FORBIDDEN)
            return self.send_json({"message": "Role-based access control is active.", "audit": []})
        return self.serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/auth/demo":
                with get_db() as db:
                    row = db.execute("SELECT * FROM users WHERE email = ?", ("demo@legalease.local",)).fetchone()
                return self.send_json(self.issue_session(row))
            if path == "/api/auth/register":
                data = self.read_json()
                name = str(data.get("name", "")).strip()
                email = str(data.get("email", "")).lower().strip()
                password = str(data.get("password", ""))
                if len(name) < 2 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or len(password) < 8:
                    return self.send_error_json("Enter your name, a valid email, and a password with at least 8 characters.")
                try:
                    with get_db() as db:
                        cursor = db.execute("INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'member', ?)",
                                            (name, email, hash_password(password), utcnow()))
                        row = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
                    return self.send_json(self.issue_session(row), HTTPStatus.CREATED)
                except sqlite3.IntegrityError:
                    return self.send_error_json("An account already exists for that email. Sign in instead.", HTTPStatus.CONFLICT)
            if path == "/api/auth/login":
                data = self.read_json()
                email = str(data.get("email", "")).lower().strip()
                password = str(data.get("password", ""))
                with get_db() as db:
                    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if not row or not verify_password(password, row["password_hash"]):
                    return self.send_error_json("Incorrect email or password.", HTTPStatus.UNAUTHORIZED)
                return self.send_json(self.issue_session(row))
            if path == "/api/auth/logout":
                token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                with SESSION_LOCK:
                    SESSIONS.pop(token, None)
                return self.send_json({"ok": True})
            if path == "/api/documents/demo":
                user = self.require_user()
                if not user:
                    return
                # A fresh, user-owned copy lets the seeded agreement work in every account.
                analysis = analyze_text(SAMPLE_CONTRACT)
                document_id = str(uuid.uuid4())
                with get_db() as db:
                    db.execute("""INSERT INTO documents (id, user_id, filename, stored_path, mime_type, extracted_text, summary, analysis_json, engine, created_at)
                        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)""",
                        (document_id, user["id"], "Northstar Service Partner Agreement", "text/plain", SAMPLE_CONTRACT,
                         analysis["summary"], json.dumps(analysis), "Local NLP fallback", utcnow()))
                    row = db.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user["id"])).fetchone()
                return self.send_json({"document": to_document(row, detailed=True)}, HTTPStatus.CREATED)
            if path == "/api/documents":
                user = self.require_user()
                if not user:
                    return
                return self.handle_upload(user)
            return self.send_error_json("Endpoint not found.", HTTPStatus.NOT_FOUND)
        except ValueError as error:
            return self.send_error_json(str(error))
        except Exception as error:  # Never expose internals in a student demonstration deployment.
            print(f"Unhandled error: {error!r}")
            return self.send_error_json("Something went wrong while processing that request. Please try again.", HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_upload(self, user: dict) -> None:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            return self.send_error_json("Upload a document using the form uploader.")
        fields = parse_multipart(content_type, self.read_body())
        incoming = fields.get("document")
        if not incoming or not incoming.get("filename"):
            return self.send_error_json("Choose a PDF or DOCX file first.")
        raw_name = incoming["filename"]
        filename = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(raw_name).name).strip()[:120]
        content = incoming["content"]
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            return self.send_error_json("LegalEase accepts PDF or DOCX documents only.")
        if not content or len(content) > MAX_UPLOAD_BYTES:
            return self.send_error_json("The document must be between 1 byte and 10 MB.")
        # Demonstration malware-validation gateway. Replace this small signature check with an AV service in production.
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content.upper() or b"X5O!P%@AP" in content.upper():
            return self.send_error_json("Upload blocked by the malware validation gateway.", HTTPStatus.UNPROCESSABLE_ENTITY)
        if suffix == ".pdf" and not content.startswith(b"%PDF"):
            return self.send_error_json("The file extension says PDF, but its contents do not look like a PDF.")
        if suffix == ".docx" and not zipfile.is_zipfile(io.BytesIO(content)):
            return self.send_error_json("The file extension says DOCX, but its contents do not look like a DOCX document.")
        owner_dir = UPLOAD_DIR / f"user-{user['id']}"
        owner_dir.mkdir(exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        stored_path = owner_dir / stored_name
        stored_path.write_bytes(content)
        try:
            extracted = extract_text(stored_path, suffix)
            if len(extracted.strip()) < 40:
                raise ValueError("The document did not contain enough readable text to analyze.")
            analysis = analyze_text(extracted)
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise
        document_id = str(uuid.uuid4())
        mime_type = "application/pdf" if suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        with get_db() as db:
            db.execute("""INSERT INTO documents (id, user_id, filename, stored_path, mime_type, extracted_text, summary, analysis_json, engine, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document_id, user["id"], filename, str(stored_path.relative_to(ROOT)), mime_type, extracted,
                 analysis["summary"], json.dumps(analysis), "Local NLP fallback", utcnow()))
            row = db.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user["id"])).fetchone()
        return self.send_json({"document": to_document(row, detailed=True)}, HTTPStatus.CREATED)

    def serve_static(self, path: str) -> None:
        requested = "index.html" if path in {"/", ""} else path.lstrip("/")
        safe_path = (WEB_DIR / requested).resolve()
        if WEB_DIR.resolve() not in safe_path.parents and safe_path != WEB_DIR.resolve():
            return self.send_error_json("Not found.", HTTPStatus.NOT_FOUND)
        if not safe_path.is_file():
            return self.serve_file(WEB_DIR / "index.html") if "." not in Path(requested).name else self.send_error_json("Not found.", HTTPStatus.NOT_FOUND)
        return self.serve_file(safe_path)

    def serve_file(self, file_path: Path) -> None:
        content_types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml"}
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_types.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    init_db()
    print("\nLegalEase is ready")
    print(f"Open http://{HOST}:{PORT}")
    print("Use Demo access for a presentation-ready account. Press Ctrl+C to stop.\n")
    try:
        ThreadingHTTPServer((HOST, PORT), LegalEaseHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nLegalEase stopped.")
