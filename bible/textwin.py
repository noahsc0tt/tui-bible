import curses


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

    def update_text(self, text):
        self._inner_win.clear()
        if curses.has_colors():
            self._inner_win.bkgd(" ", curses.color_pair(1))
        # Render line-by-line within bounds to avoid addstr ERR
        h, w = self._inner_win.getmaxyx()
        lines = text.splitlines()
        max_lines = min(h, len(lines))
        for y in range(max_lines):
            self._inner_win.addnstr(y, 0, lines[y], max(0, w - 1))
        self._inner_win.refresh()
