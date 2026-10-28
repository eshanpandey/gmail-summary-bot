# Inbox Brief — local Gmail summary assistant

Inbox Brief is a small, local web app that reads recent Gmail inbox messages and asks a free, locally running AI model to turn them into a short executive summary.

It is deliberately Gmail-only for this first version. It is a learning project that makes the backend-to-LLM API call visible in the UI.

## What it does

- Connects to Gmail through Google OAuth; it never asks for your Gmail password.
- Requests **read-only** Gmail access.
- Retrieves up to 25 inbox messages, with email bodies trimmed before summarization.
- Sends the selected text to Ollama at `http://127.0.0.1:11434/api/chat`.
- Uses the free local model `gemma3:1b` by default.
- Shows safe request metadata (endpoint, model, message count, and response field) after each summary.

## How a summary request flows

```text
Browser prompt
    │ POST /api/summary
    ▼
Flask backend (app.py)
    │ Gmail API: list unread/recent messages, then fetch message details
    ▼
Email snippets (local memory only)
    │ POST http://127.0.0.1:11434/api/chat
    ▼
Ollama + gemma3:1b (on your computer)
    │ returns summary text
    ▼
Flask returns JSON → browser displays the summary and API trace
```

For the detailed component design and route-level API flow, see [LLD.md](LLD.md).

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download)
- A Google Cloud project with the Gmail API enabled

## 1. Create Google OAuth credentials

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a project and enable the **Gmail API**.
2. Configure the OAuth consent screen. Add your Gmail address as a test user if the app is in testing mode.
3. Create an **OAuth client ID** for a **Web application**.
4. Add this authorized redirect URI exactly: `http://localhost:5000/oauth2callback`.
5. Download the client JSON file and save it in this project folder as `credentials.json`.

## 2. Configure and run

```powershell
cd "C:\Users\Eshan'spc\Documents\Codex\2026-10-29\we\outputs\gmail-summary-bot"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull gemma3:1b
python app.py
```

Open `http://localhost:5000`, choose **Connect Gmail**, and approve read-only access.

## Quick start and clean shutdown

After creating `.venv` and installing requirements, start the local services with:

```powershell
.\Start-App.ps1
```

When you are done, stop them with:

```powershell
.\Stop-App.ps1
```

`Stop-App.ps1` stops only processes whose IDs were recorded by this project. It does not stop an Ollama service that was already running before the app started.

For a complete local shutdown (including an already-running Ollama service), use `./Stop-App.ps1 -StopAllOllama`.

## Local AI model

Install and start [Ollama](https://ollama.com/download), then download the model:

```powershell
ollama pull gemma3:1b
```

The application sends selected email snippets to Ollama on your own computer. Expand **Show backend and LLM API calls** in the UI to inspect the safe request metadata after every summary.

## Project layout

```text
app.py                 Flask routes, Gmail integration, and Ollama request
templates/index.html   Browser chat interface and API trace panel
LLD.md                 Low-level design and sequence diagrams
Start-App.ps1          Starts Flask and Ollama when needed
Stop-App.ps1           Stops the local services started for this project
```

## Security notes

- `credentials.json`, `.env`, and `token.json` are ignored by Git.
- Email snippets go from the local Flask app to local Ollama only; they are not sent to a hosted LLM provider.
- Use a personal Google Cloud OAuth app for personal mail; do not share its downloaded credential file.
- Disconnecting deletes the local saved OAuth token. You can additionally revoke access from your Google Account security page.

## Limitations and next steps

This prototype summarizes mail only. It does not send email, create calendar events, or connect Slack. Those actions should be added later behind explicit user approval and more narrowly scoped OAuth permissions.
