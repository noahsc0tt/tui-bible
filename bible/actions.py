"""Key handling and shortcuts for the Bible TUI app."""

import curses

from .metadata import parse_reference
from .grep import build_grep_pane_text, execute_search, jump_to_grep_index
from .prompts import prompt_input_cancelable
from .frogmouth import open_in_frogmouth
from . import layout


UP_KEYS = (curses.KEY_UP, ord("k"))
DOWN_KEYS = (curses.KEY_DOWN, ord("j"))
LEFT_KEYS = (curses.KEY_LEFT, ord("h"))
RIGHT_KEYS = (curses.KEY_RIGHT, ord("l"))
ENTER_KEYS = (ord("\n"), ord("\r"))


def handle_key(app, key: int) -> bool:
    """Handle a single keypress for the Main app.

    Returns True if selections/text should be refreshed, False if the
    caller should skip its usual update_selections/update_text step
    (used for no-op movements and similar cases).
    """

    state = app.state

    # Up / down: either move in grep pane (if open) or in list
    if key in UP_KEYS:
        if state.grep.override_text is not None:
            if state.grep.results:
                prev = state.grep.pane_index
                state.grep.pane_index = max(0, state.grep.pane_index - 1)
                if state.grep.pane_index == prev:
                    return False
                build_grep_pane_text(app)
            else:
                curses.beep()
                return False
        else:
            moved = app.selected_window[1].increment_selection(-1)
            if not moved:
                return False

    elif key in DOWN_KEYS:
        if state.grep.override_text is not None:
            if state.grep.results:
                prev = state.grep.pane_index
                state.grep.pane_index = min(
                    len(state.grep.results) - 1,
                    state.grep.pane_index + 1,
                )
                if state.grep.pane_index == prev:
                    return False
                build_grep_pane_text(app)
            else:
                curses.beep()
                return False
        else:
            moved = app.selected_window[1].increment_selection(1)
            if not moved:
                return False

    # Switch active list window (left/right)
    elif key in LEFT_KEYS:
        app.increment_window(-1)

    elif key in RIGHT_KEYS:
        app.increment_window(1)

    # Resize event
    elif key == curses.KEY_RESIZE:
        curses.update_lines_cols()
        layout.layout_windows(app)
        app.update_text()

    # Jump to first/last in active list
    elif key == ord("g"):
        app.selected_window[1].select_first()

    elif key == ord("G"):
        app.selected_window[1].select_last()

    # Incremental search in active list window
    elif key == ord("i"):
        query = prompt_input_cancelable(app.stdscr, "Search: ")

        if query is None:
            pass  # aborted
        elif query:
            found = app.selected_window[1].search_select(query, start_at_current=True)
            if found:
                state.search.last_window = app.selected_window[1]
                state.search.query = query
            else:
                curses.beep()
        else:
            pass  # empty input ignored

    # Jump via reference like 'Prov 18:10' or 'John 3:16'
    elif key == ord(":"):
        ref = prompt_input_cancelable(app.stdscr, "Go to reference: ")

        if ref is not None and ref.strip():
            parsed = parse_reference(ref.strip())
            if parsed:
                book_name, chapter_num, verse_num = parsed
                if book_name and book_name in app.reader.get_books():
                    try:
                        app.books_win.select_value(book_name)
                    except Exception:
                        pass
                    app.update_selections()
                    try:
                        app.chapters_win.select_value(str(int(chapter_num)))
                    except Exception:
                        pass
                    app.update_selections()
                    if verse_num:
                        try:
                            app.verses_win.select_value(str(int(verse_num)))
                        except Exception:
                            pass
                else:
                    curses.beep()
            else:
                curses.beep()

    # Next / previous match: grep takes precedence, then list search
    elif key == ord("n"):
        if state.grep.results and state.grep.index >= 0:
            state.grep.index = (state.grep.index + 1) % len(state.grep.results)
            jump_to_grep_index(app, state.grep.index)
        else:
            last_query = state.search.query
            last_win = state.search.last_window
            if last_query and last_win is app.selected_window[1]:
                if not app.selected_window[1].search_next(last_query):
                    curses.beep()
            else:
                if last_query:
                    if not app.selected_window[1].search_select(last_query, True):
                        curses.beep()
                else:
                    curses.beep()

    elif key == ord("N"):
        if state.grep.results and state.grep.index >= 0:
            state.grep.index = (state.grep.index - 1) % len(state.grep.results)
            jump_to_grep_index(app, state.grep.index)
        else:
            last_query = state.search.query
            last_win = state.search.last_window
            if last_query and last_win is app.selected_window[1]:
                if not app.selected_window[1].search_prev(last_query):
                    curses.beep()
            else:
                if last_query:
                    if not app.selected_window[1].search_select(last_query, True):
                        curses.beep()
                else:
                    curses.beep()

    # Open grep results pane (selection with j/k, enter) for last-run pattern
    elif key == ord("r"):
        if state.grep.results:
            state.grep.pane_index = 0
            build_grep_pane_text(app)
        else:
            curses.beep()

    # ESC clears list search and grep view (but keeps grep history list)
    elif key == 27:  # ASCII ESC
        app.selected_window[1].clear_search_hint()
        if state.search.last_window is app.selected_window[1]:
            state.search.last_window = None
            state.search.query = ""
        state.grep.override_text = None
        state.grep.override_title = None
        state.grep.pattern = ""
        state.grep.results = []
        state.grep.index = -1
        state.grep.pane_index = 0
        state.grep.history_idx = -1

    # Prompt for grep pattern, run search, jump to first match without
    # opening results pane
    elif key == ord("/"):
        pattern = prompt_input_cancelable(app.stdscr, "Grep: ")

        if pattern is None:
            pass  # aborted
        elif pattern:
            curr_tr = app.translations_win.get_selection_tuple()[1]
            scope_translation = None
            scope_book = None
            scope_chapter = None
            if app.selected_window[1] is app.translations_win:
                scope_translation = curr_tr
            elif app.selected_window[1] is app.books_win:
                scope_translation = curr_tr
            elif app.selected_window[1] is app.chapters_win:
                scope_translation = curr_tr
                scope_book = app.books_win.get_selection_tuple()[1]
            elif app.selected_window[1] is app.verses_win:
                scope_translation = curr_tr
                scope_book = app.books_win.get_selection_tuple()[1]
                scope_chapter = app.chapters_win.get_selection_tuple()[1]
            scope = app._SearchScope(scope_translation, scope_book, scope_chapter)
            execute_search(app, pattern, scope)
            if state.grep.results and state.grep.index >= 0:
                jump_to_grep_index(app, state.grep.index)
            entry = {"pattern": pattern, "scope": scope}
            state.grep.history = [e for e in state.grep.history if e != entry]
            state.grep.history.append(entry)
            state.grep.history_idx = len(state.grep.history) - 1
        else:
            curses.beep()

    # Previous / next grep in history
    elif key == ord("K"):
        if state.grep.history:
            state.grep.history_idx = (
                max(0, state.grep.history_idx - 1)
                if state.grep.history_idx >= 0
                else len(state.grep.history) - 1
            )
            item = state.grep.history[state.grep.history_idx]
            execute_search(app, item["pattern"], item["scope"])

    # Toggle fullscreen verses view and focus verses column
    elif key == ord("f"):
        if app.selected_window[1] is not app.verses_win:
            app.deactivate_all_windows()
            for i, win in app.windows_tuples:
                if win is app.verses_win:
                    app.selected_window = (i, win)
                    state.ui.active_window_index = i
                    break
            app.selected_window[1].set_active(True)
        state.ui.sidebars_visible = not state.ui.sidebars_visible
        layout.layout_windows(app)

    # Enter: either activate grep result or open Frogmouth
    elif key in ENTER_KEYS:
        if state.grep.override_text is not None and state.grep.results:
            state.grep.index = state.grep.pane_index
            jump_to_grep_index(app, state.grep.index)
            state.grep.override_text = None
            state.grep.override_title = None
        else:
            open_in_frogmouth(app)

    # Any other key: no-op, but keep refresh behavior
    else:
        return True

    return True
