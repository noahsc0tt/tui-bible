#!/usr/bin/env python3

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

MD_DIR = Path(__file__).parent / "translations" / "MD"
BOOKS_GLOB = "Holy Bible%2F*.md"
BOOK_LINKS_FILE = MD_DIR / "Holy Bible.md"

VERSE_HEADER_RE = re.compile(r"^\s*-\s*\*\*.+?\s(\d+):(\d+)\*\*\s*$")


def find_book_files():
    # Files are flat in MD dir with "%2F" in names, e.g. "Holy Bible%2FGenesis.md"
    for p in sorted(MD_DIR.glob("Holy Bible%2F*.md")):
        yield p


def book_name_from_file(path: Path) -> str:
    # Filenames are URL-encoded, e.g. "Holy Bible%2F1 Samuel.md"
    decoded = unquote(path.name)  # e.g. "Holy Bible/1 Samuel.md"
    name = decoded.rsplit(".", 1)[0]
    if name.startswith("Holy Bible/"):
        name = name.split("/", 1)[1]
    return name


def iter_chapter_verses(lines, book_name):
    # Yields tuples: (chapter:int, verse:int, text:str)
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip("\n")
        m = VERSE_HEADER_RE.match(line)
        if m:
            chap = int(m.group(1))
            verse = int(m.group(2))
            # Collect subsequent content lines until next verse header or end
            j = i + 1
            content_lines = []
            while j < n:
                next_line = lines[j].rstrip("\n")
                if VERSE_HEADER_RE.match(next_line):
                    break
                # Skip empty structural lines like title::
                if next_line.strip().startswith("title::"):
                    j += 1
                    continue
                content_lines.append(next_line)
                j += 1
            text = " ".join(l.strip() for l in content_lines if l.strip())
            yield chap, verse, text
            i = j
            continue
        i += 1


def write_chapter_page(out_dir: Path, book: str, chapter: int, verses):
    out_dir.mkdir(parents=True, exist_ok=True)
    chapter_md = out_dir / f"{chapter}.md"
    lines = [f"# {book} {chapter}", ""]
    for vnum, vtext in verses:
        # Use simple verse marker notation
        if vtext:
            lines.append(f"({vnum}) {vtext}")
        else:
            lines.append(f"({vnum})")
        lines.append("")
    chapter_md.write_text("\n".join(lines), encoding="utf-8")


def write_book_index(out_book_dir: Path, book: str, chapters_sorted):
    out_book_dir.mkdir(parents=True, exist_ok=True)
    idx = out_book_dir / "index.md"
    lines = [f"# {book}", "", "Chapters:"]
    lines.append("")
    # Link to each chapter
    line = []
    for ch in chapters_sorted:
        line.append(f"[{'%d' % ch}]({ch}.md)")
        if len(line) >= 16:
            lines.append(" ".join(line))
            line = []
    if line:
        lines.append(" ".join(line))
    lines.append("")
    idx.write_text("\n".join(lines), encoding="utf-8")


def write_translation_index(out_trans_dir: Path, translation_name: str, books_sorted):
    out_trans_dir.mkdir(parents=True, exist_ok=True)
    idx = out_trans_dir / "index.md"
    lines = [f"# {translation_name}", "", "Books:", ""]
    for book in books_sorted:
        lines.append(f"- [{book}]({book}/index.md)")
    lines.append("")
    idx.write_text("\n".join(lines), encoding="utf-8")


def write_site_index(out_root: Path, translation_dir_name: str, translation_name: str):
    out_root.mkdir(parents=True, exist_ok=True)
    idx = out_root / "index.md"
    lines = [
        "# Bible",
        "",
        "Translations:",
        "",
        f"- [{translation_name}]({translation_dir_name}/index.md)",
        "",
    ]
    idx.write_text("\n".join(lines), encoding="utf-8")


def generate(out: Path, translation_dir_name: str, translation_name: str) -> None:
    out_trans = out / translation_dir_name

    books = []
    for book_file in find_book_files():
        book = book_name_from_file(book_file)
        books.append(book)
        # Build chapter map
        chapter_map = {}
        with book_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        for chap, verse, text in iter_chapter_verses(lines, book):
            chapter_map.setdefault(chap, []).append((verse, text))
        if not chapter_map:
            continue
        # Output book directory + chapters
        out_book_dir = out_trans / book
        for chap in sorted(chapter_map.keys(), key=int):
            verses = sorted(chapter_map[chap], key=lambda t: t[0])
            write_chapter_page(out_book_dir, book, chap, verses)
        write_book_index(out_book_dir, book, sorted(chapter_map.keys(), key=int))

    # Indexes
    books_sorted = sorted(books, key=lambda s: s.upper())
    write_translation_index(out_trans, translation_name, books_sorted)
    write_site_index(out, translation_dir_name, translation_name)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a Frogmouth-compatible Markdown site from MD Bible files"
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "markdown"),
        help="Output directory for generated site (default: ./markdown)",
    )
    parser.add_argument(
        "--translation-dir",
        default="BSB",
        help="Directory name to use for translation under output (default: BSB)",
    )
    parser.add_argument(
        "--translation-name",
        default="Berean Standard Bible (MD)",
        help="Human-readable translation name (default: Berean Standard Bible (MD))",
    )
    args = parser.parse_args(argv)

    out = Path(args.out)
    generate(out, args.translation_dir, args.translation_name)
    print(f"Generated Frogmouth site at: {out}")
    print(f"Open with: frogmouth {out / 'index.md'}")


if __name__ == "__main__":
    main()
