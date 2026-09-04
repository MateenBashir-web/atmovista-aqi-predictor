import { useEffect, useRef, useState } from "react";
import { api, type CopilotResponse } from "../api";

type ChatMsg = {
  role: "user" | "assistant";
  text: string;
  note?: string;
};

const STARTERS = [
  "Is outdoor exercise OK today?",
  "Will air improve in 24 hours?",
  "What should I do right now?",
];

type Props = {
  city: string;
};

export function CopilotPanel({ city }: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState(STARTERS);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages([]);
    setError(null);
    setSuggestions(STARTERS);
  }, [city]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    setError(null);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setLoading(true);
    try {
      const res: CopilotResponse = await api.copilot(city, trimmed);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: res.reply,
          note: res.note,
        },
      ]);
      if (res.suggestions?.length) setSuggestions(res.suggestions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Copilot request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel copilot-panel">
      <div className="section-head">
        <div>
          <p className="section-kicker">Ask AtmoVista</p>
          <h2 className="section-title">AQI Copilot · {city}</h2>
        </div>
        <span className="section-icon">✦</span>
      </div>
      <p className="section-sub">
        Ask about outdoor exercise, tomorrow’s outlook, or what to do for this city’s air quality.
      </p>

      <div className="copilot-thread" aria-live="polite">
        {!messages.length && !loading && (
          <div className="copilot-empty">
            Try a quick question about {city}’s air right now.
          </div>
        )}
        {messages.map((m, idx) => (
          <div key={`${m.role}-${idx}`} className={`copilot-bubble ${m.role}`}>
            <p>{m.text}</p>
            {m.note && <span className="copilot-note">{m.note}</span>}
          </div>
        ))}
        {loading && <div className="copilot-bubble assistant muted">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      {!!suggestions.length && (
        <div className="copilot-suggestions">
          {suggestions.map((s) => (
            <button key={s} type="button" className="copilot-chip" onClick={() => send(s)} disabled={loading}>
              {s}
            </button>
          ))}
        </div>
      )}

      {error && <p className="copilot-error">{error}</p>}

      <form
        className="copilot-form"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <input
          className="copilot-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Ask about ${city} air quality…`}
          maxLength={500}
          disabled={loading}
          aria-label="Ask the AQI copilot"
        />
        <button type="submit" className="btn btn-primary copilot-send" disabled={loading || !input.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}
