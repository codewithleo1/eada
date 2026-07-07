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

const SUGGESTIONS = [
  "What are the top 5 products by revenue?",
  "Show me a summary of the data",
  "What trends can you identify?",
  "Calculate the total sales by category",
];

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, activeAgent]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + "px";
    }
  }, [input]);

  async function handleSelectConversation(id: string) {
    try {
      const detail = await getConversation(token, id);
      setConversationId(detail.id);
      setMessages(detail.messages);
      setStreamingContent("");
      setActiveAgent(null);
    } catch { /* silently fail */ }
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
        } catch { /* not JSON */ }
      }
      if (data === "[DONE]") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: accumulated, created_at: new Date().toISOString() },
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

  function handleSend() {
    if (!input.trim() || isStreaming) return;
    const userMessage = input.trim();
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage, created_at: new Date().toISOString() },
    ]);
    setInput("");
    connectAndSend(userMessage);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const isStreaming = streamingContent !== "" || activeAgent !== null;
  const isEmpty = messages.length === 0 && !isStreaming;

  return (
    <div className="flex h-screen bg-[#0f0f0f] text-white">
      {/* Sidebar */}
      <Sidebar
        token={token}
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onLogout={onLogout}
      />

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* Context pills */}
        {(uploadedFile || ingestedDoc || uploadError) && (
          <div className="flex items-center gap-2 px-6 py-2 border-b border-white/10 bg-[#0f0f0f]">
            {uploadedFile && (
              <span className="flex items-center gap-1.5 bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs px-3 py-1 rounded-full">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M4 4a2 2 0 012-2h4l6 6v8a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"/>
                </svg>
                {uploadedFile.filename} — {uploadedFile.rowCount} rows
                <button onClick={() => setUploadedFile(null)} className="ml-1 hover:text-white">×</button>
              </span>
            )}
            {ingestedDoc && (
              <span className="flex items-center gap-1.5 bg-violet-500/10 border border-violet-500/20 text-violet-300 text-xs px-3 py-1 rounded-full">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                  <path fillRule="evenodd" d="M4 5a2 2 0 012-2v1a1 1 0 000 2H6a2 2 0 00-2 2v6a2 2 0 002 2h8a2 2 0 002-2V8a2 2 0 00-2-2h-1a1 1 0 100-2V3a2 2 0 012 2v10a4 4 0 01-4 4H6a4 4 0 01-4-4V5z" clipRule="evenodd"/>
                </svg>
                {ingestedDoc.filename} — {ingestedDoc.numChunks} chunks
                <button onClick={() => setIngestedDoc(null)} className="ml-1 hover:text-white">×</button>
              </span>
            )}
            {uploadError && (
              <span className="text-red-400 text-xs">⚠ {uploadError}</span>
            )}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {isEmpty ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center h-full px-6 pb-20">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center mb-6 shadow-lg">
                <span className="text-white font-bold text-2xl">E</span>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">How can I help you?</h2>
              <p className="text-gray-400 text-sm mb-10 text-center max-w-md">
                Upload a data file or document, then ask me anything about it. I use multiple AI agents to analyse and answer your questions.
              </p>
              <div className="grid grid-cols-2 gap-3 w-full max-w-lg">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => { setInput(s); textareaRef.current?.focus(); }}
                    className="text-left bg-white/5 hover:bg-white/10 border border-white/10
                               rounded-xl px-4 py-3 text-sm text-gray-300 hover:text-white transition"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto px-6 py-6 flex flex-col gap-6">
              {messages.map((m, i) => (
                <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  {m.role === "assistant" && (
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-white font-bold text-xs">E</span>
                    </div>
                  )}
                  <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed
                    ${m.role === "user"
                      ? "bg-white/10 text-white rounded-tr-sm"
                      : "bg-[#1a1a1a] border border-white/10 text-gray-100 rounded-tl-sm"
                    }`}>
                    <p className="whitespace-pre-wrap">{m.content}</p>
                  </div>
                  {m.role === "user" && (
                    <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-gray-300 font-bold text-xs">U</span>
                    </div>
                  )}
                </div>
              ))}

              {/* Thinking dots */}
              {activeAgent && !streamingContent && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-white font-bold text-xs">E</span>
                  </div>
                  <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
                    <div className="flex gap-1.5 items-center h-5">
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay:"0ms"}}/>
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay:"150ms"}}/>
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay:"300ms"}}/>
                    </div>
                  </div>
                </div>
              )}

              {/* Streaming */}
              {streamingContent && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-white font-bold text-xs">E</span>
                  </div>
                  <div className="max-w-[80%] bg-[#1a1a1a] border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-100 leading-relaxed">
                    <p className="whitespace-pre-wrap">{streamingContent}<span className="animate-pulse ml-0.5 text-blue-400">▋</span></p>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Agent status */}
        <AgentStatus activeAgent={activeAgent} />

        {/* Input area */}
        <div className="px-6 py-4 border-t border-white/10">
          <div className="max-w-3xl mx-auto">
            <div className="relative bg-[#1a1a1a] border border-white/10 rounded-2xl
                            focus-within:border-white/30 transition shadow-lg">

              {/* Hidden inputs */}
              <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls,.json,.parquet" className="hidden" onChange={handleFileSelect} />
              <input ref={docInputRef} type="file" accept=".pdf,.docx,.txt,.md" className="hidden" onChange={handleDocSelect} />

              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything... (Shift+Enter for new line)"
                disabled={isStreaming}
                rows={1}
                className="w-full bg-transparent text-white px-4 pt-3.5 pb-12 outline-none
                           placeholder-gray-600 text-sm resize-none leading-relaxed
                           disabled:opacity-50"
              />

              {/* Bottom toolbar */}
              <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 py-2">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading || isStreaming}
                    title="Upload data file (CSV, Excel, JSON)"
                    className="flex items-center gap-1.5 text-gray-500 hover:text-white disabled:opacity-40
                               transition text-xs px-2 py-1.5 rounded-lg hover:bg-white/5"
                  >
                    {uploading ? (
                      <div className="w-3.5 h-3.5 border-2 border-gray-500 border-t-blue-400 rounded-full animate-spin" />
                    ) : (
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    )}
                    Data
                  </button>
                  <button
                    onClick={() => docInputRef.current?.click()}
                    disabled={ingesting || isStreaming}
                    title="Upload document (PDF, DOCX, TXT)"
                    className="flex items-center gap-1.5 text-gray-500 hover:text-white disabled:opacity-40
                               transition text-xs px-2 py-1.5 rounded-lg hover:bg-white/5"
                  >
                    {ingesting ? (
                      <div className="w-3.5 h-3.5 border-2 border-gray-500 border-t-violet-400 rounded-full animate-spin" />
                    ) : (
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                    )}
                    Doc
                  </button>
                </div>

                <button
                  onClick={handleSend}
                  disabled={isStreaming || !input.trim()}
                  className="flex items-center justify-center w-8 h-8 rounded-lg
                             bg-gradient-to-r from-blue-600 to-violet-600
                             hover:from-blue-500 hover:to-violet-500
                             disabled:opacity-40 transition shadow-md"
                >
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            </div>
            <p className="text-gray-600 text-xs text-center mt-2">
              EADA may make mistakes. Verify important information.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}