"""Selection synchronization between list windows and Reader.

Keeps chapters and verses in sync when translation/book/chapter change.
"""


def update_selections(app, reader):
    trans = app.translations_win.get_selection_tuple()[1]
    reader.set_root(trans)

    book = app.books_win.get_selection_tuple()[1]
    chapter_tuples = list(enumerate(reader.get_chapters(book)))
    app.chapters_win.set_selection_tuples(chapter_tuples)

    chapter = app.chapters_win.get_selection_tuple()[1]
    verses_tuples = list(enumerate(reader.get_verses(book, chapter)))
    app.verses_win.set_selection_tuples(verses_tuples)
