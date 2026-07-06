interface AgentStatusProps {
  activeAgent: string | null;
}

const AGENT_LABELS: Record<string, string> = {
  router: "🔀 Routing request...",
  planner: "📋 Planning steps...",
  analyst: "📊 Analysing data...",
  rag_agent: "🔍 Searching document...",
  critic: "🔎 Reviewing answer...",
  summarizer: "✍️ Summarising...",
};

export default function AgentStatus({ activeAgent }: AgentStatusProps) {
  if (!activeAgent) return null;

  const label = AGENT_LABELS[activeAgent] ?? `⚙️ ${activeAgent}...`;

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-gray-800
                    border-b border-gray-700 text-sm text-gray-300">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full
                         rounded-full bg-blue-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
      </span>
      <span>{label}</span>
    </div>
  );
}
