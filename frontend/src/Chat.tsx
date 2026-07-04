import { useState, useRef, useEffect } from "react";
import { buildWebSocketUrl, uploadFile, type Message } from "./api";

interface UploadedFile {
  fileId: string;
  filename: string;
  rowCount: number;
  columns: { name: string; dtype: string }[];
}

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
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMessages(initialMessages);
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError("");
    setUploading(true);

    try {
      const result = await uploadFile(token, file);
      setUploadedFile({
        fileId: result.file_id,
        filename: result.original_filename,
        rowCount: result.row_count,
        columns: result.columns,
      });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Upload failed. Please try again.";
      setUploadError(detail);
    } finally {
      setUploading(false);
      // Reset input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function handleClearFile() {
    setUploadedFile(null);
    setUploadError("");
  }

  function connectAndSend(userMessage: string) {
    const url = buildWebSocketUrl(
      token,
      conversationId,
      uploadedFile?.fileId
    );
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
      {
        role: "user",
        content: userMessage,
        created_at: new Date().toISOString(),
      },
    ]);
    setInput("");
    connectAndSend(userMessage);
  }

  return (
    <div className="flex flex-col h-screen bg-gray-900">
      {/* Header */}
      <header className="flex justify-between items-center px-6 py-4 border-b border-gray-700">
        <h1 className="text-white font-semibold">EADA Chat</h1>
        <button
          onClick={onLogout}
          className="text-gray-400 hover:text-white text-sm"
        >
          Logout
        </button>
      </header>

      {/* File badge — shown when a file is uploaded */}
      {uploadedFile && (
        <div className="flex items-center gap-3 px-6 py-2 bg-blue-900 border-b border-blue-700">
          <span className="text-blue-300 text-sm">📊</span>
          <div className="flex-1 min-w-0">
            <span className="text-blue-100 text-sm font-medium truncate">
              {uploadedFile.filename}
            </span>
            <span className="text-blue-400 text-xs ml-2">
              {uploadedFile.rowCount.toLocaleString()} rows ·{" "}
              {uploadedFile.columns.length} columns
            </span>
          </div>
          <button
            onClick={handleClearFile}
            className="text-blue-400 hover:text-white text-xs px-2 py-1 rounded hover:bg-blue-800 transition"
          >
            ✕ Clear
          </button>
        </div>
      )}

      {/* Upload error */}
      {uploadError && (
        <div className="px-6 py-2 bg-red-900 border-b border-red-700 text-red-200 text-sm">
          ⚠️ {uploadError}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
        {messages.length === 0 && !streamingContent && (
          <div className="text-center text-gray-500 mt-16 text-sm">
            {uploadedFile
              ? `File loaded. Ask a question about ${uploadedFile.filename}.`
              : "Upload a CSV, Excel, or JSON file to analyse it, or just start chatting."}
          </div>
        )}

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

      {/* Input bar */}
      <form
        onSubmit={handleSend}
        className="flex gap-2 px-6 py-4 border-t border-gray-700 items-center"
      >
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.json,.parquet"
          className="hidden"
          onChange={handleFileSelect}
        />

        {/* Paperclip button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || streamingContent !== ""}
          title="Upload a data file"
          className="text-gray-400 hover:text-white disabled:opacity-40 transition text-xl px-1"
        >
          {uploading ? "⏳" : "📎"}
        </button>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            uploadedFile
              ? `Ask a question about ${uploadedFile.filename}...`
              : "Ask a data question or upload a file..."
          }
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