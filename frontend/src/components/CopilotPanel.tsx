import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type CopilotResponse } from "../api";

type ChatMsg = {
  role: "user" | "assistant";
  text: string;
  note?: string;
};

const STARTERS = [
  "Is outdoor exercise OK today?",
  "Will air improve in 24 hours?",
  "When is smog season worst?",
  "What is driving AQI in SHAP?",
  "How has the last week looked?",
];

const ANIM_MS = 280;

type Props = {
  city: string;
};

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function FormattedReply({ text }: { text: string }) {
  const blocks = text
    .replace(/\r\n/g, "\n")
    .trim()
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);

  return (
    <div className="copilot-rich">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
        const bulletLines = lines.filter((l) => /^[-•*]\s+/.test(l));
        if (bulletLines.length && bulletLines.length === lines.length) {
          return (
            <ul key={bi} className="copilot-rich-list">
              {lines.map((line, li) => (
                <li key={li}>{renderInline(line.replace(/^[-•*]\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={bi} className="copilot-rich-p">
            {lines.map((line, li) => (
              <span key={li}>
                {li > 0 && <br />}
                {renderInline(line.replace(/^[-•*]\s+/, ""))}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

export function CopilotPanel({ city }: Props) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState(STARTERS);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const closeTimer = useRef<number | null>(null);

  useEffect(() => {
    setMessages([]);
    setError(null);
    setSuggestions(STARTERS);
  }, [city]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading, open]);

  useEffect(() => {
    if (open) {
      const t = window.setTimeout(() => inputRef.current?.focus(), 220);
      return () => window.clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    return () => {
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    };
  }, []);

  const openPanel = () => {
    if (closeTimer.current) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    setMounted(true);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setOpen(true));
    });
  };

  const closePanel = () => {
    setOpen(false);
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => {
      setMounted(false);
      closeTimer.current = null;
    }, ANIM_MS);
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    if (!open) openPanel();
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
    <div className={`copilot-dock ${open ? "is-open" : ""} ${mounted ? "is-mounted" : ""}`}>
      {mounted && (
        <div
          className="copilot-window"
          role="dialog"
          aria-label={`AQI Copilot for ${city}`}
          aria-modal="false"
          aria-hidden={!open}
        >
          <div className="copilot-window-head">
            <div className="copilot-window-head-text">
              <p className="copilot-window-kicker">Ask AtmoVista</p>
              <h2 className="copilot-window-title">AQI Copilot · {city}</h2>
            </div>
            <button
              type="button"
              className="copilot-close"
              onClick={closePanel}
              aria-label="Close chat"
            >
              ×
            </button>
          </div>

          <div className="copilot-thread" aria-live="polite">
            {!messages.length && !loading && (
              <div className="copilot-empty">
                Ask about outdoor exercise, tomorrow’s outlook, or what to do for {city}’s air.
              </div>
            )}
            {messages.map((m, idx) => (
              <div key={`${m.role}-${idx}`} className={`copilot-bubble ${m.role}`}>
                {m.role === "assistant" ? <FormattedReply text={m.text} /> : <p>{m.text}</p>}
                {m.note && <span className="copilot-note">{m.note}</span>}
              </div>
            ))}
            {loading && <div className="copilot-bubble assistant muted">Thinking…</div>}
            <div ref={bottomRef} />
          </div>

          {!!suggestions.length && (
            <div className="copilot-suggestions">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="copilot-chip"
                  onClick={() => void send(s)}
                  disabled={loading}
                >
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
              ref={inputRef}
              className="copilot-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask about ${city}…`}
              maxLength={500}
              disabled={loading}
              aria-label="Ask the AQI copilot"
            />
            <button type="submit" className="btn btn-primary copilot-send" disabled={loading || !input.trim()}>
              Ask
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className="copilot-fab"
        onClick={openPanel}
        aria-expanded={open}
        aria-hidden={open}
        tabIndex={open ? -1 : 0}
        aria-label="Open AQI Copilot"
      >
        <span className="copilot-fab-icon" aria-hidden="true">
          ✦
        </span>
        <span className="copilot-fab-label">Ask air</span>
      </button>
    </div>
  );
}
