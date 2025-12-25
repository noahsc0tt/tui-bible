import json
import os
from typing import Any, Dict, Optional


def state_file() -> str:
    """Return the path used to persist last position."""

    return os.path.join(os.path.expanduser("~"), ".bible_last.json")


def load_last_position(reader) -> Optional[Dict[str, Any]]:
    """Load last position from disk and apply translation.

    On success, returns a dict with translation/book/chapter/verse
    (all as strings or None for chapter/verse). On failure, returns
    None and leaves the reader at its current root.
    """

    try:
        with open(state_file(), "r") as f:
            st = json.load(f)
    except Exception:
        return None

    translations = reader.get_translations()
    trans = st.get("translation")
    if trans not in translations:
        return None

    reader.set_root(trans)
    return {
        "translation": trans,
        "book": st.get("book"),
        "chapter": str(st.get("chapter")) if st.get("chapter") is not None else None,
        "verse": str(st.get("verse")) if st.get("verse") is not None else None,
    }


def apply_position(main, pos: Optional[Dict[str, Any]]) -> None:
    """Apply a previously saved position to the UI windows.

    Expects a dict with keys translation/book/chapter/verse, all
    strings, or None for chapter/verse. Swallows any selection
    errors so that corrupted state does not break startup.
    """

    if not pos:
        return
    try:
        main.translations_win.select_value(pos["translation"])
        main.update_selections()
        if pos.get("book"):
            main.books_win.select_value(pos["book"])
            main.update_selections()
        if pos.get("chapter"):
            main.chapters_win.select_value(pos["chapter"])
            main.update_selections()
        if pos.get("verse"):
            main.verses_win.select_value(pos["verse"])
    except Exception:
        pass


def save_position(main) -> None:
    """Persist the current selection (translation/book/chapter/verse)."""

    try:
        data = {
            "translation": main.translations_win.get_selection_tuple()[1],
            "book": main.books_win.get_selection_tuple()[1],
            "chapter": main.chapters_win.get_selection_tuple()[1],
            "verse": main.verses_win.get_selection_tuple()[1],
        }
        with open(state_file(), "w") as f:
            json.dump(data, f)
    except Exception:
        pass
