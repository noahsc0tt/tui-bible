"""Text view construction for the Bible TUI.

Builds the chapter text and title line for the TextWindow.
"""

import curses
import re
from textwrap import wrap


def get_current_reference(app):
    trans_name = app.translations_win.get_selection_tuple()[1]
    book_name = app.books_win.get_selection_tuple()[1]
    chapter_value = app.chapters_win.get_selection_tuple()[1]
    verse_str = app.verses_win.get_selection_tuple()[1]
    try:
        verse_int = int(verse_str) if verse_str else 1
    except Exception:
        verse_int = 1
    return trans_name, book_name, str(chapter_value), verse_int


def build_chapter_text(app, reader, verse_start: int) -> str:
    raw_text = reader.get_chapter_text(
        app.books_win.get_selection_tuple()[1],
        app.chapters_win.get_selection_tuple()[1],
        verse_start=verse_start,
    )
    verses = re.split(r"(?=\(\d+\)\s*)", raw_text)
    lines = []
    for v in verses:
        if not v.strip():
            continue
        wrapped = wrap(v, width=app.text_width - 3)
        lines.extend(wrapped)
        lines.append("")
    return "\n".join(lines[0 : curses.LINES - 2])


def update_text(app, reader):
    state = app.state
    if state.grep.override_text is not None:
        app.text_win.update_text_title(state.grep.override_title or " GREP RESULTS")
        app.text_win.update_text(
            state.grep.override_text,
            highlight_terms=[state.grep.pattern] if state.grep.pattern else None,
        )
        return

    trans_name, book_name, chapter_str, verse_int = get_current_reference(app)

    grep_indicator = ""
    if state.grep.results and state.grep.index >= 0:
        term = state.grep.pattern or "grep"
        if len(term) > 20:
            term = term[:20] + "\x01\x02\x03"
        grep_indicator = f"({term} {state.grep.index + 1}/{len(state.grep.results)}) "

    book_display = book_name
    text_title = (
        f" {grep_indicator}{book_display} {chapter_str}:{verse_int} [{trans_name}]"
    )

    text = build_chapter_text(app, reader, verse_int)

    app.text_win.update_text_title(text_title)
    highlight_terms = []
    if state.grep.results and state.grep.index >= 0 and state.grep.pattern:
        highlight_terms.append(state.grep.pattern)
    if state.search.query:
        highlight_terms.append(state.search.query)

    app.text_win.update_text(text, highlight_terms=highlight_terms or None)
