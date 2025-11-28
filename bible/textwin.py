import curses
import re


class TextWindow:
    def __init__(self, win, width):
        self._outer_win = win
        self._outer_win.box()
        if curses.has_colors():
            self._outer_win.bkgd(" ", curses.color_pair(1))

        self._width = width

        self._inner_win = self._outer_win.derwin(
            curses.LINES - 2, self._width - 2, 1, 1
        )
        if curses.has_colors():
            self._inner_win.bkgd(" ", curses.color_pair(1))

    def update_text_title(self, title):
        self._outer_win.clear()
        if curses.has_colors():
            self._outer_win.bkgd(" ", curses.color_pair(1))
        self._outer_win.box()

        title_centered = title.center(self._width, " ")
        start_pad = len(title_centered) - len(title_centered.lstrip(" "))
        # Clip title to window width to avoid curses errors
        _, w = self._outer_win.getmaxyx()
        self._outer_win.addnstr(0, max(1, start_pad), title, max(0, w - 2))
        self._outer_win.refresh()

    def update_text(self, text, highlight_terms=None):
        self._inner_win.clear()
        use_colors = curses.has_colors()
        if use_colors:
            self._inner_win.bkgd(" ", curses.color_pair(1))
            try:
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
            except Exception:
                pass
        h, w = self._inner_win.getmaxyx()
        lines = text.splitlines()
        max_lines = min(h, len(lines))
        terms = []
        if highlight_terms:
            for t in highlight_terms:
                if t:
                    terms.append(t)
        # Build a combined regex for all terms
        combined = None
        if terms:
            try:
                combined = re.compile(
                    "|".join(re.escape(t) for t in terms), re.IGNORECASE
                )
            except Exception:
                combined = None
        for y in range(max_lines):
            line = lines[y]
            if not combined:
                self._inner_win.addnstr(y, 0, line, max(0, w - 1))
                continue
            x = 0
            last_end = 0
            for m in combined.finditer(line):
                if x >= w - 1:
                    break
                # segment before match
                seg = line[last_end : m.start()]
                if seg:
                    avail = max(0, w - 1 - x)
                    if avail > 0:
                        self._inner_win.addnstr(y, x, seg[:avail], avail)
                        x += min(len(seg), avail)
                if x >= w - 1:
                    break
                # matched text
                match_text = m.group(0)
                avail = max(0, w - 1 - x)
                if avail <= 0:
                    break
                if use_colors:
                    self._inner_win.addnstr(
                        y, x, match_text[:avail], avail, curses.color_pair(2)
                    )
                    x += min(len(match_text), avail)
                else:
                    # bracketed fallback may exceed; clip carefully
                    bracketed = f"[{match_text}]"
                    self._inner_win.addnstr(y, x, bracketed[:avail], avail)
                    x += min(len(bracketed), avail)
                last_end = m.end()
            # remainder
            if last_end < len(line) and x < w - 1:
                rem = line[last_end:]
                avail = max(0, w - 1 - x)
                if avail > 0:
                    self._inner_win.addnstr(y, x, rem[:avail], avail)
        self._inner_win.refresh()
