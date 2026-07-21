#!/usr/bin/env python3
"""Renders the 3 P&ID drawings as real raster images (PNG), styled like a
schematic piping and instrumentation diagram: equipment symbols, tags, and
labeled connecting lines.

These stand in for "the real drawing" since Kaveri Refinery is fictional —
there is no proprietary document to fetch. What matters for closing the
scope gap is that a genuine image file exists and a vision model has to
actually read it; this script is the only place the ground-truth layout
(from generate_drawings.py) is used. scripts/extract_pid_vision.py, which
does the actual extraction, never imports this file or its data — it only
ever sees the rendered PNG, the same as a real vision-extraction pipeline
would.
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrow, Rectangle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_drawings import DRAWINGS  # noqa: E402

IMG_DIR = ROOT / "corpus" / "01_drawings" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

TYPE_BY_TAG = {}
with open(ROOT / "corpus" / "00_equipment_register" / "equipment_register.csv") as f:
    for row in csv.DictReader(f):
        TYPE_BY_TAG[row["tag"]] = row["type"]

COLS = 4
CELL_W, CELL_H = 4.2, 3.0


def _grid_positions(tags):
    positions = {}
    for i, tag in enumerate(tags):
        col = i % COLS
        row = i // COLS
        positions[tag] = (col * CELL_W + CELL_W / 2, -row * CELL_H - CELL_H / 2)
    return positions


def _draw_symbol(ax, tag, x, y):
    eq_type = TYPE_BY_TAG.get(tag, "")
    if eq_type == "centrifugal_pump":
        ax.add_patch(Circle((x, y), 0.42, fill=False, lw=1.6, edgecolor="black"))
        ax.text(x, y, "P", ha="center", va="center", fontsize=9, fontweight="bold")
    elif eq_type in ("pressure_vessel", "coke_drum"):
        ax.add_patch(Rectangle((x - 0.5, y - 0.75), 1.0, 1.5, fill=False, lw=1.6, edgecolor="black"))
    elif eq_type == "distillation_column":
        ax.add_patch(Rectangle((x - 0.4, y - 1.05), 0.8, 2.1, fill=False, lw=1.8, edgecolor="black"))
    elif eq_type == "fired_heater":
        ax.plot([x - 0.55, x, x + 0.55, x - 0.55], [y - 0.5, y + 0.55, y - 0.5, y - 0.5], lw=1.6, color="black")
    elif eq_type == "shell_tube_hx":
        ax.add_patch(Rectangle((x - 0.65, y - 0.32), 1.3, 0.64, fill=False, lw=1.4, edgecolor="black"))
        for dx in (-0.4, -0.13, 0.13, 0.4):
            ax.plot([x + dx, x + dx + 0.13], [y - 0.15, y + 0.15], lw=0.9, color="black")
    elif eq_type == "air_cooler":
        ax.add_patch(Rectangle((x - 0.65, y - 0.35), 1.3, 0.7, fill=False, lw=1.4, edgecolor="black", hatch="////"))
    elif eq_type == "ejector":
        ax.add_patch(Rectangle((x - 0.35, y - 0.3), 0.7, 0.6, fill=False, lw=1.3, edgecolor="black"))
    elif eq_type == "desalter":
        ax.add_patch(Rectangle((x - 0.55, y - 0.55), 1.1, 1.1, fill=False, lw=1.6, edgecolor="black"))
    else:
        ax.add_patch(Rectangle((x - 0.45, y - 0.35), 0.9, 0.7, fill=False, lw=1.3, edgecolor="black"))
    ax.text(x, y - 0.95, tag, ha="center", va="top", fontsize=8.5, fontfamily="monospace")


def _is_cross_page(tag: str) -> bool:
    return "(" in tag or "/" in tag


def render(drawing: dict):
    tags = drawing["equipment_tags"]
    positions = _grid_positions(tags)
    rows = (len(tags) + COLS - 1) // COLS

    fig, ax = plt.subplots(figsize=(COLS * CELL_W / 2.2, rows * CELL_H / 2.0 + 1.4))
    ax.set_xlim(-1, COLS * CELL_W + 1)
    ax.set_ylim(-rows * CELL_H - 1.4, 1.6)
    ax.set_aspect("equal")
    ax.axis("off")

    # title block, like a real drawing sheet
    ax.text(-0.8, 1.15, drawing["drawing_id"], fontsize=13, fontweight="bold", fontfamily="monospace")
    ax.text(-0.8, 0.65, drawing["title"], fontsize=9)
    ax.plot([-1, COLS * CELL_W + 1], [0.25, 0.25], lw=1, color="black")

    for tag in tags:
        x, y = positions[tag]
        _draw_symbol(ax, tag, x, y)

    edge_stub_count = 0
    for conn in drawing["connections"]:
        frm, to = conn["frm"], conn["to"]
        frm_cross, to_cross = _is_cross_page(frm), _is_cross_page(to)
        if frm_cross and to_cross:
            continue
        if frm_cross or to_cross:
            # stub arrow to the page edge for a connection that continues
            # onto a different drawing sheet
            local_tag = to if frm_cross else frm
            if local_tag not in positions:
                continue
            x, y = positions[local_tag]
            edge_stub_count += 1
            stub_y = y + (0.9 if frm_cross else -0.9)
            ax.annotate(
                "", xy=(x, stub_y), xytext=(x, y),
                arrowprops=dict(arrowstyle="->", lw=1.1, color="black"),
            )
            other_tag = frm if frm_cross else to
            ax.text(x + 0.15, stub_y, other_tag.split("(")[0].split("/")[0],
                     fontsize=6.5, fontfamily="monospace", color="dimgray")
            continue
        if frm not in positions or to not in positions:
            continue
        x1, y1 = positions[frm]
        x2, y2 = positions[to]
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", lw=1.0, color="black",
                             connectionstyle="arc3,rad=0.08"),
        )
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.12, conn["line_no"], fontsize=6, fontfamily="monospace",
                 color="dimgray", ha="center")

    out_path = IMG_DIR / f"{drawing['drawing_id']}.png"
    fig.savefig(out_path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Rendered {out_path} ({len(tags)} tags, {edge_stub_count} cross-sheet stubs)")


def main():
    for d in DRAWINGS:
        render(d)


if __name__ == "__main__":
    main()
