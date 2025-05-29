import os
from pathlib import Path
from typing import Iterable

from trans_lib.enums import Language
from trans_lib.helpers import calculate_checksum, ensure_dir_exists, read_string_from_file

DB_DIR_NAME = "trans_git_db"

def ensure_db_dir(root_path: Path) -> None:
    db_full_dir_path = root_path.joinpath(DB_DIR_NAME)
    ensure_dir_exists(db_full_dir_path)

def ensure_lang_dirs(root_path: Path, langs: Iterable[Language]) -> None:
    db_full_dir_path = root_path.joinpath(DB_DIR_NAME)
    for lang in langs:
        lang_str = str(lang)
        lang_full_path = db_full_dir_path.joinpath(lang_str)
        ensure_dir_exists(lang_full_path)

def add_contents(root_path: Path, contents: str, lang: Language) -> str:
    """
    Adds the given contents to the database of checksum contents to the appropriate language directory and returns the contents checksum
    """
    ensure_db_dir(root_path)
    ensure_lang_dirs(root_path, [lang])
    lang_dir_full_path = root_path.joinpath(DB_DIR_NAME).joinpath(str(lang))
    checksum = calculate_checksum(contents)
    file_path = lang_dir_full_path.joinpath(checksum)
    with open(file_path, "w") as f:
        f.write(contents)
    return checksum

def read_contents_by_checksum_with_lang(root_path: Path, checksum: str, lang: Language) -> str | None:
    """
    Looks for a file with the given checksum in the directory of the given lanaguage and returns its contents if it finds such file and None if it doesn't

    Note: better performance then a usual [read_contents_by_checksum]
    """
    ensure_db_dir(root_path)
    lang_dir_full_path = root_path.joinpath(DB_DIR_NAME).joinpath(str(lang))
    return _read_contents_by_checksum_in_dir(checksum, lang_dir_full_path)

def _read_contents_by_checksum_in_dir(checksum: str, dir: Path) -> str | None:
    if not os.path.exists(dir) or not dir.is_dir():
        return None
    for file in dir.iterdir():
        if not file.is_file():
            continue
        file_name = file.name
        if file_name == checksum:
            return read_string_from_file(file.absolute())
    return None

def read_contents_by_checksum(root_path: Path, checksum: str) -> str | None:
    """
    Iterates through all the files in all the lang directories and searches for the checksum and returns the contents if it finds such file and None if it doesn't
    """
    ensure_db_dir(root_path)
    db_dir_path = root_path.joinpath(DB_DIR_NAME)
    if not os.path.exists(db_dir_path):
        return None

    for dir in db_dir_path.iterdir():
        if not dir.is_dir():
            continue

        path = dir.absolute()
        res = _read_contents_by_checksum_in_dir(checksum, path)
        if res is not None:
            return res

    return None
