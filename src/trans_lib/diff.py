from difflib import SequenceMatcher
import os
from pathlib import Path

from trans_lib.enums import Language
from trans_lib.helpers import read_string_from_file
from trans_lib.trans_db import ensure_lang_dirs

def diff_score(a: str, b: str) -> float:
    # ratio() in [0..1], based on length of longest common subsequence
    return SequenceMatcher(None, a, b).ratio()

def get_best_match_from_db(root_path: Path, lang: Language, txt: str) -> tuple[str, float]:
    """
    Returns the best match and the score between the provided chunk and all the chunks of the provided language.
    """
    dir = ensure_lang_dirs(root_path, [lang])[0]
    return get_best_match_in_dir(dir, txt)

def get_best_match_in_dir(dir: Path, txt: str) -> tuple[str, float]:
    """
    Returns the best match between the provided chunk and all the chunks in the given directory.
    """
    _, _, files = list(os.walk(dir))[0]
    best_txt, best_score = "", 0.

    for file in files:
        contents = read_string_from_file(dir / file)
        score = diff_score(contents, txt)
        if score > best_score:
            best_txt, best_score = contents, score
    return best_txt, best_score

