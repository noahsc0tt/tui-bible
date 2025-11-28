from glob import glob
from os.path import splitext, basename, dirname, join
import xml.etree.ElementTree as ET

TRANSLATIONS_DIR = join(dirname(__file__), "translations")

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


class Reader:
    def __init__(self):
        self._load_roots()

    def _scan_translation_files(self):
        return [
            splitext(basename(f))[0] for f in glob("{0}/*.xml".format(TRANSLATIONS_DIR))
        ]

    def _load_roots(self):
        self._current_root = (None, None)
        self._roots = {}
        for ts in self._scan_translation_files():
            tree = self._get_root(ts)
            if self._is_bsb_like(tree) or self._is_old_format(tree):
                self._roots[ts] = tree

    def _get_root(self, translation_str):
        return ET.parse("{0}/{1}.xml".format(TRANSLATIONS_DIR, translation_str))

    def _is_old_format(self, tree):
        # Old format: <bible><b n="Genesis"><c n="1"><v n="1">...
        root = tree.getroot()
        return root.find("b") is not None

    def _is_bsb_like(self, tree):
        # BSB: <bible><testament name="Old|New"><book number="1"><chapter number="1"><verse number="1">
        root = tree.getroot()
        return root.tag.lower() == "bible" and root.find("testament") is not None

    def set_root(self, translation_str):
        if self._current_root[0] == translation_str:
            return
        if translation_str not in self._roots:
            raise KeyError("Unsupported translation: {0}".format(translation_str))
        self._current_root = (translation_str, self._roots[translation_str])

    def get_translations(self):
        return sorted(self._roots.keys(), key=lambda s: s.upper())

    def get_books(self):
        tree = self._current_root[1]
        root = tree.getroot()
        if self._is_bsb_like(tree):
            return BOOK_ORDER
        else:  # old format
            return [bel.attrib["n"] for bel in root.findall("b")]

    def _bsb_book_element(self, root, book_str):
        # Map human-readable book name to numeric index in BSB
        try:
            bn = str(BOOK_ORDER.index(book_str) + 1)
        except ValueError:
            return None
        # Search across both testaments
        return root.find(".//book[@number='{0}']".format(bn))

    def get_chapters(self, book_str):
        tree = self._current_root[1]
        root = tree.getroot()
        if self._is_bsb_like(tree):
            bel = self._bsb_book_element(root, book_str)
            if bel is None:
                return []
            return [chel.get("number") for chel in bel.findall("chapter")]
        else:  # old format
            bel = root.find("b[@n='{0}']".format(book_str))
            if bel is None:
                return []
            return [chel.attrib["n"] for chel in bel.findall("c")]

    def get_verses_elements(self, book_str, chapter_str):
        tree = self._current_root[1]
        root = tree.getroot()
        if self._is_bsb_like(tree):
            bel = self._bsb_book_element(root, book_str)
            if bel is None:
                return []
            chel = bel.find("chapter[@number='{0}']".format(chapter_str))
            if chel is None:
                return []
            return chel.findall("verse")
        else:  # old format
            bel = root.find("b[@n='{0}']".format(book_str))
            if bel is None:
                return []
            chel = bel.find("c[@n='{0}']".format(chapter_str))
            if chel is None:
                return []
            return chel.findall("v")

    def get_verses(self, book_str, chapter_str):
        vels = self.get_verses_elements(book_str, chapter_str)
        if not vels:
            return []
        first = vels[0]
        if first.tag == "verse":
            return [vel.get("number") for vel in vels]
        else:
            return [vel.attrib["n"] for vel in vels]

    def get_chapter_text(self, book_str, chapter_str, verse_start=1):
        vels = self.get_verses_elements(book_str, chapter_str)
        if not vels:
            return ""
        t = vels[0].tag
        if t == "verse":
            filtered = [v for v in vels if int(v.get("number")) >= int(verse_start)]
            return " ".join(
                "({0}) {1}".format(v.get("number"), (v.text or "").strip())
                for v in filtered
            )
        else:
            filtered = [v for v in vels if int(v.attrib.get("n")) >= int(verse_start)]
            return " ".join(
                "({0}) {1}".format(v.attrib.get("n"), (v.text or "").strip())
                for v in filtered
            )
