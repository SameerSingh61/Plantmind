"""The retirement capture agent. Different in kind from the briefing
agent: it generates questions, not summaries, and every question must
quote the retiring person's own words from a specific work order they
signed — people answer questions grounded in what they themselves wrote
far more readily than generic prompts.

Backed by AuraDB (Neo4j).
"""
import re
from datetime import date

from graph.llm import call_llm
from graph.neo4j_client import run

SYSTEM_PROMPT = """You help capture operational knowledge before an experienced engineer
retires. You will be given a work order completion note this person wrote
themselves, on a specific piece of equipment, along with the equipment tag
and work order id.

## Absolute rules

1. Your question must quote their own words from the note, verbatim, in
   quotation marks.
2. Ask what the informal practice actually is and under what conditions
   it is needed — do not ask a yes/no question.
3. Do not invent any technical detail not present in the note. Do not
   suggest what the answer might be.
4. One question only, under 40 words.

Output only the question, nothing else."""

# Phrases that mark a completion note as carrying undocumented tribal
# knowledge worth capturing, versus routine "no issues found" notes.
QUOTABLE_MARKERS = [
    "usual", "trick", "workaround", "not written down", "the way",
    "worth writing", "had to call", "steam-trace warm-up", "cleared by hand",
]


def _marker_pattern(marker: str) -> re.Pattern:
    # word-boundary match so "usual" doesn't false-positive inside
    # "unusual"
    return re.compile(r"\b" + re.escape(marker) + r"\b")


_MARKER_PATTERNS = [_marker_pattern(m) for m in QUOTABLE_MARKERS]


def _is_quotable(note: str) -> bool:
    lower = note.lower()
    return any(p.search(lower) for p in _MARKER_PATTERNS)


def _extract_quote(note: str) -> str:
    """Pull the most tribal-knowledge-bearing sentence out of a note for
    the fallback template (keeps the question grounded even without an
    LLM call)."""
    sentences = re.split(r"(?<=[.!?])\s+", note.strip())
    for s in sentences:
        lower = s.lower()
        if any(p.search(lower) for p in _MARKER_PATTERNS):
            return s.strip().rstrip(".")
    return sentences[0].strip().rstrip(".")


def _fallback_question(wo_id: str, equipment: str, note: str) -> str:
    quote = _extract_quote(note)
    return f'You signed {wo_id} on {equipment} with the note "{quote}" — what was the practice, and under what conditions is it needed?'


def generate_retirement_questions(orphaned_finding: dict) -> list[dict]:
    """orphaned_finding is one item from rule_orphaned_knowledge()."""
    equipment = orphaned_finding["equipment"]
    author_id = orphaned_finding["primary_author_id"]
    questions = []

    rows = run(
        "MATCH (wo:WorkOrder)-[:ASSIGNED_TO]->(p:Person {id: $author_id}) "
        "WHERE wo.id IN $wo_ids "
        "RETURN wo.id AS wo_id, wo.completion_notes AS note",
        author_id=author_id, wo_ids=orphaned_finding["work_orders"],
    )

    for row in rows:
        note = row["note"]
        if not note or not _is_quotable(note):
            continue
        wo_id = row["wo_id"]

        llm_text = call_llm(
            SYSTEM_PROMPT,
            f"Equipment: {equipment}\nWork order: {wo_id}\nCompletion note: \"{note}\"",
            max_tokens=100,
        )
        if llm_text:
            question, source = llm_text.strip(), "llm"
        else:
            question, source = _fallback_question(wo_id, equipment, note), "fallback_template"

        questions.append({
            "wo_id": wo_id, "equipment": equipment, "quoted_note": note,
            "question": question, "source": source,
        })
    return questions


def record_interview_answer(person_id: str, equipment_tag: str,
                              answer_text: str, wo_id: str, interview_date: str | None = None) -> str:
    """Writes the retiring engineer's answer back into the graph as a new
    Procedure node with a GOVERNS edge to the equipment — closing exactly
    the kind of gap the orphaned_knowledge rule was built to find. Returns
    the new node key."""
    interview_date = interview_date or date.today().isoformat()
    proc_id = f"INTERVIEW-{person_id}-{equipment_tag}-{wo_id}"
    proc_key = f"Procedure:{proc_id}"
    source_doc = f"interview:{person_id}:{interview_date}"

    run(
        "MERGE (p:Procedure {key: $proc_key}) "
        "SET p.id = $proc_id, p.title = $title, p.status = 'captured_from_interview', "
        "    p.revision = 'Rev 1', p.revision_date = $interview_date, "
        "    p.answer_text = $answer_text, p.source_document = $source_doc, "
        "    p.page = 1, p.confidence = 0.9 "
        "WITH p "
        "MATCH (eq:Equipment {id: $equipment_tag}) "
        "MERGE (p)-[r:GOVERNS]->(eq) "
        "SET r.source_document = $source_doc, r.page = 1, r.confidence = 0.9",
        proc_key=proc_key, proc_id=proc_id,
        title=f"Captured practice for {equipment_tag} (from retirement interview, ref {wo_id})",
        interview_date=interview_date, answer_text=answer_text,
        source_doc=source_doc, equipment_tag=equipment_tag,
    )
    return proc_key
