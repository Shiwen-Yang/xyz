"""Find an exact excerpt inside a PDF page (no Streamlit imports).

Elsa's response carries a 1-based PDF page and the exact excerpt, but no
coordinates.  This module searches the PDF's own text layer for the excerpt so
the viewer can highlight it, and says honestly how good the match was.  A match
only helps the reviewer look in the right place; it never approves anything.
"""
import difflib
import unicodedata

try:  # Optional at import time so the CLI keeps working without UI packages.
    import pymupdf
except ImportError:  # pragma: no cover - exercised only without requirements-ui.txt
    pymupdf = None

MIN_RATIO = 0.8        # similarity needed to accept a fuzzy span
ANCHOR = 24            # characters used to anchor the start and end of a passage
LINE_GAP = 0.8         # lines closer than this many line-heights belong to one block

EXACT, PARTIAL, OTHER_PAGE, NOT_FOUND, UNAVAILABLE = "exact", "partial", "other_page", "not_found", "unavailable"
CONTINUES = "continues"  # one passage running over a page break


def normalize(text):
    return " ".join(text.translate(FOLD).split())


def key(text):
    """Compare text ignoring case, spacing, punctuation, hyphens and ligatures."""
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def _page_words(page):
    """(stream, owner, words): the page's letters joined into one string, the word each letter came
    from, and the words themselves as (x0, y0, x1, y1, line_id) in the PDF's own reading order."""
    words, pieces, owner = [], [], []
    for x0, y0, x1, y1, text, block, line, _ in page.get_text("words"):
        folded = key(text)
        if not folded:
            continue
        pieces.append(folded)
        owner.extend([len(words)] * len(folded))
        words.append((x0, y0, x1, y1, (block, line)))
    return "".join(pieces), owner, words


def _span_rects(words, first, last):
    """One box per block of consecutive lines, plus small boxes on the first and last word."""
    lines = []
    for x0, y0, x1, y1, line_id in words[first:last + 1]:
        if lines and lines[-1]["id"] == line_id:
            box = lines[-1]
            box.update(x0=min(box["x0"], x0), y0=min(box["y0"], y0), x1=max(box["x1"], x1), y1=max(box["y1"], y1))
        else:
            lines.append(dict(id=line_id, x0=x0, y0=y0, x1=x1, y1=y1))
    blocks = []
    for line in lines:
        previous = blocks[-1] if blocks else None
        height = line["y1"] - line["y0"]
        if (previous and line["y0"] <= previous["y1"] + LINE_GAP * height
                and line["x0"] < previous["x1"] and line["x1"] > previous["x0"]):
            previous.update(x0=min(previous["x0"], line["x0"]), y0=min(previous["y0"], line["y0"]),
                            x1=max(previous["x1"], line["x1"]), y1=max(previous["y1"], line["y1"]))
        else:
            blocks.append(dict(line))

    def box(x0, y0, x1, y1, *_):
        return dict(x=round(x0, 2), y=round(y0, 2), width=round(x1 - x0, 2), height=round(y1 - y0, 2))
    marks = [box(*words[first][:4]), box(*words[last][:4])] if last > first else [box(*words[first][:4])]
    return [box(b["x0"], b["y0"], b["x1"], b["y1"]) for b in blocks], marks


def _occurrences(stream, needle):
    start = stream.find(needle)
    while start != -1:
        yield start
        start = stream.find(needle, start + 1)


