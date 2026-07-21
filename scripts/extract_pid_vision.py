#!/usr/bin/env python3
"""Real vision extraction over the rendered P&ID images.

Deliberately does NOT import generate_drawings.py or draw_pid_images.py —
this script only ever sees the PNG files, exactly like a real extraction
pipeline would. It calls a vision-capable model (gpt-4o) and writes raw,
UNVERIFIED output to corpus/01_drawings/extracted/. A human (or an agent
acting as one) then hand-verifies that output against the source image
before it's allowed to become the actual corpus file — see
scripts/verify_pid_extraction.py and the corrections log next to it.
"""
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graph.llm import MODEL, get_client  # noqa: E402  (reuses the same client config)

IMG_DIR = ROOT / "corpus" / "01_drawings" / "images"
OUT_DIR = ROOT / "corpus" / "01_drawings" / "extracted"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXTRACTION_PROMPT = """This image is a piping and instrumentation diagram (P&ID) sheet from an
industrial refinery unit. Extract, as JSON only (no markdown fence, no commentary):

{
  "drawing_id": "<the drawing number printed top-left, e.g. PID-CDU-001>",
  "title": "<the title line under the drawing number>",
  "equipment_tags": ["<every distinct equipment tag label you can read, e.g. P-101A, E-204, V-2301>"],
  "connections": [
    {"from": "<tag>", "to": "<tag>", "line_no": "<line number label near the connecting arrow, if legible>", "service": "<best guess at the service/fluid from context, or null>"}
  ],
  "cross_sheet_references": ["<any tag or drawing number pointing off-page, e.g. an arrow labeled with another drawing's tag>"],
  "low_confidence_notes": ["<anything you found ambiguous, overlapping, or hard to read>"]
}

Read the image carefully — some lines cross or overlap. If a line number is
obscured, set it to null rather than guessing. List every equipment box/
circle/triangle symbol you can find, even if you can't determine all of its
connections."""


def extract_one(image_path: Path) -> dict:
    client = get_client()
    if client is None:
        raise RuntimeError(
            "No OpenAI client available (OPENAI_API_KEY not set) — vision "
            "extraction requires a live model call, there is no offline "
            "fallback for this step."
        )
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    response = client.chat.completions.create(
        model=MODEL,
        max_completion_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def main():
    images = sorted(IMG_DIR.glob("*.png"))
    if not images:
        print(f"No images found in {IMG_DIR} — run scripts/draw_pid_images.py first.")
        return
    for img_path in images:
        print(f"Extracting {img_path.name}...")
        try:
            result = extract_one(img_path)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue
        out_path = OUT_DIR / f"{img_path.stem}-raw.json"
        out_path.write_text(json.dumps(result, indent=2))
        print(f"  -> {out_path} ({len(result.get('equipment_tags', []))} tags, "
              f"{len(result.get('connections', []))} connections extracted)")


if __name__ == "__main__":
    main()
