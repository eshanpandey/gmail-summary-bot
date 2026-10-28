"""A local Gmail inbox summarizer powered by a local Ollama model."""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-local-secret")


def gmail_service():
    """Return an authorized Gmail API client, refreshing a saved token when needed."""
    if not TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def header(headers: list[dict], name: str) -> str:
    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")


def decode_body(payload: dict) -> str:
    """Prefer the readable text/plain part, then fall back to HTML stripped to text."""
    parts = payload.get("parts", [])
    candidates = parts or [payload]
    for part in candidates:
        mime = part.get("mimeType", "")
        if mime == "text/plain" and part.get("body", {}).get("data"):
            raw = part["body"]["data"]
            return base64.urlsafe_b64decode(raw + "===").decode("utf-8", errors="replace")
    for part in candidates:
        if part.get("body", {}).get("data"):
            raw = part["body"]["data"]
            text = base64.urlsafe_b64decode(raw + "===").decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", text)
    return ""


def inbox_messages(limit: int = 12) -> list[dict]:
    service = gmail_service()
    if not service:
        raise RuntimeError("Gmail is not connected yet.")
    result = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=limit).execute()
    items = []
    for item in result.get("messages", []):
        message = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        headers = message["payload"].get("headers", [])
        body = decode_body(message["payload"])
        items.append({
            "from": header(headers, "From"),
            "subject": header(headers, "Subject") or "(no subject)",
            "date": header(headers, "Date"),
            "snippet": re.sub(r"\s+", " ", body).strip()[:900] or message.get("snippet", ""),
        })
    return items


def summarize(messages: list[dict], question: str = "") -> tuple[str, dict]:
    """Ask a locally running Ollama model to summarize supplied email snippets."""
    compact_messages = "\n\n".join(
        f"FROM: {m['from']}\nSUBJECT: {m['subject']}\nDATE: {m['date']}\nCONTENT: {m['snippet']}"
        for m in messages
    )
    prompt = (
        "You are a helpful personal inbox assistant. Summarize the supplied emails only. "
        "Highlight urgent items, deadlines, requests, and next actions. Be concise; do not invent facts. "
        f"User question: {question or 'Give me a useful inbox summary.'}\n\nEMAILS:\n{compact_messages}"
    )
    model = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    endpoint = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0.2},
    }
    trace = {
        "gmail_calls": ["users.messages.list(labelIds=INBOX)", "users.messages.get(format=full) × selected emails"],
        "llm_call": {"method": "POST", "url": endpoint, "model": model, "stream": False,
                     "email_count": len(messages), "prompt_characters": len(prompt),
                     "response_field": "message.content"},
    }
    try:
        req = UrlRequest(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError("Cannot reach Ollama. Start Ollama, then run: ollama pull gemma3:1b") from exc
    answer = result.get("message", {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("Ollama returned no message content.")
    return answer, trace


@app.get("/")
def index():
    return render_template("index.html", connected=TOKEN_FILE.exists())


@app.get("/connect")
def connect():
    if not CLIENT_SECRETS_FILE.exists():
        return "Missing credentials.json. Follow the setup instructions in README.md.", 400
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=url_for("oauth_callback", _external=True))
    authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    session["state"] = state
    return redirect(authorization_url)


@app.get("/oauth2callback")
def oauth_callback():
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=session["state"], redirect_uri=url_for("oauth_callback", _external=True))
    flow.fetch_token(authorization_response=request.url)
    TOKEN_FILE.write_text(flow.credentials.to_json(), encoding="utf-8")
    return redirect(url_for("index"))


@app.post("/api/summary")
def api_summary():
    try:
        payload = request.get_json(silent=True) or {}
        limit = min(max(int(payload.get("limit", 12)), 1), 25)
        messages = inbox_messages(limit)
        summary, trace = summarize(messages, payload.get("question", ""))
        return jsonify({"summary": summary, "count": len(messages), "trace": trace})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/disconnect")
def disconnect():
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(port=5000)
