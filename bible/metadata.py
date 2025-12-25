"""Shared Bible metadata: book order and abbreviations.

Central place for canonical 66-book order and reference parsing.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import re

# Standard 66-book order for mapping numeric-only sources like BSB
BOOK_ORDER = [
    "Genesis",
    "Exodus",
    "Leviticus",
    "Numbers",
    "Deuteronomy",
    "Joshua",
    "Judges",
    "Ruth",
    "1 Samuel",
    "2 Samuel",
    "1 Kings",
    "2 Kings",
    "1 Chronicles",
    "2 Chronicles",
    "Ezra",
    "Nehemiah",
    "Esther",
    "Job",
    "Psalms",
    "Proverbs",
    "Ecclesiastes",
    "Song of Solomon",
    "Isaiah",
    "Jeremiah",
    "Lamentations",
    "Ezekiel",
    "Daniel",
    "Hosea",
    "Joel",
    "Amos",
    "Obadiah",
    "Jonah",
    "Micah",
    "Nahum",
    "Habakkuk",
    "Zephaniah",
    "Haggai",
    "Zechariah",
    "Malachi",
    "Matthew",
    "Mark",
    "Luke",
    "John",
    "Acts",
    "Romans",
    "1 Corinthians",
    "2 Corinthians",
    "Galatians",
    "Ephesians",
    "Philippians",
    "Colossians",
    "1 Thessalonians",
    "2 Thessalonians",
    "1 Timothy",
    "2 Timothy",
    "Titus",
    "Philemon",
    "Hebrews",
    "James",
    "1 Peter",
    "2 Peter",
    "1 John",
    "2 John",
    "3 John",
    "Jude",
    "Revelation",
]

# Book abbreviations used for reference jumping, e.g. "Prov 18:10".
BOOK_ABBREV: Dict[str, str] = {
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

# Precomputed reverse mapping: abbrev (lowercased) -> full book name
_ABBREV_TO_BOOK: Dict[str, str] = {
    abbrev.lower(): full for full, abbrev in BOOK_ABBREV.items()
}

# Same reference pattern as previously used in main.py
_REF_RE = re.compile(r"([1-3]?[A-Za-z]+)\s+(\d+)(?::(\d+))?")


def parse_reference(ref: str) -> Optional[Tuple[str, str, Optional[str]]]:
    """Parse a string like "Prov 18:10" into (book, chapter, verse).

    Returns (full_book_name, chapter_str, verse_str_or_None) or None if invalid.
    """

    if not ref:
        return None
    m = _REF_RE.match(ref.strip())
    if not m:
        return None
    book_abbrev = m.group(1)
    chapter_num = m.group(2)
    verse_num = m.group(3)
    target_full = _ABBREV_TO_BOOK.get(book_abbrev.lower())
    if not target_full:
        return None
    return target_full, chapter_num, verse_num
