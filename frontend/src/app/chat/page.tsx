"use client";

import { useState, useRef, useEffect } from "react";
import { useSession } from "@/components/SessionProvider";
import api, { ChatMessage } from "@/lib/api";

export default function ChatPage() {
  const { isActive: hasSession } = useSession();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 160) + "px";
    }
  }, [input]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res = await api.chat(updatedMessages);
      const assistantMsg: ChatMessage = { role: "assistant", content: res.response };
      setMessages([...updatedMessages, assistantMsg]);
    } catch (e: any) {
      setError(e.message);
      // Keep the user message but show error
    } finally {
      setSending(false);
      // Re-focus input
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-7.5rem)] animate-in">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-border-primary">
        <div>
          <h2 className="text-lg font-semibold">Strategy Chat</h2>
          <p className="text-xs text-text-muted mt-0.5">
            Ask about your trade plans, market conditions, catalysts, or strategy adjustments
          </p>
        </div>
        <div className="flex items-center gap-3">
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="px-3 py-1.5 text-xs text-text-muted hover:text-text-secondary bg-bg-tertiary hover:bg-bg-hover rounded-md transition-colors"
            >
              Clear
            </button>
          )}
          <div className={`flex items-center gap-1.5 text-xs ${
            hasSession ? "text-accent-green" : "text-accent-amber"
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${
              hasSession ? "bg-accent-green" : "bg-accent-amber"
            }`} />
            {hasSession ? "Session active" : "No session"}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <EmptyState onSelect={(text) => {
            setInput(text);
            // Small delay so the input updates before sending
            setTimeout(() => {
              const userMsg: ChatMessage = { role: "user", content: text };
              setMessages([userMsg]);
              setSending(true);
              setError(null);
              api.chat([userMsg])
                .then((res) => {
                  setMessages([userMsg, { role: "assistant", content: res.response }]);
                })
                .catch((e: any) => setError(e.message))
                .finally(() => {
                  setSending(false);
                  setInput("");
                });
            }, 50);
          }} />
        ) : (
          messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))
        )}

        {/* Typing indicator */}
        {sending && (
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-md bg-accent-blue/20 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-bold text-accent-blue">TP</span>
            </div>
            <div className="bg-bg-secondary border border-border-primary rounded-lg px-4 py-3">
              <div className="flex gap-1.5">
                <div className="w-1.5 h-1.5 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-1.5 h-1.5 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-1.5 h-1.5 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-accent-red/10 border border-accent-red/20 rounded-lg px-4 py-3 text-sm text-accent-red">
            {error.includes("No active session")
              ? "No active session. Go to the Dashboard and initialize a session first."
              : `Error: ${error}`}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border-primary pt-4">
        <div className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your plans, the market, catalysts, or strategy..."
            rows={1}
            className="flex-1 px-4 py-3 bg-bg-secondary border border-border-primary rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue resize-none leading-relaxed"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || sending}
            className="px-5 py-3 bg-accent-blue hover:bg-accent-blue/80 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 flex-shrink-0"
          >
            Send
          </button>
        </div>
        <p className="text-xs text-text-muted mt-2">
          Shift+Enter for new line. Context includes session analysis, trade plans, and your performance history.
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${
        isUser ? "bg-bg-tertiary" : "bg-accent-blue/20"
      }`}>
        <span className={`text-xs font-bold ${isUser ? "text-text-secondary" : "text-accent-blue"}`}>
          {isUser ? "Y" : "TP"}
        </span>
      </div>

      {/* Message */}
      <div className={`max-w-[80%] rounded-lg px-4 py-3 ${
        isUser
          ? "bg-accent-blue/10 border border-accent-blue/20"
          : "bg-bg-secondary border border-border-primary"
      }`}>
        <div className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
          {message.content}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onSelect }: { onSelect: (text: string) => void }) {
  const suggestions = [
    "What's the outlook for this week?",
    "Why is catalyst risk elevated?",
    "Should I wait until after CPI to enter any positions?",
    "What sectors look strongest right now?",
    "Walk me through the NVDA trade plan",
    "What if I widen my stop on the AMD trade?",
    "Are there any hidden correlation risks in my positions?",
    "What setups work best in this regime?",
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="w-12 h-12 rounded-xl bg-accent-blue/10 flex items-center justify-center mb-4">
        <span className="text-lg font-bold text-accent-blue">TP</span>
      </div>
      <h3 className="text-sm font-medium text-text-primary mb-1">TradePilot Strategist</h3>
      <p className="text-xs text-text-muted mb-6 max-w-md">
        I have full context on today&apos;s session — market regime, catalysts, your trade plans, and performance history. Ask me anything.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg">
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => onSelect(s)}
            className="text-left px-3 py-2 text-xs text-text-secondary bg-bg-secondary border border-border-primary rounded-lg hover:border-accent-blue/30 hover:text-text-primary transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
