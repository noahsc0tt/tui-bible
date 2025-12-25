from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from .search_manager import Match


@dataclass
class SearchState:
    """State for list search hints ("i" / n / N).

    This tracks which window the last incremental search applied to,
    and the query string itself.
    """

    last_window: Any = None
    query: str = ""


@dataclass
class GrepState:
    """State for grep-like verse searching ("/", "n", "N", "r", "K", "J")."""

    pattern: str = ""
    results: List[Match] = field(default_factory=list)
    index: int = -1  # active Match index in results
    pane_index: int = 0  # selection index inside grep results pane
    override_text: Optional[str] = None
    override_title: Optional[str] = None
    history: List[dict] = field(default_factory=list)
    history_idx: int = -1


@dataclass
class UiState:
    """State for non-textual UI concerns (sidebar visibility, active pane)."""

    sidebars_visible: bool = True
    active_window_index: int = 0


@dataclass
class State:
    """Top-level application state container used by Main.

    This keeps search/grep/UI state in one place so that future
    refactors (e.g. command handlers) can work with a single object.
    """

    search: SearchState = field(default_factory=SearchState)
    grep: GrepState = field(default_factory=GrepState)
    ui: UiState = field(default_factory=UiState)
