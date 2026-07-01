import { useState, useRef, useEffect } from "react";
import { buildWebSocketUrl, type Message } from "./api";

interface ChatProps {
  token: string;
  conversationId?: string;
  initialMessages?: Message[];
  onConversationStarted: (id: string) => void;
  onLogout: () => void;
}

export default function Chat({
  token,
  conversationId,
  initialMessages = [],
  onConversationStarted,
  onLogout,
}: ChatProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(initialMessages);
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  function connectAndSend(userMessage: string) {
    const url = buildWebSocketUrl(token, conversationId);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    let accumulated = "";

    ws.onmessage = (event) => {
      const data = event.data as string;

      if (data.startsWith("{")) {
        try {
          const parsed = JSON.parse(data);
          if (parsed.type === "conversation_id") {
            if (!conversationId) {
              onConversationStarted(parsed.value);
            }
            ws.send(JSON.stringify({ message: userMessage }));
            return;
          }
        } catch {
          // not JSON
        }
      }

      if (data === "[DONE]") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: accumulated,
            created_at: new Date().toISOString(),
          },
        ]);
        setStreamingContent("");
        ws.close();
        return;
      }

      if (data.startsWith("[ERROR]")) {
        setStreamingContent("");
        ws.close();
        return;
      }

      accumulated += data;
      setStreamingContent(accumulated);
    };

    ws.onerror = () => {
      setStreamingContent("");
    };
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || streamingContent !== "") return;

    const userMessage = input.trim();
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage, created_at: new Date().toISOString() },
    ]);
    setInput("");
    connectAndSend(userMessage);
  }

  return (
    <div className="flex flex-col h-screen bg-gray-900">
      <header className="flex justify-between items-center px-6 py-4 border-b border-gray-700">
        <h1 className="text-white font-semibold">EADA Chat</h1>
        <button
          onClick={onLogout}
          className="text-gray-400 hover:text-white text-sm"
        >
          Logout
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-2xl rounded-lg px-4 py-2 ${
              m.role === "user"
                ? "bg-blue-600 text-white self-end"
                : "bg-gray-800 text-gray-100 self-start"
            }`}
          >
            <p className="whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}

        {streamingContent && (
          <div className="max-w-2xl rounded-lg px-4 py-2 bg-gray-800 text-gray-100 self-start">
            <p className="whitespace-pre-wrap">
              {streamingContent}
              <span className="animate-pulse">▍</span>
            </p>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSend}
        className="flex gap-2 px-6 py-4 border-t border-gray-700"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a data question..."
          className="flex-1 bg-gray-800 text-white rounded px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={streamingContent !== ""}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-4 py-2 font-medium transition"
        >
          Send
        </button>
      </form>
    </div>
  );
}