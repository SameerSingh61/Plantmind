"""The proactive briefing agent. Fires unprompted when a trigger rule
returns a payload with 2+ findings. The LLM only narrates what the graph
traversal already proved — see graph/rules.py for the reasoning step.
"""
import json

from graph.llm import call_llm

SYSTEM_PROMPT = """You are the operations intelligence layer for Kaveri Refinery Unit 3.
You generate short, factual briefings that appear unprompted on a
maintenance engineer's screen when the knowledge graph detects a
condition worth their attention.

You will receive a JSON payload containing a trigger event and a list
of findings retrieved from the plant knowledge graph. Every finding
carries a source document reference.

## Absolute rules

1. State ONLY what appears in the payload. You have no other knowledge
   of this plant. If a detail is not in the payload, it does not exist.
2. Every factual sentence must end with a citation in the form
   [DOC, p.N]. Sentences without a source in the payload must not be
   written at all.
3. Never recommend a specific technical procedure, torque value,
   isolation step, or safety action. You surface what the record shows
   and who owns the decision. You are not the engineer.
4. Never estimate probability, risk score, or severity. The graph found
   a pattern; a human judges its significance.
5. If the payload contains fewer than two findings, output exactly:
   NO_BRIEFING

## Output format

HEADLINE: One line, maximum 12 words, stating the condition. Neutral
tone — no alarm language, no exclamation, no "URGENT".

WHAT THE RECORD SHOWS: Two to four sentences. Chronological. Each
sentence covers one finding and ends with its citation.

WHY THIS SURFACED NOW: One sentence connecting the trigger event to
the findings.

FOR YOUR DECISION: One question directed at the engineer. It must be
answerable by them and must not imply the correct answer.

## Tone

Write like a colleague who read the file, not like a safety poster.
No adjectives of severity. No "critical", "dangerous", "immediately".
The facts carry the weight; language that inflates them makes engineers
distrust the system and stop reading it.

Maximum 90 words total, excluding citations."""


def _fallback_render(payload: dict) -> str:
    """Deterministic, non-LLM render used when no API key is configured
    or the live call fails. Same structure as the system prompt's
    required output, built directly from the payload so the demo never
    depends on a live model call."""
    findings = payload["findings"]
    event = payload["trigger_event"]

    unimplemented = [f for f in findings if f["type"] == "unimplemented_recommendation"]
    recurrence = [f for f in findings if f["type"] == "recurrence"]
    exp_gap = [f for f in findings if f["type"] == "experience_gap"]

    lead = unimplemented[0] if unimplemented else findings[0]
    headline = f"{event['equipment']} work order reopens a {lead.get('failure_mode', 'a prior').replace('_', ' ')} question"

    lines = []
    if unimplemented:
        u = unimplemented[0]
        lines.append(
            f"On {u['date']}, {u['incident']} recommended \"{u['recommendation']}\", "
            f"owned by {u['rec_owner']}, target {u['rec_target_date']} "
            f"[{u['source']['doc']}, p.{u['source']['page']}]."
        )
        lines.append(
            f"That recommendation has no linked procedure governing {event['equipment']} today "
            f"[{u['source']['doc']}, p.{u['source']['page']}]."
        )
    if recurrence:
        r = recurrence[0]
        lines.append(
            f"{r['count']} near-miss record(s) ({', '.join(r['records'])}) later showed the same "
            f"{r['shared_failure_mode'].replace('_', ' ')} signature [{r['source']['doc']}, p.{r['source']['page']}]."
        )
    if exp_gap:
        e = exp_gap[0]
        lines.append(
            f"{e['person']} has {e['prior_work_orders_on_equipment_class']} prior work order(s) on this "
            f"equipment class against a team median of {e['team_median']} [work_order_index]."
        )

    why_now = (
        f"This surfaced because {event['work_order']} opened on {event['equipment']} on {event['raised']}, "
        f"a {event.get('season_context', 'routine')}-season {event['work_type'].replace('_', ' ')}."
    )
    question = f"Given what the record shows, should this work order close the loop on the {u['date'][:4]} recommendation before proceeding?" if unimplemented else "Given what the record shows, how should this work order proceed?"

    text = (
        f"HEADLINE: {headline}\n\n"
        f"WHAT THE RECORD SHOWS: {' '.join(lines)}\n\n"
        f"WHY THIS SURFACED NOW: {why_now}\n\n"
        f"FOR YOUR DECISION: {question}"
    )
    return text


def generate_briefing(payload: dict) -> dict:
    """Returns {"text": str, "source": "llm"|"fallback_template", "payload": dict}.
    NO_BRIEFING (or None payload) short-circuits without calling the LLM."""
    if payload is None or len(payload.get("findings", [])) < 2:
        return {"text": "NO_BRIEFING", "source": "rule", "payload": payload}

    user_message = json.dumps(payload, indent=2)
    llm_text = call_llm(SYSTEM_PROMPT, user_message, max_tokens=350)
    if llm_text and llm_text != "NO_BRIEFING":
        return {"text": llm_text, "source": "llm", "payload": payload}

    return {"text": _fallback_render(payload), "source": "fallback_template", "payload": payload}
