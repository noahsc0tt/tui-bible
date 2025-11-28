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

TRANSLATIONS_WIDTH = 8
BOOKS_WIDTH = 20
CHAPTERS_WIDTH = 6
VERSES_WIDTH = 6

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
        # Ensure text area keeps majority of horizontal space; sacrifice sidebars if too narrow
        total_sidebar_width = (
            TRANSLATIONS_WIDTH + BOOKS_WIDTH + CHAPTERS_WIDTH + VERSES_WIDTH
        )
        min_text_fraction = 0.6  # Require at least 60% of width for text
        available_cols = curses.COLS
        sidebars_fit = self.sidebars_visible and (
            (available_cols - total_sidebar_width) / max(1, available_cols)
            >= min_text_fraction
        )
        if sidebars_fit:
            # Recreate all sidebar windows to avoid stale narrow-mode hidden windows
            start_x = 0
            self.translations_win._win = self.stdscr.derwin(
                curses.LINES, TRANSLATIONS_WIDTH, 0, start_x
            )
            start_x += TRANSLATIONS_WIDTH
            self.books_win._win = self.stdscr.derwin(
                curses.LINES, BOOKS_WIDTH, 0, start_x
            )
            start_x += BOOKS_WIDTH
            self.chapters_win._win = self.stdscr.derwin(
                curses.LINES, CHAPTERS_WIDTH, 0, start_x
            )
            start_x += CHAPTERS_WIDTH
            self.verses_win._win = self.stdscr.derwin(
                curses.LINES, VERSES_WIDTH, 0, start_x
            )
            start_x += VERSES_WIDTH
            self.text_width = available_cols - start_x
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
            # Show only the currently active sidebar column at left; move others off-screen
            active_win = self.selected_window[1]
            if active_win is self.translations_win:
                single_width = TRANSLATIONS_WIDTH
            elif active_win is self.books_win:
                single_width = BOOKS_WIDTH
            elif active_win is self.chapters_win:
                single_width = CHAPTERS_WIDTH
            elif active_win is self.verses_win:
                single_width = VERSES_WIDTH
            else:
                single_width = 0
            # Recreate active window at x=0
            active_win._win = self.stdscr.derwin(curses.LINES, single_width, 0, 0)
            # Move other windows to 1x1 hidden windows so they no longer blank out text
            for win in [
                self.translations_win,
                self.books_win,
                self.chapters_win,
                self.verses_win,
            ]:
                if win is not active_win:
                    win._win = self.stdscr.derwin(
                        1, 1, curses.LINES - 1, max(0, available_cols - 1)
                    )
            # Create text window to the right of active column
            self.text_width = max(1, available_cols - single_width)
            self.text_win = TextWindow(
                self.stdscr.derwin(curses.LINES, self.text_width, 0, single_width),
                self.text_width,
            )
            active_win.set_active(True)
            active_win.draw()

    def initialize_selections(self):
        self.windows_tuples = make_enumeration(
            [self.translations_win, self.books_win, self.chapters_win, self.verses_win]
        )
        # Start in verse mode
        for i, win in self.windows_tuples:
            if win is self.verses_win:
                self.selected_window = (i, win)
                break
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

        # Build title; put grep indicator fully at left if active
        grep_indicator = ""
        if self._grep_results and self._grep_index >= 0:
            term = self._last_grep or "grep"
            if len(term) > 20:
                term = term[:20] + "…"
            grep_indicator = (
                f"({term} {self._grep_index + 1}/{len(self._grep_results)}) "
            )
        # Show full book name in the title
        book_display = book_name
        text_title = f" {grep_indicator}{book_display} {chapter_name[0]}:{verse_int} [{trans_name}]"

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
            base_hint = "[Enter]: open current chapter in Frogmouth"
            wrap_width = max(1, self.text_width - 3)
            hint_lines = wrap(base_hint, width=wrap_width)
            hint = "\n" + "\n".join(hint_lines)
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
        # Relayout so that in narrow mode the newly active column is shown
        self.layout_windows()

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
        self,
        pattern,
        scope_translation=None,
        scope_book=None,
        scope_chapter=None,
        all=False,
        record_history=False,
    ):
        # Perform grep across translation XML files (with optional scope), map verses
        results_lines = []
        structured = []
        base_dir = Path(__file__).parent / "translations"
        verse_pattern = re.compile(r"<verse[^>]*?(?:number|n)=[\"'](\d+)[\"']")
        chapter_pattern = re.compile(r"<chapter[^>]*?(?:number|n)=[\"'](\d+)[\"']")
        book_pattern = re.compile(r"<book[^>]*?(?:number|n)=[\"'](\d+)[\"']")
        scoped_book_num = None
        scoped_chapter_num = None
        if all:
            # Recursively scan the entire translations directory (raw grep-style)
            try:
                for root, dirs, files in os.walk(base_dir):
                    # Skip VCS/internal dirs
                    dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
                    for fname in files:
                        fpath = Path(root) / fname
                        try:
                            with open(
                                fpath, "r", encoding="utf-8", errors="ignore"
                            ) as rf:
                                for lno, line in enumerate(rf, 1):
                                    if re.search(pattern, line, re.IGNORECASE):
                                        rel = str(fpath.relative_to(base_dir))
                                        results_lines.append(
                                            f"{rel}:{lno}: {line.rstrip()}"
                                        )
                        except Exception:
                            # Ignore unreadable files
                            continue
            except Exception:
                pass
            # Do not attempt to build structured results for raw grep; navigation (n/N) disabled
            # The existing XML scan loop below is inert due to the all-guard, and the formatter
            # at the end of this function will render results_lines as-is.
        if scope_book:
            try:
                scoped_book_num = BOOK_ORDER.index(scope_book) + 1
            except Exception:
                scoped_book_num = None
        if scope_chapter:
            try:
                scoped_chapter_num = int(scope_chapter)
            except Exception:
                scoped_chapter_num = None
        if not all:
            for xmlfile in sorted(base_dir.glob("*.xml")):
                translation = xmlfile.stem
                if scope_translation and translation != scope_translation:
                    continue
                try:
                    with open(xmlfile, "r", encoding="utf-8", errors="ignore") as f:
                        current_book_num = None
                        current_chapter_num = None
                        current_verse_num = None
                        for lno, line in enumerate(f, 1):
                            mbook = book_pattern.search(line)
                            if mbook:
                                current_book_num = int(mbook.group(1))
                            mchap = chapter_pattern.search(line)
                            if mchap:
                                current_chapter_num = int(mchap.group(1))
                            mverse = verse_pattern.search(line)
                            if mverse:
                                current_verse_num = int(mverse.group(1))
                            # Apply scope filters strictly
                            if (
                                scoped_book_num is not None
                                and current_book_num != scoped_book_num
                            ):
                                continue
                            if (
                                scoped_chapter_num is not None
                                and current_chapter_num != scoped_chapter_num
                            ):
                                continue
                            if re.search(pattern, line, re.IGNORECASE):
                                verse_num = (
                                    current_verse_num if current_verse_num else 1
                                )
                                book_name = None
                                if (
                                    current_book_num is not None
                                    and 1 <= current_book_num <= len(BOOK_ORDER)
                                ):
                                    book_name = BOOK_ORDER[current_book_num - 1]
                                snippet = line.strip()
                                cleaned = re.sub(r"<[^>]+>", "", snippet)
                                results_lines.append(
                                    f"{translation} {book_name or ''} {current_chapter_num or ''}:{verse_num} — {cleaned}"
                                )
                                if book_name and current_chapter_num:
                                    structured.append(
                                        (
                                            translation,
                                            book_name,
                                            str(current_chapter_num),
                                            str(verse_num),
                                            cleaned,
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
        elif scoped_chapter_num is not None:
            scope_label = f"[Chapter {scoped_chapter_num}]"
        else:
            scope_label = "[ALL]"
        # Verse label removed (verse-scoped search disabled)
        if results_lines:
            # Use already-cleaned results_lines for display
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
                entry = {
                    "pattern": pattern,
                    "scope_translation": scope_translation,
                    "scope_book": scope_book,
                    "scope_chapter": scoped_chapter_num,
                    "all": all,
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
            elif key == curses.KEY_RESIZE:
                curses.update_lines_cols()
                self.layout_windows()
                self.update_text()

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

            elif key == ord("s"):
                # Jump via reference like 'Prov 18:10' or 'John 3:16'
                ref = self._prompt_input_cancelable("Go to reference: ")
                if ref is not None and ref.strip():
                    ref = ref.strip()
                    m = re.match(r"([1-3]?[A-Za-z]+)\s+(\d+)(?::(\d+))?", ref)
                    if m:
                        book_abbrev = m.group(1)
                        chapter_num = m.group(2)
                        verse_num = m.group(3)
                        # reverse lookup in ABBREV mapping
                        # Recreate same ABBREV dict locally (could refactor to class attr)
                        ABBREV = {
                            "Genesis": "Gen",
                            "Exodus": "Exo",
                            "Leviticus": "Lev",
                            "Numbers": "Num",
                            "Deuteronomy": "Deut",
                            "Joshua": "Josh",
                            "Judges": "Judg",
                            "Ruth": "Ruth",
                            "1 Samuel": "1Sam",
                            "2 Samuel": "2Sam",
                            "1 Kings": "1Kgs",
                            "2 Kings": "2Kgs",
                            "1 Chronicles": "1Chr",
                            "2 Chronicles": "2Chr",
                            "Ezra": "Ezra",
                            "Nehemiah": "Neh",
                            "Esther": "Esth",
                            "Job": "Job",
                            "Psalms": "Ps",
                            "Proverbs": "Prov",
                            "Ecclesiastes": "Eccl",
                            "Song of Solomon": "Song",
                            "Isaiah": "Isa",
                            "Jeremiah": "Jer",
                            "Lamentations": "Lam",
                            "Ezekiel": "Ezek",
                            "Daniel": "Dan",
                            "Hosea": "Hos",
                            "Joel": "Joel",
                            "Amos": "Amos",
                            "Obadiah": "Obad",
                            "Jonah": "Jonah",
                            "Micah": "Mic",
                            "Nahum": "Nah",
                            "Habakkuk": "Hab",
                            "Zephaniah": "Zeph",
                            "Haggai": "Hag",
                            "Zechariah": "Zech",
                            "Malachi": "Mal",
                            "Matthew": "Matt",
                            "Mark": "Mark",
                            "Luke": "Luke",
                            "John": "John",
                            "Acts": "Acts",
                            "Romans": "Rom",
                            "1 Corinthians": "1Cor",
                            "2 Corinthians": "2Cor",
                            "Galatians": "Gal",
                            "Ephesians": "Eph",
                            "Philippians": "Phil",
                            "Colossians": "Col",
                            "1 Thessalonians": "1Th",
                            "2 Thessalonians": "2Th",
                            "1 Timothy": "1Tim",
                            "2 Timothy": "2Tim",
                            "Titus": "Titus",
                            "Philemon": "Phlm",
                            "Hebrews": "Heb",
                            "James": "Jas",
                            "1 Peter": "1Pet",
                            "2 Peter": "2Pet",
                            "1 John": "1Jn",
                            "2 John": "2Jn",
                            "3 John": "3Jn",
                            "Jude": "Jude",
                            "Revelation": "Rev",
                        }
                        # Build reverse mapping including numeric prefixes stripped variants
                        rev = {}
                        for full, ab in ABBREV.items():
                            rev[ab.lower()] = full
                        target_full = rev.get(book_abbrev.lower())
                        if target_full and target_full in self.reader.get_books():
                            try:
                                self.books_win.select_value(target_full)
                            except Exception:
                                pass
                            self.update_selections()
                            try:
                                self.chapters_win.select_value(str(int(chapter_num)))
                            except Exception:
                                pass
                            self.update_selections()
                            if verse_num:
                                try:
                                    self.verses_win.select_value(str(int(verse_num)))
                                except Exception:
                                    pass
                        else:
                            curses.beep()
                    else:
                        curses.beep()

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
                # Open grep results pane for last-run pattern
                pattern = self._last_grep
                if not pattern and self._grep_history:
                    hist = self._grep_history[-1]
                    pattern = hist.get("pattern")
                if self._grep_results:
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
                    title_term = pattern or "grep"
                    self._grep_override_title = (
                        f" GREP /{title_term}/ ({len(formatted_lines)})"
                    )
                else:
                    curses.beep()

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
                # Prompt for grep pattern, run search, jump to first match without opening results pane
                pattern = self._prompt_input_cancelable("Grep: ")
                if pattern is None:
                    pass  # aborted
                elif pattern:
                    scope_translation = None
                    scope_book = None
                    scope_chapter = None
                    all = False
                    if self.selected_window[1] is self.translations_win:
                        all = True
                    elif self.selected_window[1] is self.books_win:
                        scope_translation = self.translations_win.get_selection_tuple()[
                            1
                        ]
                    elif self.selected_window[1] is self.chapters_win:
                        scope_book = self.books_win.get_selection_tuple()[1]
                    elif self.selected_window[1] is self.verses_win:
                        scope_book = self.books_win.get_selection_tuple()[1]
                        scope_chapter = self.chapters_win.get_selection_tuple()[1]
                    # Run grep (records history); _run_grep populates override pane; clear it right after
                    self._run_grep(
                        pattern,
                        scope_translation,
                        scope_book,
                        scope_chapter,
                        all,
                        record_history=True,
                    )
                    # Clear override pane so verses view remains
                    self._grep_override_text = None
                    self._grep_override_title = None
                    # Ensure at first result
                    if self._grep_results and self._grep_index >= 0:
                        self._jump_to_grep_index(self._grep_index)
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
                        item.get("scope_chapter"),
                        item.get("all", False),
                        record_history=False,
                    )
                    # If structured verse results exist, reformat; otherwise keep raw lines from _run_grep
                    if self._grep_results:
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
                        text = (
                            "\n".join(wrapped)
                            if wrapped
                            else "\n".join(formatted_lines)
                        )
                        self._grep_override_text = text
                        self._grep_override_title = (
                            f" GREP /{item['pattern']}/ ({len(formatted_lines)})"
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
                        item.get("scope_chapter"),
                        item.get("all", False),
                        record_history=False,
                    )
                    # If structured verse results exist, reformat; otherwise keep raw lines from _run_grep
                    if self._grep_results:
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
                        text = (
                            "\n".join(wrapped)
                            if wrapped
                            else "\n".join(formatted_lines)
                        )
                        self._grep_override_text = text
                        self._grep_override_title = (
                            f" GREP /{item['pattern']}/ ({len(formatted_lines)})"
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
