import curses


class ListWindow:
    def __init__(self, win, title, item_tuples, width):
        self.MAX_ITEMS = curses.LINES - 2

        self._win = win
        self._width = width
        self._title = title
        self._active = False
        self._item_tuples = item_tuples or []
        self._selected_tuple = (0, "")
        self._bounds = (0, 0)
        self._hint = ""
        self._search_query = ""
        self._search_total = 0
        self._search_index = 0
        self.select_first()

    def select_value(self, value):
        for i, v in self._item_tuples:
            if v == value:
                self._selected_tuple = (i, v)
                start = max(0, min(i, max(0, len(self._item_tuples) - self.MAX_ITEMS)))
                self._bounds = (start, start + self.MAX_ITEMS)
                self.draw()
                return
        self.select_first()

    def set_active(self, is_active):
        self._active = is_active
        self.draw()

    def resize(self, width):
        # Adjust width dynamically (used on terminal resize)
        self._width = width
        try:
            self._win = curses.newwin(curses.LINES, width, 0, self._win.getbegyx()[1])
        except Exception:
            pass
        self.draw()

    def get_selection_tuple(self):
        return self._selected_tuple

    def set_selection_tuples(self, item_tuples):
        self._item_tuples = item_tuples or []
        prev_val = self._selected_tuple[1]
        if self._item_tuples:
            for i, v in self._item_tuples:
                if v == prev_val:
                    self._selected_tuple = (i, v)
                    start = max(
                        0, min(i, max(0, len(self._item_tuples) - self.MAX_ITEMS))
                    )
                    self._bounds = (start, start + self.MAX_ITEMS)
                    self.draw()
                    return
            self.select_first()
        else:
            self._selected_tuple = (0, "")
            self._bounds = (0, 0)
            self.draw()

    def increment_selection(self, i):
        if not self._item_tuples:
            return
        new_index = self._selected_tuple[0] + i
        if new_index < 0 or new_index >= len(self._item_tuples):
            return

        self._selected_tuple = self._item_tuples[new_index]

        (bound_lower, bound_upper) = self._bounds

        shift_up = bound_upper <= new_index < len(self._item_tuples)
        shift_down = 0 <= new_index < bound_lower
        shift = shift_down or shift_up

        if shift:
            new_lower = max(
                0, min(bound_lower + i, max(0, len(self._item_tuples) - self.MAX_ITEMS))
            )
            self._bounds = (new_lower, new_lower + self.MAX_ITEMS)

        self.draw()

    def select_first(self):
        if self._item_tuples:
            self._selected_tuple = self._item_tuples[0]
            self._bounds = (0, self.MAX_ITEMS)
        else:
            self._selected_tuple = (0, "")
            self._bounds = (0, 0)
        self.draw()

    def select_last(self):
        if self._item_tuples:
            self._selected_tuple = self._item_tuples[-1]
            start = max(0, len(self._item_tuples) - self.MAX_ITEMS)
            self._bounds = (start, start + self.MAX_ITEMS)
        else:
            self._selected_tuple = (0, "")
            self._bounds = (0, 0)
        self.draw()

    def _prepare_search_meta(self, query):
        q = str(query).lower()
        matches = [i for i, v in self._item_tuples if q in str(v).lower()]
        self._search_query = str(query)
        self._search_total = len(matches)
        # Determine current index position among matches
        cur_idx = self._selected_tuple[0]
        try:
            self._search_index = matches.index(cur_idx) + 1 if cur_idx in matches else 0
        except Exception:
            self._search_index = 0
        return matches

    def search_select(self, query, start_at_current=True):
        if not self._item_tuples or not query:
            return False
        q = str(query).lower()
        n = len(self._item_tuples)
        start = self._selected_tuple[0] if start_at_current else 0
        for off in range(n):
            i = (start + off) % n
            if q in str(self._item_tuples[i][1]).lower():
                self._selected_tuple = self._item_tuples[i]
                start_bound = max(0, min(i, max(0, n - self.MAX_ITEMS)))
                self._bounds = (start_bound, start_bound + self.MAX_ITEMS)
                self._prepare_search_meta(query)
                self.draw()
                return True
        self._prepare_search_meta(query)
        self.draw()
        return False

    def search_next(self, query):
        if not self._item_tuples or not query:
            return False
        q = str(query).lower()
        n = len(self._item_tuples)
        start = self._selected_tuple[0]
        for off in range(1, n + 1):
            i = (start + off) % n
            if q in str(self._item_tuples[i][1]).lower():
                self._selected_tuple = self._item_tuples[i]
                start_bound = max(0, min(i, max(0, n - self.MAX_ITEMS)))
                self._bounds = (start_bound, start_bound + self.MAX_ITEMS)
                self._prepare_search_meta(query)
                self.draw()
                return True
        self._prepare_search_meta(query)
        self.draw()
        return False

    def search_prev(self, query):
        if not self._item_tuples or not query:
            return False
        q = str(query).lower()
        n = len(self._item_tuples)
        start = self._selected_tuple[0]
        for off in range(1, n + 1):
            i = (start - off) % n
            if q in str(self._item_tuples[i][1]).lower():
                self._selected_tuple = self._item_tuples[i]
                start_bound = max(0, min(i, max(0, n - self.MAX_ITEMS)))
                self._bounds = (start_bound, start_bound + self.MAX_ITEMS)
                self._prepare_search_meta(query)
                self.draw()
                return True
        self._prepare_search_meta(query)
        self.draw()
        return False

    def write_title(self):
        base = self._title
        if self._search_query:
            suffix = f"[{self._search_query}"  # start bracket
            if self._search_total:
                suffix += f" {self._search_index}/{self._search_total}"
            suffix += "]"
            base = f"{self._title} {suffix}"
        # Use actual window width to avoid errors on hidden 1x1 windows
        try:
            _, actual_w = self._win.getmaxyx()
        except Exception:
            actual_w = self._width
        draw_w = max(1, min(self._width, actual_w))
        title_str = base.center(draw_w, " ")
        try:
            self._win.addnstr(0, 0, title_str, draw_w, curses.A_UNDERLINE)
        except Exception:
            pass

    def draw(self):
        # Skip drawing content for hidden 1x1 off-screen windows
        try:
            h, w = self._win.getmaxyx()
        except Exception:
            h, w = (0, 0)
        is_hidden = h <= 1 or w <= 1
        self._win.clear()
        if curses.has_colors():
            self._win.bkgd(" ", curses.color_pair(1))
        if not is_hidden:
            self.write_title()
        if is_hidden:
            return

        if self._item_tuples:
            max_rows = max(0, h - 2)
            visible = self._item_tuples[self._bounds[0] : self._bounds[1]]
            for idx, (i, val) in enumerate(visible):
                if idx >= max_rows:
                    break
                y = 1 + idx
                str_len = max(0, min(self._width - 2, w - 2))
                s = str(val)
                if len(s) > str_len:
                    s = s[:str_len]
                string = s.ljust(str_len)

                if i == self._selected_tuple[0]:
                    self._win.addnstr(
                        y,
                        0,
                        ">{0}".format(string),
                        min(str_len + 1, w - 1),
                        curses.A_STANDOUT if self._active else curses.A_BOLD,
                    )
                else:
                    self._win.addnstr(y, 1, string, str_len)

        self._win.refresh()

    def clear_search_hint(self):
        self._search_query = ""
        self._search_total = 0
        self._search_index = 0
        self.draw()
