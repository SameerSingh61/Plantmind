import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { api } from "../api";

const TYPE_COLOR = {
  Equipment: "#38bdf8",
  FailureMode: "#f97316",
  WorkOrder: "#a3a3a3",
  Incident: "#f43f5e",
  Procedure: "#34d399",
  RegulatoryClause: "#a78bfa",
  Person: "#facc15",
};

function toElements(graph, filterTypes) {
  const nodes = graph.nodes
    .filter((n) => !filterTypes.length || filterTypes.includes(n.node_type))
    .map((n) => ({
      data: {
        id: n.key,
        label: n.name || n.title || n.text?.slice(0, 24) || n.id,
        type: n.node_type,
      },
    }));
  const nodeIds = new Set(nodes.map((n) => n.data.id));
  const edges = graph.edges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e, i) => ({
      data: { id: `e${i}`, source: e.source, target: e.target, label: e.edge_type },
    }));
  return [...nodes, ...edges];
}

export default function GraphExplorer() {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [graphData, setGraphData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [typeFilter, setTypeFilter] = useState([]);
  const [pathMode, setPathMode] = useState(false);
  const [pathPicks, setPathPicks] = useState([]);
  const [pathStatus, setPathStatus] = useState(null);

  useEffect(() => {
    api.graph().then(setGraphData);
  }, []);

  useEffect(() => {
    if (!graphData || !containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: toElements(graphData, typeFilter),
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele) => TYPE_COLOR[ele.data("type")] || "#64748b",
            label: "data(label)",
            "font-size": 8,
            color: "#e2e8f0",
            "text-valign": "bottom",
            "text-halign": "center",
            width: 18,
            height: 18,
            "text-margin-y": 4,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "#334155",
            "target-arrow-color": "#334155",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "font-size": 6,
            color: "#64748b",
          },
        },
        {
          selector: ".highlighted",
          style: {
            "background-color": "#fbbf24",
            "line-color": "#fbbf24",
            "target-arrow-color": "#fbbf24",
            width: 3,
            "z-index": 999,
          },
        },
        {
          selector: ".picked",
          style: { "border-width": 3, "border-color": "#fbbf24" },
        },
      ],
      layout: { name: "cose", animate: false, nodeRepulsion: 8000, idealEdgeLength: 60 },
    });
    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      setSelected(node.data("id"));
      if (pathMode) {
        node.addClass("picked");
        setPathPicks((prev) => {
          const next = [...prev, node.data("id")];
          return next.length > 2 ? [node.data("id")] : next;
        });
      }
    });
    cyRef.current = cy;
    return () => cy.destroy();
  }, [graphData, typeFilter, pathMode]);

  useEffect(() => {
    if (pathPicks.length !== 2 || !cyRef.current) return;
    setPathStatus("loading");
    api.path(pathPicks[0], pathPicks[1]).then((res) => {
      const cy = cyRef.current;
      cy.elements(".highlighted").removeClass("highlighted");
      const nodeIds = res.nodes.map((n) => n.key);
      nodeIds.forEach((id, i) => {
        setTimeout(() => {
          const n = cy.getElementById(id);
          if (n) n.addClass("highlighted");
        }, i * 500);
      });
      res.edges.forEach((e, i) => {
        setTimeout(() => {
          cy.edges().forEach((edgeEl) => {
            if (edgeEl.data("source") === e.source && edgeEl.data("target") === e.target) {
              edgeEl.addClass("highlighted");
            }
          });
        }, i * 500 + 250);
      });
      setPathStatus({ nodes: res.nodes, edges: res.edges });
    }).catch((e) => setPathStatus({ error: String(e) }));
  }, [pathPicks]);

  const nodeDetail = graphData?.nodes.find((n) => n.key === selected);
  const types = Object.keys(TYPE_COLOR);

  return (
    <div className="flex flex-col md:flex-row h-full">
      <div className="flex-1 relative border-b md:border-b-0 md:border-r border-slate-800" style={{ minHeight: 320 }}>
        <div className="absolute top-2 left-2 z-10 flex flex-wrap gap-1 max-w-[90%]">
          {types.map((t) => (
            <button
              key={t}
              onClick={() =>
                setTypeFilter((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]))
              }
              className="text-[10px] px-2 py-0.5 rounded-full border"
              style={{
                borderColor: TYPE_COLOR[t],
                color: typeFilter.length && !typeFilter.includes(t) ? "#475569" : TYPE_COLOR[t],
                background: "rgba(15,23,42,0.7)",
              }}
            >
              {t}
            </button>
          ))}
        </div>
        <button
          onClick={() => {
            setPathMode((m) => !m);
            setPathPicks([]);
            setPathStatus(null);
            cyRef.current?.elements(".highlighted, .picked").removeClass("highlighted picked");
          }}
          className={`absolute top-2 right-2 z-10 text-xs px-3 py-1.5 rounded-md font-medium ${
            pathMode ? "bg-amber-500 text-slate-900" : "bg-slate-800 text-slate-300 border border-slate-700"
          }`}
        >
          {pathMode ? `Path mode: pick 2 nodes (${pathPicks.length}/2)` : "Show me the path"}
        </button>
        <div ref={containerRef} className="w-full h-full" />
      </div>

      <div className="w-full md:w-80 p-4 overflow-y-auto bg-slate-900/60">
        {pathMode && pathStatus && pathStatus !== "loading" && !pathStatus.error && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-amber-400 mb-2">Traversal</h3>
            {pathStatus.nodes.map((n, i) => (
              <div key={n.key} className="text-xs text-slate-300 mb-1">
                {i > 0 && <span className="text-slate-500"> —{pathStatus.edges[i - 1]?.edge_type}→ </span>}
                <span className="font-mono" style={{ color: TYPE_COLOR[n.node_type] }}>
                  {n.id}
                </span>
              </div>
            ))}
          </div>
        )}
        {nodeDetail ? (
          <div>
            <span className="text-xs uppercase font-semibold" style={{ color: TYPE_COLOR[nodeDetail.node_type] }}>
              {nodeDetail.node_type}
            </span>
            <h3 className="text-base font-semibold text-slate-100 mt-1 mb-2">
              {nodeDetail.name || nodeDetail.title || nodeDetail.id}
            </h3>
            <dl className="text-xs text-slate-400 space-y-1">
              {Object.entries(nodeDetail)
                .filter(([k]) => !["key"].includes(k))
                .map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="font-medium text-slate-500 w-28 shrink-0">{k}</dt>
                    <dd className="break-words">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                  </div>
                ))}
            </dl>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Click a node to see its properties and source documents.</p>
        )}
      </div>
    </div>
  );
}
