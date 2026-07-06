import { useState, useRef, useEffect } from "react";
import {
  buildWebSocketUrl,
  uploadFile,
  ingestDocument,
  getConversation,
  type Message,
} from "./api";
import Sidebar from "./components/Sidebar";
import AgentStatus from "./components/AgentStatus";

interface UploadedFile {
  fileId: string;
  filename: string;
  rowCount: number;
  columns: { name: string; dtype: string }[];
}

interface IngestedDoc {
  docId: string;
  filename: string;
  numChunks: number;
}

interface ChatProps {
  token: string;
  onLogout: () => void;
}

export default function Chat({ token, onLogout }: ChatProps) {
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [ingestedDoc, setIngestedDoc] = useState<IngestedDoc | null>(null);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  async function handleSelectConversation(id: string) {
    try {
      const detail = await getConversation(token, id);
      setConversationId(detail.id);
      setMessages(detail.messages);
      setStreamingContent("");
      setActiveAgent(null);
    } catch {
      // silently fail
    }
  }

  function handleNewConversation() {
    setConversationId(undefined);
    setMessages([]);
    setStreamingContent("");
    setActiveAgent(null);
    setUploadedFile(null);
    setIngestedDoc(null);
    setUploadError("");
  }

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
          ?.detail ?? "Upload failed.";
      setUploadError(detail);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDocSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError("");
    setIngesting(true);
    try {
      const result = await ingestDocument(token, file);
      setIngestedDoc({
        docId: result.doc_id,
        filename: file.name,
        numChunks: result.num_chunks,
      });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Ingest failed.";
      setUploadError(detail);
    } finally {
      setIngesting(false);
      if (docInputRef.current) docInputRef.current.value = "";
    }
  }

  function connectAndSend(userMessage: string) {
    const url = buildWebSocketUrl(
      token,
      conversationId,
      uploadedFile?.fileId,
      ingestedDoc?.docId
    );
    const ws = new WebSocket(url);
    wsRef.current = ws;
    let accumulated = "";

    ws.onmessage = (event) => {
      const data = event.data as string;

      // Handle JSON control messages
      if (data.startsWith("{")) {
        try {
          const parsed = JSON.parse(data);
          if (parsed.type === "conversation_id") {
            if (!conversationId) setConversationId(parsed.value);
            ws.send(JSON.stringify({ message: userMessage }));
            return;
          }
          if (parsed.type === "agent") {
            setActiveAgent(parsed.value);
            return;
          }
        } catch {
          // not JSON — treat as text
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
        setActiveAgent(null);
        ws.close();
        return;
      }

      if (data.startsWith("[ERROR]")) {
        setStreamingContent("");
        setActiveAgent(null);
        ws.close();
        return;
      }

      accumulated += data;
      setStreamingContent(accumulated);
    };

    ws.onerror = () => {
      setStreamingContent("");
      setActiveAgent(null);
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

  const isStreaming = streamingContent !== "";

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Sidebar */}
      <Sidebar
        token={token}
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="flex justify-between items-center px-6 py-3
                           border-b border-gray-700 bg-gray-900">
          <div className="flex items-center gap-3">
            <h2 className="text-white font-medium text-sm">
              {conversationId ? "Conversation" : "New Conversation"}
            </h2>
            {uploadedFile && (
              <span className="bg-blue-900 text-blue-200 text-xs px-2 py-0.5 rounded-full">
                📊 {uploadedFile.filename}
              </span>
            )}
            {ingestedDoc && (
              <span className="bg-purple-900 text-purple-200 text-xs px-2 py-0.5 rounded-full">
                📄 {ingestedDoc.filename}
              </span>
            )}
          </div>
          <button
            onClick={onLogout}
            className="text-gray-400 hover:text-white text-sm transition"
          >
            Logout
          </button>
        </header>

        {/* Agent status indicator */}
        <AgentStatus activeAgent={activeAgent} />

        {/* Upload error */}
        {uploadError && (
          <div className="px-6 py-2 bg-red-900 border-b border-red-700
                          text-red-200 text-sm">
            ⚠️ {uploadError}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-3">
          {messages.length === 0 && !isStreaming && (
            <div className="text-center text-gray-500 mt-20 text-sm">
              {uploadedFile
                ? `Ask a question about ${uploadedFile.filename}`
                : ingestedDoc
                ? `Ask a question about ${ingestedDoc.filename}`
                : "Upload a data file 📊 or document 📄, or just start chatting."}
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-2xl rounded-lg px-4 py-3 text-sm
                ${m.role === "user"
                  ? "bg-blue-600 text-white self-end ml-auto"
                  : "bg-gray-800 text-gray-100 self-start"
                }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
            </div>
          ))}

          {isStreaming && (
            <div className="max-w-2xl rounded-lg px-4 py-3 bg-gray-800
                            text-gray-100 self-start text-sm">
              <p className="whitespace-pre-wrap leading-relaxed">
                {streamingContent}
                <span className="animate-pulse ml-0.5">▋</span>
              </p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="px-6 py-4 border-t border-gray-700 bg-gray-900">
          {/* Hidden file inputs */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls,.json,.parquet"
            className="hidden"
            onChange={handleFileSelect}
          />
          <input
            ref={docInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={handleDocSelect}
          />

          <form onSubmit={handleSend} className="flex gap-2 items-center">
            {/* Data file upload */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || isStreaming}
              title="Upload data file (CSV, Excel, JSON, Parquet)"
              className="text-gray-400 hover:text-white disabled:opacity-40
                         transition text-lg px-1"
            >
              {uploading ? "⏳" : "📊"}
            </button>

            {/* Document upload */}
            <button
              type="button"
              onClick={() => docInputRef.current?.click()}
              disabled={ingesting || isStreaming}
              title="Upload document for Q&A (PDF, DOCX, TXT, MD)"
              className="text-gray-400 hover:text-white disabled:opacity-40
                         transition text-lg px-1"
            >
              {ingesting ? "⏳" : "📄"}
            </button>

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                uploadedFile
                  ? `Ask about ${uploadedFile.filename}...`
                  : ingestedDoc
                  ? `Ask about ${ingestedDoc.filename}...`
                  : "Ask anything..."
              }
              disabled={isStreaming}
              className="flex-1 bg-gray-800 text-white rounded-lg px-4 py-2
                         outline-none focus:ring-2 focus:ring-blue-500
                         disabled:opacity-50 text-sm"
            />
            <button
              type="submit"
              disabled={isStreaming || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50
                         text-white rounded-lg px-4 py-2 font-medium
                         transition text-sm"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
