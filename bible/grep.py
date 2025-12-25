"""Grep-like verse search behavior for the Bible TUI."""

import curses
from textwrap import wrap

from . import position


def jump_to_grep_index(app, idx):
    if idx < 0 or idx >= len(app.state.grep.results):
        return
    m = app.state.grep.results[idx]
    pos = {
        "translation": m.translation,
        "book": m.book,
        "chapter": str(m.chapter),
        "verse": str(m.verse),
    }

    position.apply_position(app, pos)

    app.state.grep.override_text = None
    app.state.grep.override_title = None


def execute_search(app, pattern: str, scope):
    matches = app._search_manager.search_literal(pattern, scope)
    app.state.grep.results = matches
    app.state.grep.index = 0 if matches else -1
    label = app._search_manager.scope_label(scope)
    if matches:
        app.state.grep.override_text = app._search_manager.format_results(
            matches, app.text_width
        )
        app.state.grep.override_title = f" GREP {label}/{pattern}/ ({len(matches)})"
        app.state.grep.pattern = pattern
    else:
        app.state.grep.override_text = "No matches"
        app.state.grep.override_title = f" GREP {label}/{pattern}/ (0)"
        app.state.grep.pattern = pattern
        curses.beep()


def build_grep_pane_text(app):
    if not app.state.grep.results:
        app.state.grep.override_text = "No matches"
        app.state.grep.override_title = " GREP RESULTS (0)"
        return

    formatted_lines = []
    for idx, m in enumerate(app.state.grep.results):
        prefix = ">" if idx == app.state.grep.pane_index else " "
        base = f"{prefix} {m.translation} {m.book} {m.chapter}:{m.verse} — {m.text}"
        formatted_lines.append(base)

    wrap_width = max(1, app.text_width - 3)
    wrapped = []

    for line in formatted_lines:
        for wl in wrap(line, width=wrap_width):
            wrapped.append(wl)
        wrapped.append("")

    text = "\n".join(wrapped) if wrapped else "\n".join(formatted_lines)
    app.state.grep.override_text = text
    title_term = app.state.grep.pattern or "grep"
    app.state.grep.override_title = f" GREP /{title_term}/ ({len(formatted_lines)})"
