#!/usr/bin/env python3
"""Build the Kaveri Refinery Unit 3 knowledge graph from the corpus and
load it into AuraDB (Neo4j). Same parsing/ontology logic as before; the
only thing that changed is where the result lives — Cypher writes to a
real graph database instead of a pickled networkx graph.

Node id convention unchanged: every node carries a `key` property of the
form f"{NodeType}:{natural_id}" (e.g. "Equipment:P-101A"), and a Neo4j
label matching its node_type (:Equipment, :Incident, ...). Edges are
Neo4j relationship types matching the ontology (PERFORMED_ON, GOVERNS,
...). Run from repo root:

    python3 graph/build.py
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graph.neo4j_client import run as neo4j_run  # noqa: E402
from graph.normalizer import TagNormalizer  # noqa: E402
from graph.parser import parse_all  # noqa: E402

CORPUS = ROOT / "corpus"

NODE_LABELS = [
    "Equipment", "Person", "RegulatoryClause", "Procedure",
    "FailureMode", "Incident", "WorkOrder",
]
EDGE_TYPES = [
    "HAS_FAILURE_MODE", "PERFORMED_ON", "ASSIGNED_TO", "INVOLVED",
    "EXHIBITED", "RECOMMENDED", "GOVERNS", "SATISFIES", "HAS_EXPERIENCE_WITH",
]


def nid(node_type: str, natural_id: str) -> str:
    return f"{node_type}:{natural_id}"


class GraphBuilder:
    """Accumulates nodes/edges in memory during parsing (so ingestion logic
    can look up "does this node exist yet" the same way it always could),
    then flushes everything to Neo4j in batched Cypher writes at the end —
    ~16 round trips total instead of ~500 individual ones."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}          # key -> {label, **props}
        self.edges: list[dict] = []                # {src, dst, edge_type, **props}
        self.normalizer: TagNormalizer | None = None
        self.warnings: list[str] = []

    def add_node(self, node_type: str, natural_id: str, **attrs):
        key = nid(node_type, natural_id)
        attrs.setdefault("confidence", 1.0)
        attrs.setdefault("source_document", None)
        attrs.setdefault("page", None)
        self.nodes[key] = {"label": node_type, "node_type": node_type, "id": natural_id, "key": key, **attrs}
        return key

    def __contains__(self, key: str) -> bool:
        return key in self.nodes

    def add_edge(self, src: str, edge_type: str, dst: str, **attrs):
        if src not in self.nodes or dst not in self.nodes:
            self.warnings.append(f"skip edge {edge_type}: missing endpoint {src} -> {dst}")
            return
        self.edges.append({"src": src, "dst": dst, "edge_type": edge_type, **attrs})

    def get_or_create_failure_mode(self, fm_raw: str | None) -> str | None:
        if not fm_raw:
            return None
        key = nid("FailureMode", fm_raw)
        if key not in self.nodes:
            self.add_node(
                "FailureMode", fm_raw,
                label_text=fm_raw.replace("_", " ").title(),
                source_document="controlled_vocabulary", confidence=1.0,
            )
        return key

    # -- ingestion steps (unchanged from the networkx version) ----------
    def load_equipment(self):
        with open(CORPUS / "00_equipment_register" / "equipment_register.csv") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            self.add_node(
                "Equipment", row["tag"],
                name=row["name"], type=row["type"], unit=row["unit"],
                service=row["service"], install_year=int(row["install_year"]),
                criticality=row["criticality"], pid_ref=row["pid_ref"],
                source_document="equipment_register.csv", page=1, confidence=1.0,
            )
        self.normalizer = TagNormalizer([r["tag"] for r in rows])
        print(f"Loaded {len(rows)} Equipment nodes")

    def load_personnel(self):
        data = json.loads((CORPUS / "08_personnel" / "personnel.json").read_text())
        for p in data:
            self.add_node(
                "Person", p["id"],
                name=p["name"], role=p["role"], unit=p["unit"],
                tenure_start=p["tenure_start"], tenure_end=p["tenure_end"] or "",
                status=p["status"], specialization=p["specialization"],
                source_document=f"{p['id']}_personnel_record.md", page=1, confidence=1.0,
            )
        print(f"Loaded {len(data)} Person nodes")

    def load_regulatory(self):
        count = 0
        for doc in parse_all(CORPUS / "07_regulatory"):
            fm = doc.front_matter
            for clause in fm.get("clauses", []):
                self.add_node(
                    "RegulatoryClause", clause["clause_id"],
                    doc_id=fm["doc_id"], doc_title=fm["title"], text=clause.get("text", ""),
                    source_document=doc.path.name, page=clause.get("source_page"),
                    confidence=1.0,
                )
                count += 1
        print(f"Loaded {count} RegulatoryClause nodes")

    def load_procedures(self):
        count = 0
        skipped_superseded = 0
        for doc in parse_all(CORPUS / "02_procedures"):
            fm = doc.front_matter
            if fm.get("status") == "superseded":
                skipped_superseded += 1
                continue
            pid = fm["procedure_id"]
            key = self.add_node(
                "Procedure", pid,
                title=fm.get("title"), status=fm.get("status"),
                revision=fm.get("revision"), revision_date=fm.get("revision_date"),
                source_document=doc.path.name, page=fm.get("source_page", 1),
                confidence=1.0,
            )
            for raw_tag in fm.get("governs_equipment") or []:
                eq_tag = self.normalizer.normalize(raw_tag)
                if eq_tag:
                    self.add_edge(key, "GOVERNS", nid("Equipment", eq_tag),
                                  source_document=doc.path.name, page=fm.get("source_page", 1))
                else:
                    self.warnings.append(f"{doc.path.name}: unresolvable equipment tag '{raw_tag}' in governs_equipment")
            for clause_id in fm.get("satisfies_clauses") or []:
                clause_key = nid("RegulatoryClause", clause_id)
                self.add_edge(key, "SATISFIES", clause_key,
                              source_document=doc.path.name, page=fm.get("source_page", 1))
            count += 1
        print(f"Loaded {count} Procedure nodes ({skipped_superseded} superseded revision(s) skipped)")

    def _resolve_incident_tags(self, doc, fm) -> list[tuple[str, float]]:
        raw_tags = fm.get("equipment_tags") or []
        resolved = []
        for raw in raw_tags:
            eq = self.normalizer.normalize(raw)
            if eq:
                resolved.append((eq, 1.0))
            else:
                self.warnings.append(f"{doc.path.name}: unresolvable equipment tag '{raw}'")
        if not resolved:
            body_tags = self.normalizer.extract_tags_from_body(doc.body)
            for eq in body_tags:
                resolved.append((eq, 0.75))
            if resolved:
                self.warnings.append(
                    f"{doc.path.name}: equipment_tags empty in front matter, "
                    f"recovered {[t for t, _ in resolved]} from body text (confidence 0.75)"
                )
        return resolved

    def load_incidents(self, directory: Path):
        count = 0
        for doc in parse_all(directory):
            fm = doc.front_matter
            iid = fm["incident_id"]
            page_count = fm.get("source_page_count", 1)
            key = self.add_node(
                "Incident", iid,
                classification=fm.get("classification", "incident"),
                date=fm.get("date"), unit=fm.get("unit"),
                regulatory_reportable=fm.get("regulatory_reportable", False),
                scan_type=fm.get("scan_type", "none"),
                source_document=doc.path.name, page=1, confidence=1.0,
            )
            tag_matches = self._resolve_incident_tags(doc, fm)
            for eq_tag, conf in tag_matches:
                self.add_edge(key, "INVOLVED", nid("Equipment", eq_tag),
                              source_document=doc.path.name, page=1, confidence=conf)

            fm_key = self.get_or_create_failure_mode(fm.get("failure_mode"))
            if fm_key:
                self.add_edge(key, "EXHIBITED", fm_key,
                              source_document=doc.path.name, page=1, confidence=1.0)

            for rec in fm.get("recommendations") or []:
                proc_id = rec.get("recommended_procedure_id")
                if not proc_id:
                    continue
                proc_key = nid("Procedure", proc_id)
                if proc_key in self.nodes:
                    self.add_edge(key, "RECOMMENDED", proc_key,
                                  text=rec.get("text"), owner=rec.get("owner"),
                                  owner_role=rec.get("owner_role"), target_date=rec.get("target_date"),
                                  source_document=doc.path.name, page=rec.get("source_page", page_count))
                else:
                    self.warnings.append(f"{doc.path.name}: recommended_procedure_id '{proc_id}' has no matching Procedure node")
            count += 1
        return count

    def load_work_orders(self):
        count = 0
        for doc in parse_all(CORPUS / "03_work_orders"):
            fm = doc.front_matter
            wo_id = fm["wo_id"]
            key = self.add_node(
                "WorkOrder", wo_id,
                raised_date=fm.get("raised_date"), work_type=fm.get("work_type"),
                priority=fm.get("priority"), permit_type=fm.get("permit_type"),
                planned_hours=fm.get("planned_hours") or 0, actual_hours=fm.get("actual_hours") or 0,
                completion_notes=fm.get("completion_notes") or "", status=fm.get("status"),
                source_document=doc.path.name, page=fm.get("source_page", 1), confidence=1.0,
            )
            for raw in fm.get("equipment_tags") or []:
                eq = self.normalizer.normalize(raw)
                if eq:
                    self.add_edge(key, "PERFORMED_ON", nid("Equipment", eq),
                                  source_document=doc.path.name, page=1)
                else:
                    self.warnings.append(f"{doc.path.name}: unresolvable equipment tag '{raw}'")
            assignee = fm.get("assigned_to")
            if assignee:
                person_key = nid("Person", assignee)
                if person_key in self.nodes:
                    self.add_edge(key, "ASSIGNED_TO", person_key,
                                  source_document=doc.path.name, page=1)
                else:
                    self.warnings.append(f"{doc.path.name}: unknown person id '{assignee}'")
            count += 1
        print(f"Loaded {count} WorkOrder nodes")

    def compute_experience_edges(self):
        pair_counts: dict[tuple[str, str], int] = {}
        wo_people: dict[str, list[str]] = {}
        wo_equipment: dict[str, list[str]] = {}
        for e in self.edges:
            if e["edge_type"] == "ASSIGNED_TO":
                wo_people.setdefault(e["src"], []).append(e["dst"])
            elif e["edge_type"] == "PERFORMED_ON":
                wo_equipment.setdefault(e["src"], []).append(e["dst"])
        for wo_key, people in wo_people.items():
            for eq_key in wo_equipment.get(wo_key, []):
                for person_key in people:
                    pair_counts[(person_key, eq_key)] = pair_counts.get((person_key, eq_key), 0) + 1

        for (person_key, eq_key), count in pair_counts.items():
            self.add_edge(person_key, "HAS_EXPERIENCE_WITH", eq_key,
                          work_order_count=count, source_document="derived:work_order_aggregation",
                          confidence=1.0)
        print(f"Computed {len(pair_counts)} HAS_EXPERIENCE_WITH edges")

    def build(self):
        self.load_equipment()
        self.load_personnel()
        self.load_regulatory()
        self.load_procedures()
        n_inc = self.load_incidents(CORPUS / "04_incidents")
        n_nm = self.load_incidents(CORPUS / "05_near_misses")
        print(f"Loaded {n_inc} Incident nodes + {n_nm} near-miss Incident nodes")
        self.load_work_orders()
        self.compute_experience_edges()

    # -- flush to AuraDB --------------------------------------------------
    def ensure_constraints(self):
        for label in NODE_LABELS:
            neo4j_run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE")

    def wipe(self):
        neo4j_run("MATCH (n) DETACH DELETE n")

    def flush(self):
        self.ensure_constraints()
        self.wipe()

        by_label: dict[str, list[dict]] = {}
        for node in self.nodes.values():
            by_label.setdefault(node["label"], []).append({k: v for k, v in node.items() if k != "label"})
        for label, batch in by_label.items():
            neo4j_run(
                f"UNWIND $rows AS row MERGE (n:{label} {{key: row.key}}) SET n += row",
                rows=batch,
            )
            print(f"  -> wrote {len(batch)} :{label} nodes")

        by_type: dict[str, list[dict]] = {}
        for edge in self.edges:
            by_type.setdefault(edge["edge_type"], []).append(
                {k: v for k, v in edge.items() if k not in ("src", "dst", "edge_type")} | {"src": edge["src"], "dst": edge["dst"]}
            )
        for edge_type, batch in by_type.items():
            neo4j_run(
                f"UNWIND $rows AS row "
                f"MATCH (a {{key: row.src}}), (b {{key: row.dst}}) "
                f"MERGE (a)-[r:{edge_type}]->(b) SET r += row",
                rows=batch,
            )
            print(f"  -> wrote {len(batch)} :{edge_type} edges")


def main():
    builder = GraphBuilder()
    builder.build()
    print(f"\nParsed {len(builder.nodes)} nodes, {len(builder.edges)} edges. Flushing to AuraDB...")
    builder.flush()

    n_count = neo4j_run("MATCH (n) RETURN count(n) AS c")[0]["c"]
    e_count = neo4j_run("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    print(f"\nAuraDB now has {n_count} nodes, {e_count} edges")

    if builder.warnings:
        print(f"\n{len(builder.warnings)} warnings:")
        for w in builder.warnings:
            print(f"  - {w}")
    return builder


if __name__ == "__main__":
    main()
