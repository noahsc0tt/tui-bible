#!/usr/bin/env python3

"""Curses entrypoint and orchestrator for the Bible TUI."""

import curses
from pathlib import Path

from .reader import Reader
from .state import State
from .actions import handle_key
from .listwin import ListWindow
from .textwin import TextWindow
from . import position
from . import layout
from . import selection
from . import views


class Main:
    def __init__(self, stdscr):
        self.stdscr = stdscr

        self.stdscr.clear()

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_WHITE, -1)
            self.stdscr.bkgd(" ", curses.color_pair(1))
        try:
            curses.set_escdelay(25)  # Reduce default ~1000ms ESC delay
        except Exception:
            pass
        try:
            curses.curs_set(0)  # hide cursor to prevent flicker during repeats
        except Exception:
            pass

        from .search_manager import SearchManager, Scope, Match

        # Core managers
        self._search_manager = SearchManager(Path(__file__).parent / "translations")
        self._SearchScope = Scope
        self._SearchMatch = Match

        # Structured state (search / grep / UI)
        self.state = State()

        saved = self.initialize_reader()
        self.state.ui.sidebars_visible = True

        # Initialize windows and assign to self
        (
            self.translations_win,
            self.books_win,
            self.chapters_win,
            self.verses_win,
            self.text_win,
            self.text_width,
        ) = layout.create_windows(self.stdscr, self.reader)

        self.initialize_selections()
        position.apply_position(self, saved)
        layout.layout_windows(self)

        selection.update_selections(self, self.reader)
        views.update_text(self, self.reader)

        self.start_input_loop()

    def initialize_reader(self):
        self.reader = Reader()
        translations = self.reader.get_translations()
        default = (
            "BSB"
            if "BSB" in translations
            else (translations[0] if translations else None)
        )
        if not default:
            raise RuntimeError("No supported translations found")
        self.reader.set_root(default)
        return position.load_last_position(self.reader)

    def initialize_selections(self):
        self.windows_tuples: list[tuple[int, ListWindow]] = list(
            enumerate(
                [
                    self.translations_win,
                    self.books_win,
                    self.chapters_win,
                    self.verses_win,
                ]
            )
        )
        # Start in verse mode
        for i, win in self.windows_tuples:
            if win is self.verses_win:
                self.selected_window = (i, win)
                self.state.ui.active_window_index = i
                break
        self.selected_window[1].set_active(True)

    def update_selections(self):
        selection.update_selections(self, self.reader)

    def update_text(self):
        views.update_text(self, self.reader)

    def deactivate_all_windows(self):
        for i, win in self.windows_tuples:
            win.set_active(False)

    def increment_window(self, i):
        self.deactivate_all_windows()
        new_windex = self.selected_window[0] + i
        if new_windex >= len(self.windows_tuples):
            new_windex = 0
        elif new_windex < 0:
            new_windex = len(self.windows_tuples) - 1
        self.selected_window = self.windows_tuples[new_windex]
        self.state.ui.active_window_index = new_windex
        self.selected_window[1].set_active(True)
        # Relayout so that in narrow mode the newly active column is shown
        layout.layout_windows(self)

    def start_input_loop(self):
        key = None
        while key != ord("q"):
            key = self.stdscr.getch()
            refresh = handle_key(self, key)
            if refresh:
                self.update_selections()
                self.update_text()
        position.save_position(self)


def main():
    curses.wrapper(Main)


if __name__ == "__main__":
    main()
