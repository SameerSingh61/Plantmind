import { useEffect, useState } from "react";
import { api } from "../api";

export default function RetirementView() {
  const [tag, setTag] = useState("V-2301");
  const [data, setData] = useState(null);
  const [answers, setAnswers] = useState({});
  const [saved, setSaved] = useState({});
  const [error, setError] = useState(null);

  const load = async (t) => {
    setError(null);
    setData(null);
    try {
      const d = await api.retirementQuestions(t);
      setData(d);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => { load(tag); }, []);

  const submit = async (q) => {
    const text = answers[q.wo_id];
    if (!text) return;
    const payload = {
      person_id: data.finding.primary_author_id,
      equipment_tag: data.finding.equipment,
      wo_id: q.wo_id,
      answer_text: text,
    };
    const res = await api.submitInterviewAnswer(payload);
    setSaved((s) => ({ ...s, [q.wo_id]: res.new_node }));
  };

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h2 className="text-xl font-bold text-slate-100 mb-1">Before the knowledge leaves the building</h2>
      <p className="text-sm text-slate-400 mb-4">
        Every question below quotes the retiring engineer's own words back to them — people answer
        questions grounded in what they themselves wrote far more readily than a blank form.
      </p>

      <form
        onSubmit={(e) => { e.preventDefault(); load(tag); }}
        className="flex gap-2 mb-4"
      >
        <input
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100"
        />
        <button className="bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium px-4 py-2 rounded-md">
          Look up
        </button>
      </form>

      {error && <p className="text-rose-400 text-sm">{error}</p>}

      {data && (
        <>
          <div className="rounded-lg border border-slate-700 bg-slate-800/40 p-4 mb-4">
            <p className="text-sm text-slate-200">
              <strong>{data.finding.primary_author}</strong> authored{" "}
              {Math.round(data.finding.primary_author_share * 100)}% of the {data.finding.work_order_count} work
              orders on <strong>{data.finding.equipment}</strong>
              {data.finding.primary_author_status === "retiring"
                ? `, and retires ${data.finding.primary_author_tenure_end}. `
                : ". "}
              No current procedure governs this equipment.
            </p>
          </div>

          {data.questions.map((q) => (
            <div key={q.wo_id} className="rounded-lg border border-slate-700 bg-slate-800/60 p-4 mb-3">
              <p className="text-xs text-slate-500 mb-1">{q.wo_id}</p>
              <p className="text-sm text-slate-100 mb-3">{q.question}</p>
              {saved[q.wo_id] ? (
                <p className="text-xs text-emerald-400">
                  Saved as {saved[q.wo_id]} — now governs {data.finding.equipment}.
                </p>
              ) : (
                <div className="flex gap-2">
                  <textarea
                    rows={2}
                    value={answers[q.wo_id] || ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.wo_id]: e.target.value }))}
                    placeholder="Type the answer as the engineer would give it…"
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-sm text-slate-100"
                  />
                  <button
                    onClick={() => submit(q)}
                    className="bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-medium px-3 py-1.5 rounded-md self-start"
                  >
                    Save to graph
                  </button>
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
