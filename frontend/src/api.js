const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => req("/api/health"),
  graph: () => req("/api/graph"),
  node: (key) => req(`/api/graph/node/${encodeURIComponent(key)}`),
  path: (source, target) =>
    req(`/api/graph/path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`),
  briefings: () => req("/api/briefings"),
  triggerStoryline1: () => req("/api/demo/trigger-storyline-1", { method: "POST" }),
  createWorkOrder: (wo) => req("/api/work-orders", { method: "POST", body: JSON.stringify(wo) }),
  recurrencePatterns: () => req("/api/sweep/recurrence-patterns"),
  orphanedKnowledge: () => req("/api/sweep/orphaned-knowledge"),
  query: (question) => req("/api/query", { method: "POST", body: JSON.stringify({ question }) }),
  retirementQuestions: (tag) => req(`/api/retirement/${encodeURIComponent(tag)}`),
  submitInterviewAnswer: (payload) =>
    req("/api/retirement/answer", { method: "POST", body: JSON.stringify(payload) }),
  drawings: () => req("/api/drawings"),
  drawing: (id) => req(`/api/drawings/${encodeURIComponent(id)}`),
  reset: () => req("/api/reset", { method: "POST" }),
};
