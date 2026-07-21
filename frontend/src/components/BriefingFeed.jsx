import { useEffect, useState } from "react";
import { api } from "../api";

function BriefingCard({ b }) {
  const sections = {};
  for (const part of b.text.split(/\n\n+/)) {
    const m = part.match(/^([A-Z][A-Z\s]+):\s*([\s\S]*)$/);
    if (m) sections[m[1].trim()] = m[2].trim();
  }
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/60 p-4 mb-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs uppercase tracking-wide text-amber-400 font-semibold">
          {b.trigger_rule?.replaceAll("_", " ") || "pattern"}
        </span>
        <span className="text-xs text-slate-500">{b.source === "llm" ? "generated live" : "template render (no live model call)"}</span>
      </div>
      {sections["HEADLINE"] && (
        <h3 className="text-lg font-semibold text-slate-100 mb-2">{sections["HEADLINE"]}</h3>
      )}
      {sections["WHAT THE RECORD SHOWS"] && (
        <p className="text-sm text-slate-300 mb-2">{sections["WHAT THE RECORD SHOWS"]}</p>
      )}
      {sections["WHY THIS SURFACED NOW"] && (
        <p className="text-xs text-slate-400 italic mb-2">{sections["WHY THIS SURFACED NOW"]}</p>
      )}
      {sections["FOR YOUR DECISION"] && (
        <p className="text-sm text-sky-300 font-medium border-t border-slate-700 pt-2 mt-2">
          {sections["FOR YOUR DECISION"]}
        </p>
      )}
    </div>
  );
}

function PatternCard({ p }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/40 p-4 mb-3">
      <span className="text-xs uppercase tracking-wide text-fuchsia-400 font-semibold">recurrence pattern</span>
      <h3 className="text-base font-semibold text-slate-100 mt-1 mb-1">
        {p.failure_mode.replaceAll("_", " ")} across {p.equipment_involved.length} {p.equipment_type.replaceAll("_", " ")}s
      </h3>
      <p className="text-sm text-slate-300">
        {p.incident_count} incidents ({p.incidents.join(", ")}) on {p.equipment_involved.join(", ")}, spanning{" "}
        {p.date_range[0]} to {p.date_range[1]}. No single report cross-references the others.
      </p>
    </div>
  );
}

function OrphanCard({ o }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/40 p-4 mb-3">
      <span className="text-xs uppercase tracking-wide text-rose-400 font-semibold">orphaned knowledge</span>
      <h3 className="text-base font-semibold text-slate-100 mt-1 mb-1">
        {o.equipment} — {o.work_order_count} work orders, zero governing procedures
      </h3>
      <p className="text-sm text-slate-300">
        {o.primary_author} authored {Math.round(o.primary_author_share * 100)}% of them
        {o.primary_author_status === "retiring" ? ` and retires ${o.primary_author_tenure_end}.` : "."}
      </p>
    </div>
  );
}

export default function BriefingFeed() {
  const [briefings, setBriefings] = useState([]);
  const [patterns, setPatterns] = useState([]);
  const [orphans, setOrphans] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    const [b, p, o] = await Promise.all([api.briefings(), api.recurrencePatterns(), api.orphanedKnowledge()]);
    setBriefings(b.briefings);
    setPatterns(p.patterns);
    setOrphans(o.orphans);
  };

  useEffect(() => { refresh(); }, []);

  const trigger = async () => {
    setLoading(true);
    try {
      await api.triggerStoryline1();
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  const nothing = briefings.length === 0 && patterns.length === 0 && orphans.length === 0;

  return (
    <div className="max-w-2xl mx-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-100">The plant speaks first</h2>
        <button
          onClick={trigger}
          disabled={loading}
          className="text-sm bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium px-3 py-1.5 rounded-md"
        >
          {loading ? "Opening WO-2026-4471…" : "Open WO-2026-4471 on P-101A"}
        </button>
      </div>
      <p className="text-sm text-slate-400 mb-4">
        Nothing here is a response to a question — every card below fired because the graph detected
        a condition on its own. Unprompted briefings appear at the top; the nightly sweep (recurrence
        patterns, orphaned knowledge) runs below.
      </p>
      {nothing && <p className="text-slate-500 text-sm">No conditions detected yet. Try the button above.</p>}
      {briefings.map((b) => <BriefingCard key={b.id} b={b} />)}
      {patterns.map((p, i) => <PatternCard key={i} p={p} />)}
      {orphans.map((o, i) => <OrphanCard key={i} o={o} />)}
    </div>
  );
}
