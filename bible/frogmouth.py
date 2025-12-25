"""Integration with Frogmouth Markdown viewer for the Bible TUI."""

import curses
import os
from pathlib import Path

from . import layout, selection, views


def open_in_frogmouth(app) -> None:
    """Open the current BSB chapter in Frogmouth, if available.

    Only works for BSB, resolves the markdown path, runs frogmouth,
    then restores the TUI layout and content.
    """

    trans = app.translations_win.get_selection_tuple()[1]
    if trans != "BSB":
        return

    book = app.books_win.get_selection_tuple()[1]
    chapter = app.chapters_win.get_selection_tuple()[1]
    base = Path(__file__).parent / "markdown" / "BSB" / book
    md = base / f"{chapter}.md"
    if not md.exists():
        md = base / "index.md"
    if not md.exists():
        return

    curses.endwin()
    try:
        os.system(f"frogmouth '{md}'")
    finally:
        app.stdscr.refresh()
        layout.layout_windows(app)
        selection.update_selections(app, app.reader)
        views.update_text(app, app.reader)
