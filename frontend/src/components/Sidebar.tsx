import { useEffect, useState } from "react";
import { listConversations, type ConversationSummary } from "../api";

interface SidebarProps {
  token: string;
  activeConversationId?: string;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onLogout: () => void;
}

export default function Sidebar({
  token,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onLogout,
}: SidebarProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (activeConversationId) loadConversations();
  }, [activeConversationId]);

  async function loadConversations() {
    try {
      const data = await listConversations(token);
      setConversations(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }

  function formatDate(iso: string) {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const days = Math.floor(diff / 86400000);
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return `${days} days ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  // Group conversations by date
  const grouped = conversations.reduce((acc, conv) => {
    const label = formatDate(conv.updated_at);
    if (!acc[label]) acc[label] = [];
    acc[label].push(conv);
    return acc;
  }, {} as Record<string, ConversationSummary[]>);

  return (
    <div className="flex flex-col h-full w-64 bg-[#0f0f0f] border-r border-white/10">
      {/* Logo */}
      <div className="px-4 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">E</span>
          </div>
          <div>
            <p className="text-white font-semibold text-sm leading-none">EADA</p>
            <p className="text-gray-500 text-xs mt-0.5">Data Analyst</p>
          </div>
        </div>
      </div>

      {/* New chat button */}
      <div className="px-3 pb-3">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl
                     bg-white/5 hover:bg-white/10 border border-white/10
                     text-white text-sm font-medium transition group"
        >
          <svg className="w-4 h-4 text-gray-400 group-hover:text-white transition" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Conversation
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 scrollbar-thin">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-4 h-4 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
          </div>
        ) : conversations.length === 0 ? (
          <p className="text-gray-600 text-xs px-3 py-4 text-center">No conversations yet</p>
        ) : (
          Object.entries(grouped).map(([label, convs]) => (
            <div key={label} className="mb-3">
              <p className="text-gray-600 text-xs px-3 py-1 font-medium uppercase tracking-wider">{label}</p>
              {convs.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className={`w-full text-left px-3 py-2 rounded-xl mb-0.5 transition text-sm group
                    ${conv.id === activeConversationId
                      ? "bg-white/10 text-white"
                      : "text-gray-400 hover:bg-white/5 hover:text-white"
                    }`}
                >
                  <p className="truncate font-medium leading-snug">
                    {conv.title || "New Conversation"}
                  </p>
                </button>
              ))}
            </div>
          ))
        )}
      </div>

      {/* User / logout */}
      <div className="px-3 py-3 border-t border-white/10">
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-xl
                     text-gray-400 hover:text-white hover:bg-white/5 transition text-sm"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Sign Out
        </button>
      </div>
    </div>
  );
}