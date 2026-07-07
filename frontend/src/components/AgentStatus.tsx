interface AgentStatusProps {
  activeAgent: string | null;
}

const AGENT_LABELS: Record<string, { label: string; color: string }> = {
  router:    { label: "Routing query",        color: "text-yellow-400" },
  planner:   { label: "Planning steps",       color: "text-blue-400"   },
  analyst:   { label: "Analysing data",       color: "text-green-400"  },
  rag_agent: { label: "Searching documents",  color: "text-purple-400" },
  critic:    { label: "Reviewing answer",     color: "text-orange-400" },
  summarizer:{ label: "Summarising",          color: "text-cyan-400"   },
};

export default function AgentStatus({ activeAgent }: AgentStatusProps) {
  if (!activeAgent) return null;
  const info = AGENT_LABELS[activeAgent] ?? { label: activeAgent, color: "text-gray-400" };

  return (
    <div className="flex items-center justify-center py-2 px-4">
      <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1.5">
        <span className="relative flex h-2 w-2">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-current ${info.color}`} />
          <span className={`relative inline-flex rounded-full h-2 w-2 bg-current ${info.color}`} />
        </span>
        <span className={`text-xs font-medium ${info.color}`}>{info.label}</span>
      </div>
    </div>
  );
}