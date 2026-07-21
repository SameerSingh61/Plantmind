"""Equipment tag normalization.

Real documents spell the same tag inconsistently (P101A, P-101 A, P-101A).
The normalizer strips everything but alphanumerics and compares against the
same stripped form of every canonical tag in the equipment register. This
single trick resolves every spelling variant we've planted in the corpus
without any per-tag special-casing.
"""
import re

_STRIP_RE = re.compile(r"[^A-Za-z0-9]")


def _stripped(tag: str) -> str:
    return _STRIP_RE.sub("", tag).upper()


class TagNormalizer:
    def __init__(self, canonical_tags: list[str]):
        self.canonical_tags = list(canonical_tags)
        self._lookup = {_stripped(t): t for t in canonical_tags}
        # longest-first so body-text scanning doesn't let a short tag
        # shadow a longer one that contains it as a substring
        self._by_length = sorted(canonical_tags, key=len, reverse=True)

    def normalize(self, raw_tag: str) -> str | None:
        if raw_tag is None:
            return None
        return self._lookup.get(_stripped(raw_tag))

    def extract_tags_from_body(self, body_text: str) -> list[str]:
        """Fallback for documents where a structured tag field was left
        empty. Scans prose for any canonical tag spelled in its canonical
        form or a whitespace/hyphen variant of it."""
        found = []
        for tag in self._by_length:
            pattern = re.compile(
                r"\b" + re.escape(tag).replace(r"\-", r"[\s-]?") + r"\b"
            )
            if pattern.search(body_text):
                found.append(tag)
        return found
