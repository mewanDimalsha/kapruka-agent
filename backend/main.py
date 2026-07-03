# main.py
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

load_dotenv()

for var in ("AIM_API_KEY", "AIM_BASE_URL"):
    if not os.environ.get(var):
        raise RuntimeError(f"{var} is not set — check backend/.env")

app = FastAPI(title="Kapruka Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

client = AsyncOpenAI(
    api_key=os.environ["AIM_API_KEY"],
    base_url=os.environ["AIM_BASE_URL"],  # ← the one line that redirects the SDK
)

MODEL = "aim/claude-sonnet-4-6"
MAX_TURNS = 8  # safety cap on loop iterations


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    async def event_stream():
        try:
            async with kapruka_session() as session:
                # 1. Ask Kapruka what tools exist, translate for the model
                tool_defs = mcp_tools_to_openai(await session.list_tools())

                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                messages += [m.model_dump() for m in req.messages]

                # 2. THE AGENT LOOP
                for _ in range(MAX_TURNS):
                    resp = await client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        tools=tool_defs,
                        max_tokens=4096,
                    )
                    msg = resp.choices[0].message

                    # 3. Claude wants tools → execute and loop again
                    if msg.tool_calls:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": msg.content,
                                "tool_calls": [
                                    tc.model_dump() for tc in msg.tool_calls
                                ],
                            }
                        )
                        for tc in msg.tool_calls:
                            yield sse({"type": "tool", "name": tc.function.name})

                            args = json.loads(tc.function.arguments or "{}")
                            result = await session.call_tool(tc.function.name, args)
                            result_text = "\n".join(
                                c.text for c in result.content if c.type == "text"
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": result_text[:50_000],
                                }
                            )
                        continue  # ← back to step 2: Claude reads results, decides again

                    # 4. No tool calls → this is the final answer
                    yield sse({"type": "text", "text": msg.content or ""})
                    break

            yield "data: [DONE]\n\n"

        except Exception as exc:
            print(f"stream error: {exc!r}")
            yield sse({"type": "error", "message": "Something went wrong"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
