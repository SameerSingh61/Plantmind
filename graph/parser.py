"""Front-matter + body parsing for corpus markdown documents.

Every corpus document is a YAML front-matter block (between `---` lines)
followed by a markdown body. Front-matter is what the ingestion pipeline
reads deterministically; the body is prose a human reads, and is only
consulted by ingestion as a fallback (see normalizer.extract_tags_from_body)
when front-matter omits something it should have had.
"""
import datetime
from dataclasses import dataclass
from pathlib import Path

import yaml


def _stringify_dates(obj):
    """YAML parses unquoted dates like 2026-07-19 into datetime.date
    objects. Normalize everything to ISO strings so the rest of the
    pipeline (and JSON export) never has to special-case the type."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _stringify_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify_dates(v) for v in obj]
    return obj


@dataclass
class ParsedDoc:
    path: Path
    front_matter: dict
    body: str


def parse_document(path: Path) -> ParsedDoc:
    text = path.read_text()
    if not text.startswith("---"):
        return ParsedDoc(path=path, front_matter={}, body=text)
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ParsedDoc(path=path, front_matter={}, body=text)
    _, fm_text, body = parts
    front_matter = _stringify_dates(yaml.safe_load(fm_text) or {})
    return ParsedDoc(path=path, front_matter=front_matter, body=body.strip())


def parse_all(directory: Path, pattern: str = "*.md"):
    for p in sorted(directory.glob(pattern)):
        yield parse_document(p)
