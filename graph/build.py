#!/usr/bin/env python3
"""Build the Kaveri Refinery Unit 3 knowledge graph from the corpus.

Node id convention: f"{NodeType}:{natural_id}" (e.g. "Equipment:P-101A",
"Incident:INC-2019-04"). Every node carries source_document, page, and
confidence per the ontology. Run from repo root:

    python3 graph/build.py

Writes data/graph.pkl (networkx.MultiDiGraph, pickled) and
data/graph_export.json (Cytoscape-friendly node/edge lists for the frontend).
"""
import csv
import json
import pickle
import re
import sys
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graph.normalizer import TagNormalizer  # noqa: E402
from graph.parser import parse_all, parse_document  # noqa: E402

CORPUS = ROOT / "corpus"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


def nid(node_type: str, natural_id: str) -> str:
    return f"{node_type}:{natural_id}"


class GraphBuilder:
    def __init__(self):
        self.g = nx.MultiDiGraph()
        self.normalizer: TagNormalizer | None = None
        self.warnings: list[str] = []

    # -- node helpers --------------------------------------------------
    def add_node(self, node_type: str, natural_id: str, **attrs):
        key = nid(node_type, natural_id)
        attrs.setdefault("confidence", 1.0)
        attrs.setdefault("source_document", None)
        attrs.setdefault("page", None)
        self.g.add_node(key, node_type=node_type, id=natural_id, **attrs)
        return key

    def add_edge(self, src: str, edge_type: str, dst: str, **attrs):
        if src not in self.g or dst not in self.g:
            self.warnings.append(f"skip edge {edge_type}: missing endpoint {src} -> {dst}")
            return
        self.g.add_edge(src, dst, key=edge_type, edge_type=edge_type, **attrs)

    def get_or_create_failure_mode(self, fm_raw: str | None) -> str | None:
        if not fm_raw:
            return None
        key = nid("FailureMode", fm_raw)
        if key not in self.g:
            self.add_node(
                "FailureMode", fm_raw,
                label=fm_raw.replace("_", " ").title(),
                source_document="controlled_vocabulary",
                confidence=1.0,
            )
        return key

    # -- ingestion steps -------------------------------------------------
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
                tenure_start=p["tenure_start"], tenure_end=p["tenure_end"],
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
        """Returns list of (canonical_tag, confidence). Falls back to a
        body-text scan when the front-matter field was left empty --
        this is the deliberate messiness case in INC-2022-16."""
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
                if proc_key in self.g:
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
                planned_hours=fm.get("planned_hours"), actual_hours=fm.get("actual_hours"),
                completion_notes=fm.get("completion_notes"), status=fm.get("status"),
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
                if person_key in self.g:
                    self.add_edge(key, "ASSIGNED_TO", person_key,
                                  source_document=doc.path.name, page=1)
                else:
                    self.warnings.append(f"{doc.path.name}: unknown person id '{assignee}'")
            count += 1
        print(f"Loaded {count} WorkOrder nodes")

    def compute_experience_edges(self):
        """HAS_EXPERIENCE_WITH is derived, not extracted: aggregate existing
        ASSIGNED_TO + PERFORMED_ON edges per (Person, Equipment) pair."""
        pair_counts: dict[tuple[str, str], int] = {}
        for wo_node, attrs in self.g.nodes(data=True):
            if attrs.get("node_type") != "WorkOrder":
                continue
            people = [v for _, v, d in self.g.out_edges(wo_node, data=True) if d.get("edge_type") == "ASSIGNED_TO"]
            equipment = [v for _, v, d in self.g.out_edges(wo_node, data=True) if d.get("edge_type") == "PERFORMED_ON"]
            for person_key in people:
                for eq_key in equipment:
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
        return self.g


def save(g: nx.MultiDiGraph):
    with open(DATA / "graph.pkl", "wb") as f:
        pickle.dump(g, f)

    nodes = []
    for key, attrs in g.nodes(data=True):
        node = dict(attrs)
        node["key"] = key
        nodes.append(node)
    edges = []
    for u, v, attrs in g.edges(data=True):
        edge = dict(attrs)
        edge["source"] = u
        edge["target"] = v
        edges.append(edge)
    (DATA / "graph_export.json").write_text(json.dumps({"nodes": nodes, "edges": edges}, indent=2, default=str))


def main():
    builder = GraphBuilder()
    g = builder.build()
    save(g)
    print(f"\nGraph built: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    if builder.warnings:
        print(f"\n{len(builder.warnings)} warnings:")
        for w in builder.warnings:
            print(f"  - {w}")
    return builder, g


if __name__ == "__main__":
    main()
