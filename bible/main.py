#!/usr/bin/env python3

import curses

from hyphen import Hyphenator
from textwrap import wrap
import re
import json
import os
from pathlib import Path

from .reader import Reader
from .textwin import TextWindow
from .listwin import ListWindow

TRANSLATIONS_WIDTH = 6
BOOKS_WIDTH = 14
CHAPTERS_WIDTH = 4
VERSES_WIDTH = 4

h_en = Hyphenator("en_US")


def make_enumeration(list_):
    return list(enumerate(list_))


class Main:
    def __init__(self, stdscr):
        self.stdscr = stdscr

        self.stdscr.clear()

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_WHITE, -1)
            self.stdscr.bkgd(" ", curses.color_pair(1))

        self._last_search = {"win": None, "query": ""}

        self.initialize_reader()
        self.sidebars_visible = True
        self.initialize_windows()
        self.initialize_selections()
        self._apply_loaded_position()
        self.layout_windows()

        self.update_selections()
        self.update_text()

        self.start_input_loop()

    def _state_file(self):
        return os.path.join(os.path.expanduser("~"), ".bible_last.json")

    def _load_last_position(self):
        self._loaded_state = None
        try:
            with open(self._state_file(), "r") as f:
                st = json.load(f)
        except Exception:
            return
        translations = self.reader.get_translations()
        trans = st.get("translation")
        if trans in translations:
            self.reader.set_root(trans)
            self._loaded_state = {
                "translation": trans,
                "book": st.get("book"),
                "chapter": str(st.get("chapter"))
                if st.get("chapter") is not None
                else None,
                "verse": str(st.get("verse")) if st.get("verse") is not None else None,
            }

    def _apply_loaded_position(self):
        st = getattr(self, "_loaded_state", None)
        if not st:
            return
        try:
            self.translations_win.select_value(st["translation"])
            self.update_selections()
            if st.get("book"):
                self.books_win.select_value(st["book"])
                self.update_selections()
            if st.get("chapter"):
                self.chapters_win.select_value(st["chapter"])
                self.update_selections()
            if st.get("verse"):
                self.verses_win.select_value(st["verse"])
        except Exception:
            pass

    def _save_position(self):
        try:
            data = {
                "translation": self.translations_win.get_selection_tuple()[1],
                "book": self.books_win.get_selection_tuple()[1],
                "chapter": self.chapters_win.get_selection_tuple()[1],
                "verse": self.verses_win.get_selection_tuple()[1],
            }
            with open(self._state_file(), "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _prompt_input(self, prompt_text):
        h, w = self.stdscr.getmaxyx()
        try:
            curses.echo()
            self.stdscr.move(h - 1, 0)
            self.stdscr.clrtoeol()
            self.stdscr.addnstr(h - 1, 0, prompt_text, max(0, w - 1))
            self.stdscr.refresh()
            s = self.stdscr.getstr(
                h - 1, len(prompt_text), max(1, w - len(prompt_text) - 1)
            )
            return s.decode("utf-8").strip()
        except Exception:
            return ""
        finally:
            curses.noecho()
            self.stdscr.move(h - 1, 0)
            self.stdscr.clrtoeol()
            self.stdscr.refresh()

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
        self._load_last_position()

    def initialize_windows(self):
        start_x = 0
        self.translations_win = ListWindow(
            self.stdscr.derwin(curses.LINES, TRANSLATIONS_WIDTH, start_x, 0),
            "TR",
            make_enumeration(self.reader.get_translations()),
            TRANSLATIONS_WIDTH,
        )

        start_x += TRANSLATIONS_WIDTH
        self.books_win = ListWindow(
            self.stdscr.derwin(curses.LINES, BOOKS_WIDTH, 0, start_x),
            "BOOK",
            make_enumeration(self.reader.get_books()),
            BOOKS_WIDTH,
        )

        start_x += BOOKS_WIDTH
        self.chapters_win = ListWindow(
            self.stdscr.derwin(curses.LINES, CHAPTERS_WIDTH, 0, start_x),
            "CH",
            make_enumeration(self.reader.get_chapters("Genesis")),
            CHAPTERS_WIDTH,
        )

        start_x += CHAPTERS_WIDTH
        self.verses_win = ListWindow(
            self.stdscr.derwin(curses.LINES, VERSES_WIDTH, 0, start_x),
            "VS",
            make_enumeration(self.reader.get_verses("Genesis", 1)),
            VERSES_WIDTH,
        )

        self.text_width = curses.COLS
        self.text_win = TextWindow(
            self.stdscr.derwin(curses.LINES, self.text_width, 0, 0),
            self.text_width,
        )

    def layout_windows(self):
        if self.sidebars_visible:
            start_x = TRANSLATIONS_WIDTH + BOOKS_WIDTH + CHAPTERS_WIDTH + VERSES_WIDTH
            self.text_width = curses.COLS - start_x
            self.text_win = TextWindow(
                self.stdscr.derwin(curses.LINES, self.text_width, 0, start_x),
                self.text_width,
            )
            self.deactivate_all_windows()
            self.selected_window[1].set_active(True)
            for win in [
                self.translations_win,
                self.books_win,
                self.chapters_win,
                self.verses_win,
            ]:
                win.draw()
        else:
            self.text_width = curses.COLS
            self.text_win = TextWindow(
                self.stdscr.derwin(curses.LINES, self.text_width, 0, 0),
                self.text_width,
            )
            self.deactivate_all_windows()
            for win in [
                self.translations_win,
                self.books_win,
                self.chapters_win,
                self.verses_win,
            ]:
                w = win._win
                w.clear()
                w.refresh()

    def initialize_selections(self):
        self.windows_tuples = make_enumeration(
            [self.translations_win, self.books_win, self.chapters_win, self.verses_win]
        )
        self.selected_window = self.windows_tuples[1]
        self.selected_window[1].set_active(True)

    def update_selections(self):
        trans = self.translations_win.get_selection_tuple()[1]
        self.reader.set_root(trans)

        book = self.books_win.get_selection_tuple()[1]

        chapter_tuples = make_enumeration(self.reader.get_chapters(book))
        self.chapters_win.set_selection_tuples(chapter_tuples)

        chapter = self.chapters_win.get_selection_tuple()[1]

        verses_tuples = make_enumeration(self.reader.get_verses(book, chapter))
        self.verses_win.set_selection_tuples(verses_tuples)

    def update_text(self):
        trans_name = self.translations_win.get_selection_tuple()[1]
        book_name = self.books_win.get_selection_tuple()[1]
        chapter_name = (self.chapters_win.get_selection_tuple()[1],)
        verse_str = self.verses_win.get_selection_tuple()[1]
        try:
            verse_int = int(verse_str) if verse_str else 1
        except Exception:
            verse_int = 1

        text_title = " {0} {1}:{3} [{2}]".format(
            book_name, str(chapter_name[0]), trans_name, verse_int
        )

        raw_text = self.reader.get_chapter_text(
            self.books_win.get_selection_tuple()[1],
            self.chapters_win.get_selection_tuple()[1],
            verse_start=verse_int,
        )
        verses = re.split(r"(?=\(\d+\)\s*)", raw_text)
        lines = []
        for v in verses:
            if not v.strip():
                continue
            wrapped = wrap(v, width=self.text_width - 3)
            lines.extend(wrapped)
            lines.append("")
        text = "\n".join(lines[0 : curses.LINES - 2])

        hint = ""
        if trans_name == "BSB":
            hint = "\n[Enter]: open current chapter in Frogmouth"
        self.text_win.update_text_title(text_title)
        self.text_win.update_text(text + hint)

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
        self.selected_window[1].set_active(True)

    def _open_in_frogmouth(self):
        trans = self.translations_win.get_selection_tuple()[1]
        if trans != "BSB":
            return
        book = self.books_win.get_selection_tuple()[1]
        chapter = self.chapters_win.get_selection_tuple()[1]
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
            self.stdscr.refresh()
            self.layout_windows()
            self.update_selections()
            self.update_text()

    def start_input_loop(self):
        key = None
        while key != ord("q"):
            key = self.stdscr.getch()

            if key == curses.KEY_UP or key == ord("k"):
                self.selected_window[1].increment_selection(-1)

            elif key == curses.KEY_DOWN or key == ord("j"):
                self.selected_window[1].increment_selection(1)

            elif key == curses.KEY_LEFT or key == ord("h"):
                self.increment_window(-1)

            elif key == curses.KEY_RIGHT or key == ord("l"):
                self.increment_window(1)

            elif key == ord("g"):
                self.selected_window[1].select_first()

            elif key == ord("G"):
                self.selected_window[1].select_last()

            elif key == ord("i"):
                query = self._prompt_input("Search: ")
                if query:
                    found = self.selected_window[1].search_select(
                        query, start_at_current=True
                    )
                    if found:
                        self._last_search = {
                            "win": self.selected_window[1],
                            "query": query,
                        }
                    else:
                        curses.beep()

            elif key == ord("n"):
                last = self._last_search
                if last["query"] and last["win"] is self.selected_window[1]:
                    if not self.selected_window[1].search_next(last["query"]):
                        curses.beep()
                else:
                    # Repeat last search starting from current
                    if last["query"]:
                        if not self.selected_window[1].search_select(
                            last["query"], True
                        ):
                            curses.beep()
                    else:
                        curses.beep()

            elif key == ord("N"):
                last = self._last_search
                if last["query"] and last["win"] is self.selected_window[1]:
                    if not self.selected_window[1].search_prev(last["query"]):
                        curses.beep()
                else:
                    if last["query"]:
                        if not self.selected_window[1].search_select(
                            last["query"], True
                        ):
                            curses.beep()
                    else:
                        curses.beep()

            elif key == ord("f"):
                if self.selected_window[1] is not self.verses_win:
                    self.deactivate_all_windows()
                    for i, win in self.windows_tuples:
                        if win is self.verses_win:
                            self.selected_window = (i, win)
                            break
                    self.selected_window[1].set_active(True)
                self.sidebars_visible = not self.sidebars_visible
                self.layout_windows()

            elif key in (10, 13):
                self._open_in_frogmouth()

            self.update_selections()
            self.update_text()
        self._save_position()


def main():
    curses.wrapper(Main)


if __name__ == "__main__":
    main()
