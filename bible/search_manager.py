from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap
from typing import Dict, List, Optional, Tuple

from .metadata import BOOK_ORDER


Result = Tuple[str, str, str, str, str]


@dataclass(frozen=True)
class Scope:
    translation: Optional[str] = None
    book: Optional[str] = None
    chapter: Optional[str] = None


@dataclass(frozen=True)
class Match:
    translation: str
    book: str
    chapter: str
    verse: str
    text: str

    def as_result(self) -> Result:
        return (self.translation, self.book, self.chapter, self.verse, self.text)


class VerseIndex:
    """Builds a normalized in‑memory verse index from translation XML files.

    Structure: index[translation][book][chapter][verse] = plain_text
    Book normalization prefers explicit name attribute; falls back to number lookup via BOOK_ORDER.
    Chapter/verse keys always stored as string numbers.
    """

    def __init__(self, translations_dir: Path):
        self._translations_dir = translations_dir
        self._index: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
        self._built = False

    def build(self) -> None:
        if self._built:
            return
        for xmlfile in sorted(self._translations_dir.glob("*.xml")):
            translation = xmlfile.stem
            try:
                tree = ET.parse(xmlfile)
                root = tree.getroot()
            except Exception:
                continue
            tmap: Dict[str, Dict[str, Dict[str, str]]] = {}
            # Detect format by presence of elements
            old_format_books = root.findall("b")  # <b n="Genesis">...
            bsb_books = root.findall(".//book")  # <book number="1">...
            if bsb_books:
                for book_el in bsb_books:
                    book_name: Optional[str] = None
                    num = book_el.get("number") or book_el.get("n")
                    name_attr = book_el.get("name")
                    if name_attr and any(ch.isalpha() for ch in name_attr):
                        book_name = name_attr.strip()
                    elif num and num.isdigit():
                        idx = int(num) - 1
                        if 0 <= idx < len(BOOK_ORDER):
                            book_name = BOOK_ORDER[idx]
                    if not book_name:
                        continue
                    chapters_map: Dict[str, Dict[str, str]] = {}
                    for chap_el in book_el.findall("chapter"):
                        chap_num = chap_el.get("number") or chap_el.get("n")
                        if not chap_num:
                            continue
                        chap_key = str(chap_num)
                        verses_map: Dict[str, str] = {}
                        for verse_el in chap_el.findall("verse"):
                            verse_num = verse_el.get("number") or verse_el.get("n")
                            if not verse_num:
                                continue
                            verse_key = str(verse_num)
                            verse_text = "".join(verse_el.itertext()).strip()
                            verses_map[verse_key] = verse_text
                        chapters_map[chap_key] = verses_map
                    tmap[book_name] = chapters_map
            elif old_format_books:
                for book_el in old_format_books:
                    book_name = book_el.attrib.get("n") or book_el.attrib.get("name")
                    if not book_name:
                        num = book_el.attrib.get("number") or book_el.attrib.get("n")
                        if num and str(num).isdigit():
                            idx = int(num) - 1
                            if 0 <= idx < len(BOOK_ORDER):
                                book_name = BOOK_ORDER[idx]
                    if not book_name:
                        continue
                    chapters_map: Dict[str, Dict[str, str]] = {}
                    for chap_el in book_el.findall("c"):
                        chap_key = str(
                            chap_el.attrib.get("n")
                            or chap_el.attrib.get("number")
                            or ""
                        )
                        if not chap_key:
                            continue
                        verses_map: Dict[str, str] = {}
                        for verse_el in chap_el.findall("v"):
                            verse_key = str(
                                verse_el.attrib.get("n")
                                or verse_el.attrib.get("number")
                                or ""
                            )
                            if not verse_key:
                                continue
                            verse_text = (verse_el.text or "").strip()
                            verses_map[verse_key] = verse_text
                        chapters_map[chap_key] = verses_map
                    tmap[book_name] = chapters_map
            self._index[translation] = tmap
        self._built = True

    def get(self) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
        self.build()
        return self._index


class SearchManager:
    """Provides scoped literal substring searching over the verse index."""

    def __init__(self, translations_dir: Path):
        self._index = VerseIndex(translations_dir)

    def search_literal(
        self, query: str, scope: Scope, *, limit: Optional[int] = None
    ) -> List[Match]:
        if not query:
            return []
        q = query.lower()
        data = self._index.get()
        translations = (
            [scope.translation]
            if scope.translation and scope.translation in data
            else list(data.keys())
        )
        matches: List[Match] = []
        for tr in translations:
            books = data.get(tr, {})
            book_keys = (
                [scope.book]
                if scope.book and scope.book in books
                else list(books.keys())
            )
            for bk in book_keys:
                chapters = books.get(bk, {})
                chapter_keys = (
                    [scope.chapter]
                    if scope.chapter and scope.chapter in chapters
                    else list(chapters.keys())
                )
                for ch in chapter_keys:
                    verses = chapters.get(ch, {})
                    for vs, text in verses.items():
                        if q in text.lower():
                            matches.append(Match(tr, bk, ch, vs, text))
                            if limit is not None and len(matches) >= limit:
                                return matches
        return matches

    # Simple compatibility layer mirroring bible.search.Search
    def search_verses(
        self,
        query: str,
        *,
        translation: Optional[str] = None,
        book: Optional[str] = None,
        chapter: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Result]:
        scope = Scope(translation=translation, book=book, chapter=chapter)
        matches = self.search_literal(query, scope, limit=limit)
        return [m.as_result() for m in matches]

    @staticmethod
    def scope_label(scope: Scope) -> str:
        if scope.translation and scope.book and scope.chapter:
            return f"[{scope.translation} {scope.book} {scope.chapter}]"
        if scope.translation and scope.book:
            return f"[{scope.translation} {scope.book}]"
        if scope.book and scope.chapter:
            return f"[{scope.book} {scope.chapter}]"
        if scope.book:
            return f"[{scope.book}]"
        if scope.translation:
            return f"[{scope.translation}]"
        return "[ALL]"

    @staticmethod
    def format_results(matches: List[Match], width: int) -> str:
        if not matches:
            return "No matches"
        wrap_width = max(1, width - 3)
        lines: List[str] = []
        for m in matches:
            base = f"{m.translation} {m.book} {m.chapter}:{m.verse} — {m.text}"
            for wl in wrap(base, width=wrap_width):
                lines.append(wl)
            lines.append("")
        return "\n".join(lines)
