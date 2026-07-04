# Kiri (කිරි) — AI Shopping Agent for Kapruka 🛍️

A multilingual, full-screen conversational shopping agent built on the
[Kapruka MCP](https://mcp.kapruka.com) for the **Kapruka Agent Challenge 2026**.
Kiri takes a customer from _"I'm not sure what to get"_ all the way to a real,
payable guest-checkout order — in **English, සිංහල, தமிழ், Singlish, or Tanglish**.

**🔗 Live demo:** https://kapruka-agent-sigma.vercel.app
**🎬 Demo video:**

---

## What Kiri can do

- **Speak how Sri Lankans speak** — mirrors the customer's language _and register_,
  including mid-conversation switches and code-switched Singlish/Tanglish
- **Search the live catalog** and present products as rich image cards (never a wall of text)
- **Full checkout** — multi-item carts, delivery city + date resolution
  ("heta" → tomorrow, date-grounded in Sri Lanka time), free gift messages,
  and a real click-to-pay link via Kapruka guest checkout
- **Stay truthful** — every product, price, image and link is grounded in live
  MCP tool results; structured card data bypasses the model entirely

## Architecture

Browser ── Next.js (Vercel, static shell + streaming chat UI)
│ POST /chat → SSE stream (tool / products / text events)
FastAPI (Render, persistent process)
│ hand-built agent loop (OpenAI SDK · manual tool orchestration)
│ • per-request MCP session → mcp.kapruka.com (all 7 tools)
│ • parallel tool execution (asyncio.gather)
│ • structured <products> extraction + backend image enrichment
│ • graceful degradation: tool errors are fed back to the model
Claude Sonnet (via OpenAI-compatible gateway; model is env-configurable)

## Engineering notes

- **Manual agent loop** — tool discovery via MCP `list_tools`, translated to
  OpenAI function-calling schemas; the transcript is the agent's only state
- **Anti-hallucination, in layers** — grounding rules in the system prompt,
  card data extracted server-side and enriched from `kapruka_get_product`
  (guarantees in code, preferences in prompts), temperature tuned for
  low-resource-language script stability
- **Multilingual by prompting** — mirroring rules + native-authored few-shot
  examples per language/register; no translation layer (it would destroy
  code-switching)
- **Evaluated** — a 20-row golden test matrix (languages × behaviors ×
  checkout) re-run on every change
- **Resilient** — Pydantic validation at the boundary, bounded loop (MAX_TURNS),
  tool-result truncation, keep-alive against cold starts, CORS allow-list

## Stack

FastAPI · Python `mcp` SDK · OpenAI SDK (custom base_url) · Next.js 16 ·
Tailwind v4 · react-markdown · Render + Vercel

## Run locally

```bash
# backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo 'LLM_API_KEY=...\nLLM_BASE_URL=...\nLLM_MODEL=...' > .env
uvicorn main:app --reload --port 8000

# frontend
cd frontend && npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev
```

Built solo by **Mewan Dimalsha** 🇱🇰
