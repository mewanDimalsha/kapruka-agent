"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Msg = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "🎂 Birthday gift under Rs 5000",
  "🍫 Chocolates for my sister",
  "අම්මාට තෑග්ගක් ඕනේ 🎁",
  "Anniversary gift ekak hoyala denna",
];

export default function Home() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<"idle" | "thinking" | string>("idle");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || status !== "idle") return;

    const history: Msg[] = [...messages, { role: "user", content }];
    setMessages(history);
    setInput("");
    setStatus("thinking");

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          if (!frame.startsWith("data: ")) continue;
          const payload = frame.slice(6);
          if (payload === "[DONE]") continue;

          const event = JSON.parse(payload);
          if (event.type === "tool") {
            setStatus(friendlyToolName(event.name));
          } else if (event.type === "text") {
            assistantText += event.text;
            setMessages([
              ...history,
              { role: "assistant", content: assistantText },
            ]);
          } else if (event.type === "error") {
            setMessages([
              ...history,
              {
                role: "assistant",
                content:
                  "අපොයි! Something went wrong on my side 🙈 Please try again.",
              },
            ]);
          }
        }
      }
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "I couldn't reach the server 🙏 Check that the backend is running and try again.",
        },
      ]);
    } finally {
      setStatus("idle");
    }
  }

  return (
    <main className="flex h-dvh flex-col bg-gradient-to-b from-emerald-50 via-white to-amber-50">
      {/* Header */}
      <header className="border-b border-emerald-100 bg-white/70 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-600 text-xl shadow-sm">
            🛍️
          </div>
          <div>
            <h1 className="text-lg font-bold text-emerald-900">
              Kiri <span className="font-normal text-emerald-600">· කිරි</span>
            </h1>
            <p className="text-xs text-emerald-700">
              Your Kapruka shopping buddy — English · සිංහල · தமிழ்
            </p>
          </div>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.length === 0 && (
            <div className="mt-16 text-center duration-500 animate-in fade-in slide-in-from-bottom-4">
              <p className="text-3xl">🎁</p>
              <h2 className="mt-3 text-xl font-semibold text-emerald-900">
                Ayubowan! What are we shopping for today?
              </h2>
              <p className="mt-1 text-sm text-emerald-700">
                Gifts, chocolates, flowers, cakes — I&apos;ll find it and get it
                delivered anywhere in Sri Lanka.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-emerald-200 bg-white px-4 py-2 text-sm text-emerald-800 shadow-sm transition hover:-translate-y-0.5 hover:bg-emerald-50 hover:shadow"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex duration-300 animate-in fade-in slide-in-from-bottom-2 ${
                m.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={
                  m.role === "user"
                    ? "max-w-[85%] rounded-2xl rounded-br-sm bg-emerald-600 px-4 py-3 text-white shadow"
                    : "prose prose-sm max-w-[85%] rounded-2xl rounded-bl-sm border border-emerald-100 bg-white px-4 py-3 shadow-sm prose-a:text-emerald-700 prose-img:my-2 prose-img:h-44 prose-img:w-full prose-img:rounded-xl prose-img:object-cover"
                }
              >
                {m.role === "user" ? (
                  m.content
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.content}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          ))}

          {status !== "idle" && (
            <div className="flex justify-start duration-300 animate-in fade-in">
              <div className="flex items-center gap-2 rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-sm text-emerald-700 shadow-sm">
                <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
                {status === "thinking" ? "Kiri is thinking…" : status}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-emerald-100 bg-white/70 px-4 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-3xl gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder="Type in English, සිංහල, தமிழ், Singlish…"
            className="flex-1 rounded-full border border-emerald-200 bg-white px-5 py-3 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          />
          <button
            onClick={() => send(input)}
            disabled={status !== "idle"}
            className="rounded-full bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow transition hover:bg-emerald-700 active:scale-95 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </main>
  );
}

function friendlyToolName(name: string): string {
  const map: Record<string, string> = {
    kapruka_search_products: "🔎 Searching Kapruka…",
    kapruka_get_product: "🖼️ Fetching product details…",
    kapruka_list_categories: "🗂️ Browsing categories…",
    kapruka_list_delivery_cities: "📍 Finding your city…",
    kapruka_check_delivery: "🚚 Checking delivery…",
    kapruka_create_order: "🧾 Creating your order…",
    kapruka_track_order: "📦 Tracking your order…",
  };
  return map[name] ?? "Working on it…";
}
