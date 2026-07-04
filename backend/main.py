import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from mcp_client import kapruka_session, mcp_tools_to_openai
from prompts import SYSTEM_PROMPT
from schemas import ChatRequest
from typing import Any, cast

from openai.types.chat import ChatCompletionMessageParam
from typing import Any, cast

from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
import re

load_dotenv()
PRODUCTS_RE = re.compile(r"<products>\s*(.*?)\s*</products>", re.DOTALL)


def extract_products(text: str) -> tuple[str, list[dict] | None]:
    """Lift the <products> JSON block out of the model's reply.
    Returns (clean_text, products or None). Fails safe: on any parse
    problem the block is still stripped so raw JSON never reaches the UI."""
    match = PRODUCTS_RE.search(text)
    if not match:
        return text, None
    clean = PRODUCTS_RE.sub("", text).strip()
    try:
        products = json.loads(match.group(1))
        if not isinstance(products, list):
            return clean, None
        return clean, products[:6]
    except json.JSONDecodeError:
        print("products block parse failed — stripped, no cards")
        return clean, None


for var in ("AIM_API_KEY", "AIM_BASE_URL"):
    if not os.environ.get(var):
        raise RuntimeError(f"{var} is not set — check backend/.env")

app = FastAPI(title="Kapruka Agent API")

DEFAULT_ORIGINS = [
    "https://kapruka-agent-sigma.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]


def allowed_origins() -> list[str]:
    extra = os.environ.get("ALLOWED_ORIGINS", "")
    origins = list(DEFAULT_ORIGINS)
    if extra:
        origins.extend(origin.strip() for origin in extra.split(",") if origin.strip())
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

client = AsyncOpenAI(
    api_key=os.environ["AIM_API_KEY"],
    base_url=os.environ["AIM_BASE_URL"],  # ← the one line that redirects the SDK
)

MODEL = "aim/gemini-3.5-flash-low"
MAX_TURNS = 8  # safety cap on loop iterations


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/")
async def root():
    return {"service": "Kiri — Kapruka shopping agent API", "health": "/health"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    async def event_stream():
        try:
            async with kapruka_session() as session:
                tool_defs = mcp_tools_to_openai(await session.list_tools())

                # Explicit annotation — fixes the too-narrow inference (Error 1)
                # and satisfies create()'s signature (Error 2)
                messages: list[ChatCompletionMessageParam] = [
                    {"role": "system", "content": SYSTEM_PROMPT}
                ]
                for m in req.messages:
                    if m.role == "user":
                        messages.append({"role": "user", "content": m.content})
                    else:
                        messages.append({"role": "assistant", "content": m.content})

                for _ in range(MAX_TURNS):
                    resp = await client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        tools=tool_defs,
                        max_tokens=4096,
                        temperature=0.4,
                    )
                    msg = resp.choices[0].message

                    if msg.tool_calls:
                        # The one honest cast: model_dump() is dynamic data,
                        # provably-correct typing is impossible here by nature
                        messages.append(
                            cast(
                                ChatCompletionMessageParam,
                                {
                                    "role": "assistant",
                                    "content": msg.content,
                                    "tool_calls": [
                                        tc.model_dump() for tc in msg.tool_calls
                                    ],
                                },
                            )
                        )

                        for tc in msg.tool_calls:
                            # NARROWING — the real-bug fix (Error 4):
                            # skip any non-function tool call instead of crashing on it
                            if tc.type != "function":
                                continue

                            yield sse({"type": "tool", "name": tc.function.name})

                            args: dict[str, Any] = json.loads(
                                tc.function.arguments or "{}"
                            )
                            result = await session.call_tool(tc.function.name, args)
                            result_text = "\n".join(
                                c.text for c in result.content if c.type == "text"
                            )
                            print(f"\n===== TOOL RESULT: {tc.function.name} =====")
                            print(result_text[:3000])
                            print("===== END =====\n")
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": result_text[:50_000],
                                }
                            )
                        continue
                    # 4. No tool calls → final answer
                    clean_text, products = extract_products(msg.content or "")
                    if products:
                        yield sse({"type": "products", "items": products})
                    yield sse({"type": "text", "text": clean_text})
                    break

        except Exception as exc:
            print(f"stream error: {exc!r}")
            yield sse({"type": "error", "message": "Something went wrong"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
