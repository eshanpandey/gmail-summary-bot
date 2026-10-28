# Low-level design: Inbox Brief

## Goal

Inbox Brief is a local web application. It lets one user authenticate with Gmail, fetch a limited number of inbox emails, and ask a local LLM to summarize them or answer an inbox question.

The model setup is **Ollama + `gemma3:1b`**. Both run on the user's computer, so the email content is not sent to an AI provider.

## Components

| Component | Responsibility | Data it holds |
|---|---|---|
| Browser | Displays chat UI and starts requests | Prompt, selected email limit, rendered answer |
| Flask (`app.py`) | Auth, Gmail read, prompt construction, API endpoints | Temporary OAuth state; no email database |
| `credentials.json` | Identifies this app to Google OAuth | Google OAuth client ID/secret |
| `token.json` | Authorizes future Gmail reads | User's refresh/access token; local only |
| Gmail API | Lists and returns inbox email messages | User's Gmail mailbox |
| Ollama | Runs an LLM HTTP server at `localhost:11434` | Downloaded model and current prompt only |
| Gemma 3 1B | Turns retrieved email snippets into a response | Context supplied in one request |

## Runtime flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Browser
    participant App as Flask app (localhost:5000)
    participant Google as Google OAuth / Gmail API
    participant LLM as Ollama (localhost:11434)

    User->>UI: Click "Connect Gmail"
    UI->>App: GET /connect
    App->>Google: OAuth authorization request
    Google->>User: Google sign-in and consent screen
    Google->>App: GET /oauth2callback?code=...
    App->>App: Save authorized token as token.json

    User->>UI: Ask "What needs attention today?"
    UI->>App: POST /api/summary {question, limit}
    App->>Google: List latest INBOX message IDs
    App->>Google: Get full content for each selected ID
    Google-->>App: Headers + message bodies
    App->>App: Extract From, Subject, Date, text snippet
    App->>LLM: POST /api/chat with instructions + email snippets
    LLM-->>App: Plain-text summary
    App-->>UI: {summary, count}
    UI-->>User: Render summary
```

## Request-level design

### `GET /`

Renders `templates/index.html`. It checks whether `token.json` exists and shows either **Connect Gmail** or the chat panel.

### `GET /connect`

1. Reads local `credentials.json`.
2. Creates a Google OAuth authorization URL with the sole scope `gmail.readonly`.
3. Saves an anti-forgery `state` value in the Flask session.
4. Redirects the browser to Google.

### `GET /oauth2callback`

1. Confirms the OAuth state.
2. Exchanges the received authorization code for credentials.
3. Writes credentials to `token.json`.
4. Redirects to `/`.

### `POST /api/summary`

Input:

```json
{ "question": "Which email is urgent?", "limit": 12 }
```

Processing:

1. Clamp `limit` to 1–25.
2. Refresh the stored Google token if needed.
3. Call `users.messages.list` with `labelIds=INBOX`.
4. For each selected ID, call `users.messages.get(format=full)`.
5. Extract `From`, `Subject`, and `Date` headers; decode `text/plain` content (or fall back to stripped HTML).
6. Trim every message body to a fixed length before it goes to the model.
7. Send a strict prompt to Ollama: summarize only supplied emails, highlight deadlines/actions, and do not invent facts.
8. Return the generated answer.

Output:

```json
{ "summary": "• Follow up with…", "count": 12 }
```

### `POST /disconnect`

Deletes only the local `token.json` file and returns to `/`. For complete revocation, the user can also remove the app from their Google Account permissions.

## Data boundaries

```mermaid
flowchart LR
  A["Gmail inbox"] -->|"Read-only OAuth API"| B["Flask app"]
  B -->|"selected email snippets"| C["Ollama on localhost"]
  C -->|"summary text"| B
  B -->|"JSON"| D["Browser"]
  E["credentials.json + token.json"] -. "local files" .-> B

  classDef local fill:#e9f8ee,stroke:#3c9d67,color:#163d27;
  classDef external fill:#fff3e2,stroke:#d18a27,color:#573000;
  class B,C,D,E local;
  class A external;
```

With Ollama, email snippets never leave the machine after Gmail returns them. Google still sees normal OAuth and Gmail API activity. If the app uses Gemini/OpenAI/Groq instead, the snippet bundle is transmitted to that provider; this must be opt-in and clearly disclosed in the UI.

## Code changes for Ollama

`summarize()` makes this local HTTP call:

```python
from urllib.request import Request, urlopen

request = Request(
    "http://127.0.0.1:11434/api/chat",
    data=json.dumps({
        "model": "gemma3:1b",
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urlopen(request, timeout=120) as response:
    answer = json.loads(response.read())["message"]["content"]
```

The UI exposes a safe API trace after each request: Gmail method names, Ollama endpoint, model, email count, and prompt size. It deliberately never displays full email content in this trace. The app should return a clear error if Ollama is not running. Model output remains a suggestion: display the source sender and subject in the summary when practical, and do not take autonomous actions such as deleting, sending, or archiving email.

## Failure behavior

| Failure | App response |
|---|---|
| No `credentials.json` | Explain Google OAuth setup is incomplete |
| No `token.json` | Show Connect Gmail button |
| Expired token | Refresh it automatically; ask user to reconnect if refresh fails |
| Gmail API error | Return a human-readable failure; do not expose token data |
| Ollama offline/model missing | Return “Start Ollama and run `ollama pull gemma3:1b`” |
| Oversized inbox payload | Limit email count and per-message text before inference |

## Local setup topology

```text
Browser ──────────── http://localhost:5000 ─────────── Flask
                                                        │
Google OAuth / Gmail API ──────────────────────────────┤
                                                        │
Flask ───────────── http://localhost:11434 ─────────── Ollama + gemma3:1b
```
