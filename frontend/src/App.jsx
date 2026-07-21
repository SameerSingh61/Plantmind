import { useState } from "react";
import BriefingFeed from "./components/BriefingFeed";
import QuerySurface from "./components/QuerySurface";
import GraphExplorer from "./components/GraphExplorer";
import RetirementView from "./components/RetirementView";

const TABS = [
  { id: "briefings", label: "Briefings", icon: "⚡" },
  { id: "ask", label: "Ask", icon: "❓" },
  { id: "explorer", label: "Explorer", icon: "🕸" },
  { id: "retirement", label: "Retirement", icon: "🎓" },
];

export default function App() {
  const [tab, setTab] = useState("briefings");

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100">
      <header className="px-4 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-lg font-bold">PlantMind</h1>
          <p className="text-xs text-slate-500">Kaveri Refinery Unit 3 — knowledge graph</p>
        </div>
        <span className="hidden sm:block text-xs text-slate-600">
          The plant has a memory, and it interrupts you before you make the mistake.
        </span>
      </header>

      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto">
          {tab === "briefings" && <BriefingFeed />}
          {tab === "ask" && <QuerySurface />}
          {tab === "explorer" && <div className="h-full"><GraphExplorer /></div>}
          {tab === "retirement" && <RetirementView />}
        </div>
      </main>

      <nav className="shrink-0 border-t border-slate-800 flex sm:hidden">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2 flex flex-col items-center text-xs ${
              tab === t.id ? "text-sky-400" : "text-slate-500"
            }`}
          >
            <span className="text-base">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
      <nav className="hidden sm:flex border-t border-slate-800 px-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              tab === t.id ? "text-sky-400 border-sky-400" : "text-slate-500 border-transparent"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
