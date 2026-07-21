# PlantMind — Architecture

**Kaveri Refinery Unit 3 knowledge graph platform — ET AI Hackathon 2026, Problem Statement 1**

The core design bet: **traversal does the reasoning, the LLM only writes.** Four hardcoded graph rules detect conditions; language models never decide what matters, only narrate what a rule already found. That inversion is what keeps proactive alerts reliable instead of hallucinated.

---

## System overview

```mermaid
flowchart TB
    subgraph CORPUS["CORPUS — 150+ source documents"]
        direction LR
        C1["P&IDs\n(3 drawings)"]
        C2["Work orders\n(60)"]
        C3["Incidents &\nnear-misses (34)"]
        C4["Procedures\n(22)"]
        C5["OISD / Factory Act\nextracts (6)"]
        C6["Personnel\nrecords (12)"]
    end

    CORPUS --> ING["Ingestion pipeline\ngraph/parser.py + graph/normalizer.py\nYAML front-matter parse, tag-variant resolution,\nbody-text fallback extraction"]

    ING --> GRAPH[("Knowledge Graph\n7 node types / 9 edge types\nNeo4j (AuraDB Free)\n189 nodes · 319 edges")]

    GRAPH --> R1["Rule 1: unclosed_recommendation\nIncident --RECOMMENDED--> Procedure,\ncheck Procedure --GOVERNS--> Equipment"]
    GRAPH --> R2["Rule 2: recurrence_pattern\n3+ Incidents, 1 FailureMode,\n3+ Equipment of same type"]
    GRAPH --> R3["Rule 3: experience_gap\nPerson work_order_count vs\nteam median for equipment class"]
    GRAPH --> R4["Rule 4: orphaned_knowledge\nEquipment, 5+ WorkOrders,\n0 GOVERNS edges, 1 dominant author"]

    R1 --> BRIEF["Briefing Agent\ngraph/briefing_agent.py\nAbsolute Rules 1-5: cite everything,\nnever prescribe an action, refuse below 2 findings"]
    R3 --> BRIEF
    R2 --> FEED["Recurrence + Orphan feed\n(nightly-sweep style)"]
    R4 --> FEED
    R4 --> RETIRE["Retirement Capture Agent\ngraph/retirement_agent.py\nquestions quote the retiree's\nown work-order notes verbatim"]

    ASK["Field technician\nasks a question"] --> QUERY["Query Agent\ngraph/query_agent.py"]
    GRAPH --> QUERY
    QUERY -->|"context supports an answer"| ANSWER["Grounded answer\nevery sentence ends [DOC, p.N]"]
    QUERY -->|"context does not cover it"| REFUSE["Refusal\nnames the Person with the highest\nHAS_EXPERIENCE_WITH weight"]

    BRIEF --> API["FastAPI backend\nbackend/main.py"]
    FEED --> API
    ANSWER --> API
    REFUSE --> API
    RETIRE --> API

    API --> UI["React + Cytoscape.js frontend\nBriefings · Ask · Explorer · Retirement"]
    UI -->|"interview answer\nwrites back"| GRAPH

    classDef corpus fill:#141f2e,stroke:#8593a8,color:#e7ecf2
    classDef pipe fill:#101826,stroke:#46c2b9,color:#e7ecf2
    classDef graphdb fill:#101826,stroke:#f2a53c,color:#f2a53c,stroke-width:2px
    classDef rule fill:#141f2e,stroke:#46c2b9,color:#e7ecf2
    classDef agent fill:#141f2e,stroke:#e2626b,color:#e7ecf2
    classDef ui fill:#0a0f16,stroke:#f2a53c,color:#f2a53c,stroke-width:2px
    class C1,C2,C3,C4,C5,C6 corpus
    class ING pipe
    class GRAPH graphdb
    class R1,R2,R3,R4 rule
    class BRIEF,QUERY,RETIRE agent
    class API,UI ui
```

