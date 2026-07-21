import { useState } from "react";
import { api } from "../api";

const EXAMPLES = [
  "What incidents has P-101A had?",
  "What is the design pressure rating for V-2301?",
  "What has R. Krishnan worked on?",
];

function AnswerCard({ result }) {
  if (result.refused) {
    return (
      <div className="rounded-lg border border-rose-800 bg-rose-950/40 p-4">
        <span className="text-xs uppercase tracking-wide text-rose-400 font-semibold">refused — not in the record</span>
        <p className="text-sm text-slate-200 mt-2">{result.answer}</p>
        {result.person_to_ask && (
          <p className="text-xs text-slate-500 mt-2">
            Ask: {result.person_to_ask.name} ({result.person_to_ask.role})
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-emerald-800 bg-emerald-950/30 p-4">
      <span className="text-xs uppercase tracking-wide text-emerald-400 font-semibold">grounded answer</span>
      <p className="text-sm text-slate-200 mt-2 whitespace-pre-wrap">{result.answer}</p>
    </div>
  );
}

export default function QuerySurface() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  const ask = async (q) => {
    const text = (q ?? question).trim();
    if (!text) return;
    setLoading(true);
    setQuestion("");
    try {
      const result = await api.query(text);
      setHistory((h) => [{ question: text, result }, ...h]);
    } catch (e) {
      setHistory((h) => [{ question: text, result: { answer: String(e), refused: true } }, ...h]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-4 flex flex-col h-full">
      <h2 className="text-xl font-bold text-slate-100 mb-1">Ask the plant</h2>
      <p className="text-sm text-slate-400 mb-4">
        Every claim carries a citation. If the graph doesn't cover something, the system says so and
        names who to ask — it never improvises.
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => ask(ex)}
            className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded-full border border-slate-700"
          >
            {ex}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); ask(); }}
        className="flex gap-2 mb-4 sticky top-0"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about any equipment, e.g. P-101A, V-2301, E-206…"
          className="flex-1 bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md"
        >
          {loading ? "…" : "Ask"}
        </button>
      </form>

      <div className="flex-1 overflow-y-auto space-y-4">
        {history.map((h, i) => (
          <div key={i}>
            <p className="text-sm text-slate-400 mb-1">Q: {h.question}</p>
            <AnswerCard result={h.result} />
            {h.result.time_to_answer_ms !== undefined && (
              <p className="text-xs text-slate-600 mt-1">answered in {h.result.time_to_answer_ms}ms</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
