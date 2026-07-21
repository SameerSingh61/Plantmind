# PlantMind — Demo Video Script

**Target runtime: 3:30.** Rehearse this out loud with a stopwatch at least the fifteen times the build brief asks for — timing drifts fastest in the sections with live clicks, not the ones with just narration.

## Pre-flight, every single take

Do this before every recording pass, not just the first:

```bash
# terminal 1 — backend
cd ~/ET && lsof -ti:8123 -sTCP:LISTEN | xargs -r kill
uvicorn backend.main:app --port 8123 &

# terminal 2 — frontend
cd ~/ET/frontend && VITE_API_BASE=http://localhost:8123 npm run dev -- --port 5173 &

# reset state so the briefing feed is empty when the recording starts
curl -s -X POST http://localhost:8123/api/reset
```

Close every other browser tab. Full-screen the browser window. Zoom to 100% — screen recordings at odd zoom levels make citation text unreadable on a projector.

**No live call can break this recording.** No `OPENAI_API_KEY` is required — every scene below renders from the deterministic fallback templates if no key is set, and identically (just with better prose) if one is. Confirm this is true on your machine before the take, not during it.

---

## Scene 1 — Cold open (0:00–0:15)

**Screen:** black, or the PlantMind title card.

**Say:**
> "Visakhapatnam Steel Plant, January 2025. Eight workers died in a coke oven explosion. The gas sensors were reading correctly. Nothing connected that reading to a decision in time. That's not a sensor problem. That's a memory problem."

## Scene 2 — Thesis (0:15–0:30)

**Screen:** cut to the Briefings tab, empty state ("No conditions detected yet…").

**Say:**
> "Most teams here will build a document chatbot. We built the opposite. The plant has a memory, and it interrupts you before you make the mistake."

## Scene 3 — Storyline 1: the unclosed loop (0:30–1:30)

**Action:** Click **"Open WO-2026-4471 on P-101A"**.

**Say (while it loads — it's near-instant, so talk fast or pause on the button a beat):**
> "This button opens a real work order — a pump inspection ahead of monsoon season. Watch what happens next. Nobody asked a question."

**Action:** The briefing card renders. Zoom/highlight on the headline and citations.

**Say:**
> "In 2019, this same pump failed during a monsoon restart. The RCA recommended a seal-flush check. That recommendation was never folded into the startup procedure — and the graph just found that gap by walking one edge, not by a flag someone forgot to set. Two near-misses since have shown the exact same signature."

**Action:** Point at the **FOR YOUR DECISION** line.

**Say:**
> "It doesn't tell the engineer what to do. It asks. That's deliberate — a wrong prescription in a refinery isn't a bad UX moment, it's a hazard."

## Scene 4 — Storyline 2: the pattern nobody connected (1:30–2:00)

**Action:** Scroll down in the same Briefings tab to the **"tube sheet fouling across 3 shell tube hxs"** card (already present from the nightly sweep).

**Say:**
> "Five incidents, three different exchangers, four different engineers, over four years. Every RCA was filed and closed individually. No single report cross-references the others. One graph query — three-plus incidents, one failure mode, three-plus equipment of the same type — surfaces the pattern nobody was told to look for."

## Scene 5 — Show me the path (2:00–2:30)

**Action:** Switch to the **Explorer** tab. Click **"Show me the path"**. Click the P-101A node, then the missing-procedure node it connects to (or narrate live if the exact second click varies).

**Say:**
> "This is the fifteen seconds that actually prove it's a graph and not a chatbot. Pump, to incident, to the procedure that was recommended and never written — drawn live, edge by edge."

## Scene 6 — Storyline 3: the knowledge cliff (2:30–3:00)

**Action:** Switch to the **Retirement** tab. It should already show **V-2301**.

**Say:**
> "R. Krishnan retires next month. Fourteen work orders on this coker knockout drum, eleven signed by him, zero governing procedures. Everything anyone knows about this vessel lives in his own words in a maintenance log."

**Action:** Point at one generated question (ideally the WO-2019-33 one quoting "the usual workaround on the level bridle").

**Say:**
> "The question quotes him back to himself — people answer what they already said far more readily than a blank form. Type an answer, hit save—"

**Action:** Type a short answer, click **Save to graph**.

**Say:**
> "—and it just became a real Procedure node governing V-2301. The gap the system found, it just helped close."

## Scene 7 — Ask, and the refusal (3:00–3:20)

**Action:** Switch to **Ask** tab. Type: *"What is the design pressure rating for V-2301?"* Submit.

**Say:**
> "And when it doesn't know — it says so, and names who to ask, instead of guessing. In this building, a confidently wrong answer is worse than no answer."

## Scene 8 — Close (3:20–3:30)

**Screen:** cut back to title card or the acceptance-test checklist.

**Say:**
> "Twelve out of twelve acceptance tests pass against this exact build. The plant has a memory. And it interrupts you before you make the mistake."

---

## Fallback notes if something looks off mid-recording

- **Briefing card missing citations** — you forgot to `curl -X POST /api/reset` before this take; a prior take's duplicate got merged. Reset and retry.
- **Retirement tab empty** — the lookup box defaults to `V-2301`; if it's been changed in a prior take, retype it and hit **Look up**.
- **Path mode picks the wrong second node** — the layout is force-directed and re-settles per load; pick any node adjacent to P-101A in the legend colors (equipment=blue, incident=red) rather than memorizing pixel coordinates.
- **Anything involving a live model call is slow or errors** — it isn't required. Every scene above was verified against the non-LLM fallback path; if a key is set and a call times out, the code already falls back automatically and the on-screen text will barely change.
