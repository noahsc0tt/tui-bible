import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Result tuple: (translation, book, chapter, verse, text)
Result = Tuple[str, str, str, str, str]


class VerseIndex:
    def __init__(self, translations_dir: Path):
        self.translations_dir = translations_dir
        self._index: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
        self._built = False

    def build(self):
        if self._built:
            return
        for xmlfile in sorted(self.translations_dir.glob("*.xml")):
            translation = xmlfile.stem
            try:
                tree = ET.parse(xmlfile)
                root = tree.getroot()
            except Exception:
                continue
            tmap: Dict[str, Dict[str, Dict[str, str]]] = {}
            # Support both MD and XML structures:
            # XML form: <book number="1" name="Genesis"><chapter number="1"><verse number="1">text</verse></chapter></book>
            # Alt form: compact tags b/c/v
            for bel in list(root):
                book_name = (
                    bel.get("name") or bel.attrib.get("n") or bel.attrib.get("number")
                )
                # If only number is present, attempt to map later; keep as str
                book_key = str(book_name) if book_name is not None else ""
                if not book_key:
                    # fallback: try text content
                    book_key = bel.tag
                cmap: Dict[str, Dict[str, str]] = {}
                for chel in list(bel):
                    chap = chel.get("number") or chel.attrib.get("n")
                    chapter_key = str(chap) if chap is not None else ""
                    vmap: Dict[str, str] = {}
                    for vel in list(chel):
                        verse = vel.get("number") or vel.attrib.get("n")
                        verse_key = str(verse) if verse is not None else ""
                        # Extract plain text by joining all text recursively
                        text = "".join(vel.itertext()).strip()
                        vmap[verse_key] = text
                    cmap[chapter_key] = vmap
                tmap[book_key] = cmap
            self._index[translation] = tmap
        self._built = True

    def search_literal(
        self,
        query: str,
        translation: Optional[str] = None,
        book: Optional[str] = None,
        chapter: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Result]:
        if not query:
            return []
        self.build()
        q = query.lower()
        results: List[Result] = []
        translations = (
            [translation]
            if translation and translation in self._index
            else list(self._index.keys())
        )
        for tr in translations:
            books = self._index.get(tr, {})
            # book filter by name key exact match
            book_keys = [book] if book and book in books else list(books.keys())
            for bk in book_keys:
                chapters = books.get(bk, {})
                chapter_keys = (
                    [chapter]
                    if chapter and chapter in chapters
                    else list(chapters.keys())
                )
                for ch in chapter_keys:
                    verses = chapters.get(ch, {})
                    for vs, text in verses.items():
                        if q in text.lower():
                            results.append((tr, bk, str(ch), str(vs), text))
                            if limit is not None and len(results) >= limit:
                                return results
        return results


class Search:
    """Deprecated shim kept for backward compatibility.

    New code should import `Search` from `bible` or use
    `bible.search_manager.SearchManager` directly. This class simply
    forwards to the package-level `Search` facade.
    """

    def __init__(self, base_dir: Path):
        # Late import to avoid cycles
        from . import Search as _SearchFacade

        self._delegate = _SearchFacade(base_dir)

    def search_verses(
        self,
        query: str,
        *,
        translation: Optional[str] = None,
        book: Optional[str] = None,
        chapter: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Result]:
        return self._delegate.search_verses(
            query,
            translation=translation,
            book=book,
            chapter=chapter,
            limit=limit,
        )
