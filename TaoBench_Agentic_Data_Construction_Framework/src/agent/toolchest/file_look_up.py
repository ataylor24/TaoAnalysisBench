import os
from globals import ANALYSIS_BOOK_DIRECTORY

def file_look_up(chapter_name: str) -> str:
    with open(os.path.join(ANALYSIS_BOOK_DIRECTORY, chapter_name + ".lean"), "r") as f:
        return f.read()