---

## The one traversal that fires the flagship demo

Storyline 1 — the unclosed loop on **P-101A** — is a single traversal, not a rules engine:

```mermaid
sequenceDiagram
    participant WO as WorkOrder<br/>WO-2026-4471
    participant EQ as Equipment<br/>P-101A
    participant INC as Incident<br/>INC-2019-04
    participant PROC as Procedure<br/>REC-INC-2019-04-1
    participant NM as near-misses<br/>NM-2022-11, NM-2024-07
    participant AGENT as Briefing Agent

    Note over WO: New work order opens<br/>(monsoon, corrective maintenance)
    WO->>EQ: PERFORMED_ON
    EQ->>INC: <-- INVOLVED
    INC->>PROC: RECOMMENDED
    PROC-->>EQ: GOVERNS? — NO EDGE FOUND
    Note over PROC,EQ: Gap detected by absence,<br/>not a flag field
    EQ->>NM: <-- INVOLVED (same failure_mode)
    Note over NM: 2 near-misses, same signature,<br/>2022 and 2024
    INC-->>AGENT: findings: [unimplemented_recommendation, recurrence]
    AGENT-->>WO: unprompted briefing, <br/>cited, no prescribed action
```

---

## Ontology — 7 node types, 9 edges, nothing added

| Node type | Carries |
|---|---|
| `Equipment` | tag, name, type, unit, criticality, pid_ref |
| `FailureMode` | canonical failure taxonomy (mechanical_seal_failure, tube_sheet_fouling, …) |
| `WorkOrder` | raised_date, work_type, priority, completion_notes |
| `Incident` | classification (incident / near_miss), date, failure mode link |
| `Procedure` | revision, status, satisfies_clauses |
| `RegulatoryClause` | doc_id, clause text, source page |
| `Person` | role, tenure, specialization |

Every node also carries `source_document`, `page`, and `confidence` — the triplet that makes citation, and refusal, possible.

| Edge | From → To | Notes |
|---|---|---|
| `HAS_FAILURE_MODE` | Equipment → FailureMode | known failure modes for the equipment class |
| `PERFORMED_ON` | WorkOrder → Equipment | |
| `ASSIGNED_TO` | WorkOrder → Person | |
| `INVOLVED` | Incident → Equipment | |
| `EXHIBITED` | Incident → FailureMode | |
| `RECOMMENDED` | Incident → Procedure | carries owner + target date |
| `GOVERNS` | Procedure → Equipment | its *absence* is the signal for the unclosed-loop rule |
| `SATISFIES` | Procedure → RegulatoryClause | |
| `HAS_EXPERIENCE_WITH` | Person → Equipment | derived by aggregating WorkOrder edges, not extracted |

---

## Running on real Neo4j (AuraDB Free)

No Docker in the build environment, so instead of a local container the graph runs on a free-tier AuraDB instance — a real, hosted Neo4j database, not an in-memory substitute. Every trigger rule in `graph/rules.py` is genuine Cypher, executed via the official `neo4j` Python driver (`graph/neo4j_client.py`); `graph/build.py` ingests the corpus straight into it with batched `UNWIND`/`MERGE` writes.

## Where each judging criterion lives

- **Innovation** — the push-not-pull briefing feed and the retirement-capture agent (questions grounded in the retiree's own words) are both agent patterns most teams won't build.
- **Technical Excellence** — compound risk detection is graph topology, not a model guess; the tag normalizer resolves real spelling drift (`P101A` / `P-101 A` / `P-101A`).
- **Scalability** — runs on real Neo4j (AuraDB), not an in-memory graph — the same instance scales to a real refinery's document volume without an architecture change.
- **Business Impact** — closes exactly the gap the Vizag Steel Plant investigation named: data present, unacted upon.
- **User Experience** — mobile-first query surface, visible refusal instead of a confident wrong answer, flat non-alarming briefing tone so engineers keep reading.
