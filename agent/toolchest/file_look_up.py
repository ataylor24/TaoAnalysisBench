import os
from globals import ANALYSIS_BOOK_DIRECTORY

def file_look_up(chapter_name: str) -> str:
    chapter_name = chapter_name + ".lean" if not chapter_name.endswith(".lean") else chapter_name
    with open(os.path.join(ANALYSIS_BOOK_DIRECTORY, chapter_name), "r") as f:
        return f.read()