def _find_span(stream, wanted):
    """(start, end, exact) character offsets of the best match for ``wanted`` in ``stream``, else None."""
    start = stream.find(wanted)
    if start != -1:
        return start, start + len(wanted), True
    if len(wanted) < 2 * ANCHOR:
        return None
    heads = list(_occurrences(stream, wanted[:ANCHOR]))
    tails = list(_occurrences(stream, wanted[-ANCHOR:]))
    best = None
    for head in heads:
        for tail in tails:
            end = tail + ANCHOR
            if end <= head or not 0.6 * len(wanted) <= end - head <= 1.6 * len(wanted):
                continue
            ratio = difflib.SequenceMatcher(None, stream[head:end], wanted, autojunk=False).ratio()
            if ratio >= MIN_RATIO and (best is None or ratio > best[0]):
                best = (ratio, head, end)
    if best:
        return best[1], best[2], False
    matcher = difflib.SequenceMatcher(None, stream, wanted, autojunk=False)
    block = matcher.find_longest_match(0, len(stream), 0, len(wanted))
    if block.size >= max(ANCHOR, len(wanted) // 2):
        return block.a, block.a + block.size, False
    return None


def _search_page(page, wanted):
    """(rects, marks, coverage) for one page; coverage is 1.0 for a whole-passage match."""
    stream, owner, words = _page_words(page)
    found = _find_span(stream, wanted) if stream else None
    if not found:
        return [], [], 0.0
    start, end, exact = found
    rects, marks = _span_rects(words, owner[start], owner[end - 1])
    return rects, marks, 1.0 if exact else max(0.5, (end - start) / len(wanted) * 0.99)


def _search_across(document, first_page, wanted):
    """Look for a passage that starts on 1-based ``first_page`` and ends on the next page, ignoring any
    running header, footer or page number between the two halves. Returns parts [dict(page, rects, marks)]
    or None."""
    if not 1 <= first_page < document.page_count:
        return None
    streams, owner, words, page_of = [], [], [], []
    for number in (first_page, first_page + 1):
        stream, own, page_words = _page_words(document[number - 1])
        base = len(words)
        owner.extend(i + base for i in own)
        words.extend(page_words)
        page_of.extend([number] * len(page_words))
        streams.append(stream)
    found = _find_span("".join(streams), wanted)
    if not found:
        return None
    start, end, _ = found
    first, last = owner[start], owner[end - 1]
    if page_of[first] == page_of[last]:
        return None  # not actually a continuation; the single-page search owns this case
    boundary = page_of.index(first_page + 1)
    head, head_marks = _span_rects(words, first, boundary - 1)
    tail, tail_marks = _span_rects(words, boundary, last)
    return [dict(page=first_page, rects=head, marks=head_marks[:1]),
            dict(page=first_page + 1, rects=tail, marks=tail_marks[-1:])]


def locate(path, page_number, excerpt):
    """Locate ``excerpt`` near PDF page ``page_number``.

    Returns ``dict(status, page, rects, marks)``.  ``status`` is one of: exact (whole
    excerpt on the cited page), partial (wording differs or only part matched), other_page
    (found, but on a different page than cited), not_found, or unavailable
    (not a readable PDF / no text layer support).  ``rects`` are the boxes around the passage
    and ``marks`` the first and last word, in PDF points from the page's top-left corner,
    the convention the viewer uses.  Matching ignores case, spacing, punctuation, hyphenation
    and ligatures.
    """
    result = dict(status=UNAVAILABLE, page=page_number, rects=[], marks=[])
    if pymupdf is None or not str(path).lower().endswith(".pdf") or not key(excerpt):
        return result
    try:
        document = pymupdf.open(str(path))
    except (OSError, ValueError, RuntimeError):
        return result
    with document:
        wanted = key(excerpt)
        count = document.page_count
        cited = page_number if isinstance(page_number, int) and 1 <= page_number <= count else None
        if cited:
            rects, marks, coverage = _search_page(document[cited - 1], wanted)
            if rects and coverage == 1.0:
                return dict(status=EXACT, page=cited, rects=rects, marks=marks)
            for first_page in (cited - 1, cited):  # the passage may start on the cited page or end on it
                parts = _search_across(document, first_page, wanted)
                if parts:
                    return dict(status=CONTINUES, page=parts[0]["page"], rects=parts[0]["rects"], marks=parts[0]["marks"], parts=parts)
            partial = None
            if rects:
                partial = dict(status=PARTIAL, page=cited, rects=rects, marks=marks)
        else:
            partial = None
        elsewhere = None
        for index in range(count):
            if index + 1 == cited:
                continue
            rects, marks, coverage = _search_page(document[index], wanted)
            if rects and coverage == 1.0:
                return dict(status=OTHER_PAGE, page=index + 1, rects=rects, marks=marks)
            if rects and not elsewhere:
                elsewhere = dict(status=OTHER_PAGE, page=index + 1, rects=rects, marks=marks)
        if partial:
            return partial
        if elsewhere:
            return elsewhere
        return dict(status=NOT_FOUND, page=cited or 1, rects=[], marks=[])


LABELS = {EXACT: "Excerpt found on the cited page",
          PARTIAL: "Only part of the excerpt was found on the cited page",
          OTHER_PAGE: "Excerpt found on a different page than cited",
          NOT_FOUND: "Excerpt not found in the PDF text (check the page by eye)",
          CONTINUES: "Passage continues across a page break",
          UNAVAILABLE: "Not checked"}
