"""Window layout for the Bible TUI.

Responsible for creating and arranging the list and text windows
based on terminal size and UI state.
"""

import curses

from .textwin import TextWindow
from .listwin import ListWindow

TRANSLATIONS_WIDTH = 8
BOOKS_WIDTH = 20
CHAPTERS_WIDTH = 6
VERSES_WIDTH = 6


def initialize_windows(app, reader):
    start_x = 0
    app.translations_win = ListWindow(
        app.stdscr.derwin(curses.LINES, TRANSLATIONS_WIDTH, start_x, 0),
        "TR",
        list(enumerate(reader.get_translations())),
        TRANSLATIONS_WIDTH,
    )

    start_x += TRANSLATIONS_WIDTH
    app.books_win = ListWindow(
        app.stdscr.derwin(curses.LINES, BOOKS_WIDTH, 0, start_x),
        "BOOK",
        list(enumerate(reader.get_books())),
        BOOKS_WIDTH,
    )

    start_x += BOOKS_WIDTH
    app.chapters_win = ListWindow(
        app.stdscr.derwin(curses.LINES, CHAPTERS_WIDTH, 0, start_x),
        "CH",
        list(enumerate(reader.get_chapters("Genesis"))),
        CHAPTERS_WIDTH,
    )

    start_x += CHAPTERS_WIDTH
    app.verses_win = ListWindow(
        app.stdscr.derwin(curses.LINES, VERSES_WIDTH, 0, start_x),
        "VS",
        list(enumerate(reader.get_verses("Genesis", 1))),
        VERSES_WIDTH,
    )

    app.text_width = curses.COLS
    app.text_win = TextWindow(
        app.stdscr.derwin(curses.LINES, app.text_width, 0, 0),
        app.text_width,
    )


def layout_windows(app):
    available_cols = curses.COLS
    state = app.state
    if not state.ui.sidebars_visible:
        _layout_fullscreen(app, available_cols)
        return

    total_sidebar_width = (
        TRANSLATIONS_WIDTH + BOOKS_WIDTH + CHAPTERS_WIDTH + VERSES_WIDTH
    )
    min_text_fraction = 0.6
    sidebars_fit = (available_cols - total_sidebar_width) / max(
        1, available_cols
    ) >= min_text_fraction
    if sidebars_fit:
        _layout_all_sidebars(app, available_cols)
    else:
        _layout_single_sidebar(app, available_cols)


def _layout_fullscreen(app, available_cols: int):
    app.text_width = available_cols
    app.text_win = TextWindow(
        app.stdscr.derwin(curses.LINES, app.text_width, 0, 0),
        app.text_width,
    )
    for win in [
        app.translations_win,
        app.books_win,
        app.chapters_win,
        app.verses_win,
    ]:
        win._win = app.stdscr.derwin(1, 1, curses.LINES - 1, max(0, available_cols - 1))


def _layout_all_sidebars(app, available_cols: int):
    start_x = 0
    app.translations_win._win = app.stdscr.derwin(
        curses.LINES, TRANSLATIONS_WIDTH, 0, start_x
    )
    start_x += TRANSLATIONS_WIDTH
    app.books_win._win = app.stdscr.derwin(curses.LINES, BOOKS_WIDTH, 0, start_x)
    start_x += BOOKS_WIDTH
    app.chapters_win._win = app.stdscr.derwin(curses.LINES, CHAPTERS_WIDTH, 0, start_x)
    start_x += CHAPTERS_WIDTH
    app.verses_win._win = app.stdscr.derwin(curses.LINES, VERSES_WIDTH, 0, start_x)
    start_x += VERSES_WIDTH
    app.text_width = available_cols - start_x
    app.text_win = TextWindow(
        app.stdscr.derwin(curses.LINES, app.text_width, 0, start_x),
        app.text_width,
    )
    app.deactivate_all_windows()
    app.selected_window[1].set_active(True)
    for win in [
        app.translations_win,
        app.books_win,
        app.chapters_win,
        app.verses_win,
    ]:
        win.draw()


def _layout_single_sidebar(app, available_cols: int):
    active_win = app.selected_window[1]
    if active_win is app.translations_win:
        single_width = TRANSLATIONS_WIDTH
    elif active_win is app.books_win:
        single_width = BOOKS_WIDTH
    elif active_win is app.chapters_win:
        single_width = CHAPTERS_WIDTH
    elif active_win is app.verses_win:
        single_width = VERSES_WIDTH
    else:
        single_width = 0

    active_win._win = app.stdscr.derwin(curses.LINES, single_width, 0, 0)
    for win in [
        app.translations_win,
        app.books_win,
        app.chapters_win,
        app.verses_win,
    ]:
        if win is not active_win:
            win._win = app.stdscr.derwin(
                1, 1, curses.LINES - 1, max(0, available_cols - 1)
            )

    app.text_width = max(1, available_cols - single_width)
    app.text_win = TextWindow(
        app.stdscr.derwin(curses.LINES, app.text_width, 0, single_width),
        app.text_width,
    )
    active_win.set_active(True)
    active_win.draw()
