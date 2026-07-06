import { useEffect, useState } from "react";
import { listConversations, type ConversationSummary } from "../api";

interface SidebarProps {
  token: string;
  activeConversationId?: string;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}

export default function Sidebar({
  token,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
}: SidebarProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConversations();
  }, [activeConversationId]);

  async function loadConversations() {
    try {
      const data = await listConversations(token);
      setConversations(data);
    } catch {
      // silently fail — sidebar is non-critical
    } finally {
      setLoading(false);
    }
  }

  function formatDate(iso: string) {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  return (
    <div className="flex flex-col h-full w-64 bg-gray-900 border-r border-gray-700">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-700">
        <h1 className="text-white font-bold text-lg">EADA</h1>
        <p className="text-gray-500 text-xs">Autonomous Data Analyst</p>
      </div>

      {/* New conversation button */}
      <div className="px-3 py-3">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg
                     bg-blue-600 hover:bg-blue-700 text-white text-sm
                     font-medium transition"
        >
          <span>+</span>
          <span>New Conversation</span>
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {loading ? (
          <p className="text-gray-500 text-xs px-2 mt-2">Loading...</p>
        ) : conversations.length === 0 ? (
          <p className="text-gray-500 text-xs px-2 mt-2">No conversations yet.</p>
        ) : (
          conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className={`w-full text-left px-3 py-2 rounded-lg mb-1
                         transition text-sm
                         ${
                           conv.id === activeConversationId
                             ? "bg-gray-700 text-white"
                             : "text-gray-400 hover:bg-gray-800 hover:text-white"
                         }`}
            >
              <p className="truncate font-medium">
                {conv.title || "Untitled"}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {formatDate(conv.updated_at)}
              </p>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
