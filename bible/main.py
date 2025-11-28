#!/usr/bin/env python3

import curses

from hyphen import Hyphenator
from textwrap import wrap
import re
import json
import os
from pathlib import Path

from .reader import Reader, BOOK_ORDER
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
        try:
            curses.set_escdelay(25)  # Reduce default ~1000ms ESC delay
        except Exception:
            pass

        self._last_search = {"win": None, "query": ""}
        self._last_grep = ""
        self._grep_history = []  # list of dicts: {pattern, scope_translation, scope_book}
        self._grep_history_idx = -1
        self._grep_override_text = None
        self._grep_override_title = None
        self._grep_results = []  # list of (translation, book, chapter, verse, snippet)
        self._grep_raw_lines = []  # raw grep lines with filenames
        self._grep_index = -1

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

    def _prompt_input_cancelable(self, prompt_text):
        h, w = self.stdscr.getmaxyx()
        buf = []
        curses.noecho()
        while True:
            self.stdscr.move(h - 1, 0)
            self.stdscr.clrtoeol()
            display = prompt_text + "".join(buf)
            self.stdscr.addnstr(h - 1, 0, display, max(0, w - 1))
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (10, 13):  # Enter
                break
            if ch == 27:  # ESC cancel
                buf = None
                break
            if ch in (curses.KEY_BACKSPACE, 127):
                if buf:
                    buf.pop()
                continue
            if 32 <= ch <= 126:  # printable ASCII
                if len(buf) < w - len(prompt_text) - 1:
                    buf.append(chr(ch))
        # Clear prompt line
        self.stdscr.move(h - 1, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        if buf is None:
            return None
        s = "".join(buf).strip()
        return s if s else ""

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
        if self._grep_override_text is not None:
            # Grep view active
            self.text_win.update_text_title(
                self._grep_override_title or " GREP RESULTS"
            )
            self.text_win.update_text(
                self._grep_override_text,
                highlight_terms=[self._last_grep] if self._last_grep else None,
            )
            return

        trans_name = self.translations_win.get_selection_tuple()[1]
        book_name = self.books_win.get_selection_tuple()[1]
        chapter_name = (self.chapters_win.get_selection_tuple()[1],)
        verse_str = self.verses_win.get_selection_tuple()[1]
        try:
            verse_int = int(verse_str) if verse_str else 1
        except Exception:
            verse_int = 1

        # Build title with grep indicator left of verse number
        grep_indicator = ""
        if self._grep_results and self._grep_index >= 0:
            term = self._last_grep or "grep"
            if len(term) > 20:
                term = term[:20] + "…"
            grep_indicator = (
                f" ({term} {self._grep_index + 1}/{len(self._grep_results)})"
            )
        text_title = " {0} {1}{gi}:{3} [{2}]".format(
            book_name, str(chapter_name[0]), trans_name, verse_int, gi=grep_indicator
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
        highlight_terms = []
        if self._grep_results and self._grep_index >= 0 and self._last_grep:
            highlight_terms.append(self._last_grep)
        # Also highlight active list search term in verses if applicable (book/chapter lists not matched here but harmless)
        if self._last_search.get("query"):
            highlight_terms.append(self._last_search.get("query"))
        self.text_win.update_text(text + hint, highlight_terms=highlight_terms or None)

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

    def _jump_to_grep_index(self, idx):
        if idx < 0 or idx >= len(self._grep_results):
            return
        (translation, book, chapter, verse, snippet) = self._grep_results[idx]
        try:
            self.translations_win.select_value(translation)
        except Exception:
            pass
        self.update_selections()
        try:
            self.books_win.select_value(book)
        except Exception:
            pass
        self.update_selections()
        try:
            self.chapters_win.select_value(chapter)
        except Exception:
            pass
        self.update_selections()
        try:
            self.verses_win.select_value(verse)
        except Exception:
            pass
        self._grep_override_text = None
        self._grep_override_title = None

    def _run_grep(
        self, pattern, scope_translation=None, scope_book=None, record_history=False
    ):
        # Perform grep across translation XML files (with optional scope), map verses
        results_lines = []
        structured = []
        base_dir = Path(__file__).parent / "translations"
        verse_pattern = re.compile(r"<verse[^>]*?(?:number|n)=[\"'](\d+)[\"']")
        chapter_pattern = re.compile(r"<chapter[^>]*?(?:number|n)=[\"'](\d+)[\"']")
        book_pattern = re.compile(r"<book[^>]*?(?:number|n)=[\"'](\d+)[\"']")
        scoped_book_num = None
        if scope_book:
            try:
                scoped_book_num = BOOK_ORDER.index(scope_book) + 1
            except Exception:
                scoped_book_num = None
        for xmlfile in sorted(base_dir.glob("*.xml")):
            translation = xmlfile.stem
            if scope_translation and translation != scope_translation:
                continue
            try:
                with open(xmlfile, "r", encoding="utf-8", errors="ignore") as f:
                    current_book_num = None
                    current_chapter_num = None
                    for lno, line in enumerate(f, 1):
                        mbook = book_pattern.search(line)
                        if mbook:
                            current_book_num = int(mbook.group(1))
                        mchap = chapter_pattern.search(line)
                        if mchap:
                            current_chapter_num = int(mchap.group(1))
                        if scoped_book_num and current_book_num != scoped_book_num:
                            continue
                        if re.search(pattern, line, re.IGNORECASE):
                            mverse = verse_pattern.search(line)
                            verse_num = int(mverse.group(1)) if mverse else 1
                            book_name = None
                            if (
                                current_book_num is not None
                                and 1 <= current_book_num <= len(BOOK_ORDER)
                            ):
                                book_name = BOOK_ORDER[current_book_num - 1]
                            snippet = line.strip()
                            if len(snippet) > 200:
                                snippet = snippet[:200] + "…"
                            scope_tag = ""
                            if scope_translation:
                                scope_tag = "(t)"
                            elif scope_book:
                                scope_tag = "(b)"
                            results_lines.append(
                                f"{xmlfile.name}:{lno} {scope_tag} {snippet}".strip()
                            )
                            if book_name and current_chapter_num:
                                structured.append(
                                    (
                                        translation,
                                        book_name,
                                        str(current_chapter_num),
                                        str(verse_num),
                                        snippet,
                                    )
                                )
            except Exception:
                continue
        self._grep_results = structured
        self._grep_index = 0 if structured else -1
        self._grep_raw_lines = results_lines
        scope_label = ""
        if scope_translation:
            scope_label = f"[{scope_translation}]"
        elif scope_book:
            scope_label = f"[{scope_book}]"
        if results_lines:
            # Build a formatted occurrences list from structured results
            formatted_lines = []
            for translation, book, chapter, verse, snippet in structured:
                cleaned = re.sub(r"<[^>]+>", "", snippet)
                line = f"{translation} {book} {chapter}:{verse} — {cleaned}"
                formatted_lines.append(line)
            if not formatted_lines:
                formatted_lines = results_lines
            # Wrap lines to text window width
            wrap_width = max(1, self.text_width - 3)
            wrapped = []
            for line in formatted_lines:
                for wl in wrap(line, width=wrap_width):
                    wrapped.append(wl)
                wrapped.append("")
            text = "\n".join(wrapped) if wrapped else "\n".join(formatted_lines)
            self._grep_override_text = text

            self._grep_override_title = (
                f" GREP {scope_label}/{pattern}/ ({len(formatted_lines)})"
            )
            self._last_grep = pattern
            if record_history:
                # Append unique or move to end
                entry = {
                    "pattern": pattern,
                    "scope_translation": scope_translation,
                    "scope_book": scope_book,
                }
                self._grep_history = [e for e in self._grep_history if e != entry]
                self._grep_history.append(entry)
                self._grep_history_idx = len(self._grep_history) - 1
            if self._grep_index >= 0:
                self._jump_to_grep_index(self._grep_index)
        else:
            curses.beep()
            self._grep_override_text = "No matches"
            self._grep_override_title = f" GREP {scope_label}/{pattern}/ (0)"
            self._last_grep = pattern
            self._grep_results = []
            self._grep_index = -1

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
                query = self._prompt_input_cancelable("Search: ")
                if query is None:
                    pass  # aborted
                elif query:
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
                else:
                    pass  # empty input ignored

            elif key == ord("n"):
                if self._grep_results and self._grep_index >= 0:
                    # Advance grep result navigation
                    self._grep_index = (self._grep_index + 1) % len(self._grep_results)
                    self._jump_to_grep_index(self._grep_index)
                else:
                    last = self._last_search
                    if last["query"] and last["win"] is self.selected_window[1]:
                        if not self.selected_window[1].search_next(last["query"]):
                            curses.beep()
                    else:
                        if last["query"]:
                            if not self.selected_window[1].search_select(
                                last["query"], True
                            ):
                                curses.beep()
                        else:
                            curses.beep()

            elif key == ord("N"):
                if self._grep_results and self._grep_index >= 0:
                    # Reverse grep navigation
                    self._grep_index = (self._grep_index - 1) % len(self._grep_results)
                    self._jump_to_grep_index(self._grep_index)
                else:
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

            elif key == ord("r"):
                # Rerun last grep scoped by current column, then show formatted results menu
                scope_translation = None
                scope_book = None
                if self.selected_window[1] is self.translations_win:
                    scope_translation = self.translations_win.get_selection_tuple()[1]
                elif self.selected_window[1] is self.books_win:
                    scope_book = self.books_win.get_selection_tuple()[1]
                pattern = self._last_grep
                if not pattern and self._grep_history:
                    hist = self._grep_history[-1]
                    pattern = hist.get("pattern")
                    scope_translation = hist.get("scope_translation", scope_translation)
                    scope_book = hist.get("scope_book", scope_book)
                if pattern:
                    self._run_grep(
                        pattern, scope_translation, scope_book, record_history=False
                    )
                    formatted_lines = []
                    for (
                        translation,
                        book,
                        chapter,
                        verse,
                        snippet,
                    ) in self._grep_results:
                        cleaned = re.sub(r"<[^>]+>", "", snippet)
                        formatted_lines.append(
                            f"{translation} {book} {chapter}:{verse} — {cleaned}"
                        )
                    wrap_width = max(1, self.text_width - 3)
                    wrapped = []
                    for line in formatted_lines:
                        for wl in wrap(line, width=wrap_width):
                            wrapped.append(wl)
                        wrapped.append("")
                    text = "\n".join(wrapped) if wrapped else "\n".join(formatted_lines)
                    self._grep_override_text = text
                    title_term = pattern
                    self._grep_override_title = (
                        f" GREP /{title_term}/ ({len(formatted_lines)})"
                    )
                else:
                    curses.beep()
                    self._grep_override_text = "No matches"
                    self._grep_override_title = " GREP RESULTS (0)"

            elif key == 27:  # ESC clears search or grep view
                # Clear list search state
                self.selected_window[1].clear_search_hint()
                if self._last_search["win"] is self.selected_window[1]:
                    self._last_search = {"win": None, "query": ""}
                # Clear grep override if active
                self._grep_override_text = None
                self._grep_override_title = None
                self._last_grep = ""
                self._grep_results = []
                self._grep_index = -1
                # Keep history but reset active pointer
                self._grep_history_idx = -1

            elif key == ord("/"):
                pattern = self._prompt_input_cancelable("Grep: ")
                if pattern is None:
                    pass  # aborted
                elif pattern:
                    scope_translation = None
                    scope_book = None
                    # Auto-scope by active column
                    if self.selected_window[1] is self.translations_win:
                        scope_translation = self.translations_win.get_selection_tuple()[
                            1
                        ]
                    elif self.selected_window[1] is self.books_win:
                        scope_book = self.books_win.get_selection_tuple()[1]
                    # Chapters/Verses columns: leave unscoped for now
                    self._run_grep(
                        pattern, scope_translation, scope_book, record_history=True
                    )
                else:
                    curses.beep()  # empty pattern

            elif key == ord("K"):
                # Previous grep in history
                if self._grep_history:
                    self._grep_history_idx = (
                        max(0, self._grep_history_idx - 1)
                        if self._grep_history_idx >= 0
                        else len(self._grep_history) - 1
                    )
                    item = self._grep_history[self._grep_history_idx]
                    self._run_grep(
                        item["pattern"],
                        item.get("scope_translation"),
                        item.get("scope_book"),
                        record_history=False,
                    )
            elif key == ord("J"):
                # Next grep in history
                if self._grep_history:
                    self._grep_history_idx = (
                        (self._grep_history_idx + 1) % len(self._grep_history)
                        if self._grep_history_idx >= 0
                        else 0
                    )
                    item = self._grep_history[self._grep_history_idx]
                    self._run_grep(
                        item["pattern"],
                        item.get("scope_translation"),
                        item.get("scope_book"),
                        record_history=False,
                    )

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
