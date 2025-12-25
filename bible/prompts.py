"""Prompt utilities for the Bible TUI."""

import curses


def prompt_input_cancelable(stdscr, prompt_text: str):
    """Prompt for a single-line input that can be cancelled with ESC.

    Returns the entered string (stripped), an empty string for blank input,
    or None if the user pressed ESC.
    """

    h, w = stdscr.getmaxyx()
    buf = []
    max_len = max(0, w - len(prompt_text) - 1)
    curses.noecho()
    while True:
        # Render prompt + current buffer
        stdscr.move(h - 1, 0)
        stdscr.clrtoeol()
        display = prompt_text + "".join(buf)
        stdscr.addnstr(h - 1, 0, display, max(0, w - 1))
        stdscr.refresh()

        ch = stdscr.getch()
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
            if len(buf) < max_len:
                buf.append(chr(ch))

    # Clear prompt line
    stdscr.move(h - 1, 0)
    stdscr.clrtoeol()
    stdscr.refresh()

    if buf is None:
        return None
    s = "".join(buf).strip()
    return s if s else ""
