"""Find an exact excerpt inside a PDF page (no Streamlit imports).

Elsa's response carries a 1-based PDF page and the exact excerpt, but no
coordinates.  This module searches the PDF's own text layer for the excerpt so
the viewer can highlight it, and says honestly how good the match was.  A match
only helps the reviewer look in the right place; it never approves anything.
"""
import re

try:  # Optional at import time so the CLI keeps working without UI packages.
    import pymupdf
except ImportError:  # pragma: no cover - exercised only without requirements-ui.txt
    pymupdf = None

CHUNK_WORDS = 6
MIN_COVERAGE = 0.5
FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                      "–": "-", "—": "-", "−": "-", " ": " "})

EXACT, PARTIAL, OTHER_PAGE, NOT_FOUND, UNAVAILABLE = "exact", "partial", "other_page", "not_found", "unavailable"


def normalize(text):
    return " ".join(text.translate(FOLD).split())


def _rects(page, needle):
    found = []
    for rect in page.search_for(needle):
        found.append(dict(x=round(rect.x0, 2), y=round(rect.y0, 2),
                          width=round(rect.width, 2), height=round(rect.height, 2)))
    return found


def _search_page(page, excerpt):
    """Return (rects, coverage) for one page; coverage is the share of text matched."""
    whole = _rects(page, excerpt)
    if whole:
        return whole, 1.0
    words = excerpt.split()
    if len(words) <= CHUNK_WORDS:
        return [], 0.0
    chunks = [" ".join(words[i:i + CHUNK_WORDS]) for i in range(0, len(words), CHUNK_WORDS)]
    hits, rects = 0, []
    for chunk in chunks:
        found = _rects(page, chunk)
        if found:
            hits += 1
            rects.extend(found[:1])
    return rects, hits / len(chunks)


def locate(path, page_number, excerpt):
    """Locate ``excerpt`` near PDF page ``page_number``.

    Returns ``dict(status, page, rects)``.  ``status`` is one of: exact (whole
    excerpt on the cited page), partial (only some of it matched), other_page
    (found, but on a different page than cited), not_found, or unavailable
    (not a readable PDF / no text layer support).  Rectangles are in PDF points
    from the page's top-left corner, the convention the viewer uses.
    """
    result = dict(status=UNAVAILABLE, page=page_number, rects=[])
    if pymupdf is None or not str(path).lower().endswith(".pdf") or not normalize(excerpt):
        return result
    try:
        document = pymupdf.open(str(path))
    except (OSError, ValueError, RuntimeError):
        return result
    with document:
        needle = normalize(excerpt)
        count = document.page_count
        cited = page_number if isinstance(page_number, int) and 1 <= page_number <= count else None
        if cited:
            rects, coverage = _search_page(document[cited - 1], needle)
            if rects and coverage == 1.0:
                return dict(status=EXACT, page=cited, rects=rects)
            if rects and coverage >= MIN_COVERAGE:
                return dict(status=PARTIAL, page=cited, rects=rects)
        for index in range(count):
            if index + 1 == cited:
                continue
            rects, coverage = _search_page(document[index], needle)
            if rects and coverage >= MIN_COVERAGE:
                return dict(status=OTHER_PAGE, page=index + 1, rects=rects)
        return dict(status=NOT_FOUND, page=cited or 1, rects=[])


LABELS = {EXACT: "Excerpt found on the cited page",
          PARTIAL: "Only part of the excerpt was found on the cited page",
          OTHER_PAGE: "Excerpt found on a different page than cited",
          NOT_FOUND: "Excerpt not found in the PDF text (check the page by eye)",
          UNAVAILABLE: "Not checked"}
