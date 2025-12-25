from pathlib import Path

from .search_manager import SearchManager


class Search:
    """Backwards-compatible facade exposing verse search.

    This wraps SearchManager so external callers can continue importing
    `bible.Search` while the internal implementation lives in search_manager.
    """

    def __init__(self, base_dir: Path):
        self._manager = SearchManager(base_dir / "translations")

    def search_verses(
        self,
        query: str,
        *,
        translation: str | None = None,
        book: str | None = None,
        chapter: str | None = None,
        limit: int | None = None,
    ):
        return self._manager.search_verses(
            query,
            translation=translation,
            book=book,
            chapter=chapter,
            limit=limit,
        )
