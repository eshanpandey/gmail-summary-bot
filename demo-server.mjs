import http from "node:http";

const demoEmails = [
  { from: "Sarah Kim", subject: "Project review moved to 10:30 AM", snippet: "Hi — tomorrow's project review is now at 10:30 AM. Please bring the launch notes." },
  { from: "Billing", subject: "Invoice due Friday", snippet: "Your October invoice of $49 is due this Friday. No action is needed if payment is already scheduled." },
  { from: "Team Updates", subject: "Weekly engineering digest", snippet: "This week's releases: search filters, mobile notification fixes, and dashboard improvements." },
];

function json(res, status, data) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

// This mimics Ollama's POST /api/chat response format. Replace it with real Ollama later.
const mockLlm = http.createServer(async (req, res) => {
  if (req.method !== "POST" || req.url !== "/api/chat") return json(res, 404, { error: "Not found" });
  let body = "";
  for await (const chunk of req) body += chunk;
  const received = JSON.parse(body);
  const response = {
    model: received.model,
    message: { role: "assistant", content: "Priority: Sarah's project review moved to 10:30 AM tomorrow; bring the launch notes.\n\nAction needed: Review or schedule payment for the $49 invoice due Friday.\n\nFYI: The engineering digest contains this week's release updates." },
    done: true,
  };
  json(res, 200, response);
});

const page = `<!doctype html><html><head><meta charset="utf-8"><title>Inbox Brief demo</title><style>
body{margin:0;background:#f6f7fb;color:#172033;font:16px system-ui,sans-serif}.wrap{max-width:860px;margin:52px auto;padding:0 22px}h1{font-size:42px;margin:0}.lead{color:#5b667c}.card{background:#fff;border:1px solid #e3e7f0;border-radius:16px;padding:22px;margin-top:18px}.mail{border-bottom:1px solid #edf0f5;padding:12px 0}.mail:last-child{border:0}.subject{font-weight:700}.muted{color:#65718a;font-size:14px}button{background:#315ce8;border:0;border-radius:9px;color:#fff;font:inherit;padding:11px 16px;cursor:pointer}pre{white-space:pre-wrap;background:#f5f7fb;border-radius:10px;padding:15px;line-height:1.5}details{margin-top:14px}textarea{box-sizing:border-box;width:100%;height:75px;border:1px solid #ccd3e0;border-radius:9px;padding:10px;font:inherit;margin:8px 0}</style></head><body><main class="wrap"><h1>Inbox Brief</h1><p class="lead">Runnable demo mode — Gmail and Ollama are simulated, but the backend-to-LLM HTTP call is real.</p><section class="card"><div class="muted">Demo inbox (normally returned by Gmail API)</div>${demoEmails.map(e=>`<div class="mail"><div class="subject">${e.subject}</div><div class="muted">${e.from} · ${e.snippet}</div></div>`).join("")}</section><section class="card"><label for="q">Ask your inbox assistant</label><textarea id="q">What needs my attention tomorrow?</textarea><button id="run">Create summary</button><span id="status" class="muted"></span><pre id="answer">Click Create summary to run the demo.</pre><details open><summary>Backend ↔ LLM API trace</summary><pre id="trace">No request yet.</pre></details></section></main><script>document.querySelector('#run').onclick=async()=>{status.textContent=' Calling backend…';answer.textContent='';const r=await fetch('/api/summary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q.value})});const d=await r.json();status.textContent='';answer.textContent=d.summary;trace.textContent=JSON.stringify(d.trace,null,2)};</script></body></html>`;

const app = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/") { res.writeHead(200, { "Content-Type": "text/html" }); return res.end(page); }
  if (req.method !== "POST" || req.url !== "/api/summary") return json(res, 404, { error: "Not found" });
  let body = "";
  for await (const chunk of req) body += chunk;
  const { question = "Give me an inbox brief." } = JSON.parse(body);
  const prompt = `Summarize these emails only. User question: ${question}\n\n` + demoEmails.map(e => `FROM: ${e.from}\nSUBJECT: ${e.subject}\nCONTENT: ${e.snippet}`).join("\n\n");
  const llmPayload = { model: "gemma3:1b", stream: false, messages: [{ role: "user", content: prompt }], options: { temperature: 0.2 } };
  const llmResponse = await fetch("http://127.0.0.1:11434/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(llmPayload) });
  const llmResult = await llmResponse.json();
  json(res, 200, { summary: llmResult.message.content, trace: { gmail_calls: ["DEMO: users.messages.list(labelIds=INBOX)", "DEMO: users.messages.get(format=full) × 3"], llm_call: { method: "POST", url: "http://127.0.0.1:11434/api/chat", model: llmPayload.model, stream: false, prompt_characters: prompt.length, response_field: "message.content" }, note: "The local mock uses the same API contract as Ollama. Install Ollama and remove the mock server to use the real model." } });
});

mockLlm.listen(11434, "127.0.0.1", () => console.log("Mock Ollama listening at http://127.0.0.1:11434"));
app.listen(5050, "127.0.0.1", () => console.log("Demo available at http://127.0.0.1:5050"));
