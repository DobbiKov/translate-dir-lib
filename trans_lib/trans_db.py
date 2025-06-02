import os
import csv
from pathlib import Path
from typing import Iterable

from trans_lib.enums import Language
from trans_lib.helpers import calculate_checksum, ensure_dir_exists, read_string_from_file
from trans_lib.constants import DB_DIR_NAME, CORRESPONDENCE_DB_NAME


def ensure_db_dir(root_path: Path) -> None:
    db_full_dir_path = root_path.joinpath(DB_DIR_NAME)
    ensure_dir_exists(db_full_dir_path)

def ensure_lang_dirs(root_path: Path, langs: Iterable[Language]) -> None:
    db_full_dir_path = root_path.joinpath(DB_DIR_NAME)
    for lang in langs:
        lang_str = str(lang)
        lang_full_path = db_full_dir_path.joinpath(lang_str)
        ensure_dir_exists(lang_full_path)


def add_contents_to_db(root_path: Path, contents: str, lang: Language) -> str:
    """
    Adds the given contents to the database of checksum contents to the appropriate language directory and returns the contents checksum
    """
    ensure_db_dir(root_path)
    ensure_lang_dirs(root_path, [lang])
    lang_dir_full_path = root_path.joinpath(DB_DIR_NAME).joinpath(str(lang))
    checksum = calculate_checksum(contents)
    file_path = lang_dir_full_path.joinpath(checksum)
    if os.path.exists(file_path): # if the checksum file already exists, then no need to write it
        return checksum

    with open(file_path, "w") as f:
        f.write(contents)
    return checksum

def read_contents_by_checksum_with_lang(root_path: Path, checksum: str, lang: Language) -> str | None:
    """
    Looks for a file with the given checksum in the directory of the given language and returns its contents if it finds such file and None if it doesn't

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

# correspondence db
def get_correspondence_db_path(root_path: Path) -> Path:
    """
    Returns a full path to the correspondence db file.
    """
    db_dir_path = root_path.joinpath(DB_DIR_NAME)
    file_path = db_dir_path.joinpath(CORRESPONDENCE_DB_NAME)
    return file_path

def ensure_correspondence_db(root_path: Path) -> None:
    file_path = get_correspondence_db_path(root_path)
    ensure_db_dir(root_path)
    if os.path.exists(file_path):
        return
    with open(file_path, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[])

        writer.writeheader()

def add_lang_to_db_data(fields: list[str], data_list: list[dict], lang: Language) -> tuple[list[str], list[dict]]:
    """
    Helper function.
    Adds language to the provided db data
    """
    if str(lang) in fields:
        return (fields, data_list)

    fields.append(str(lang)) 

    for i in range(len(data_list)):
        data_list[i][str(lang)] = ""

    return (fields, data_list)

def remove_lang_from_db_data(fields: list[str], data_list: list[dict], lang: Language) -> tuple[list[str], list[dict]]:
    """
    Helper function.
    Removes language from the provided db data
    """

    if str(lang) not in fields:
        return (fields, data_list)

    fields.remove(str(lang))
    for i in range(len(data_list)):
        data_list[i].pop(str(lang))

    return (fields, data_list)

def add_language_to_correspondence_db(root_path: Path, lang: Language) -> None:
    db_data = read_correspondence_db(root_path)
    if db_data is None: # if the db doesn't exist, then we create it and add our lang as a field
        write_correspondence_db(root_path, [], [str(lang)])
        return

    (fields, data_list) = db_data

    (fields, data_list) = add_lang_to_db_data(fields, data_list, lang)

    write_correspondence_db(root_path, data_list, fields)


def remove_language_from_correspondence_db(root_path: Path, lang: Language) -> None:
    db_data = read_correspondence_db(root_path)
    if db_data is None: # if the db doesn't exist, then do nothing
        ensure_correspondence_db(root_path)
        return

    (fields, data_list) = db_data

    (fields, data_list) = remove_lang_from_db_data(fields, data_list, lang)

    write_correspondence_db(root_path, data_list, fields)

def find_correspondent_checksum(root_path: Path, src_checksum: str, src_lang: Language, tgt_lang: Language) -> str | None:
    """
    Looks for the correspondent checksum of a particular language to the given checksum (of the given language) returns the checksum if finds it, None otherwise

    Example:
        eng_checksum | fr_checksum
        aaa          | aca
        baa          | aba

    ```py
    find_correspondent_checksum(., "aaa", English, French) # returns "aca"
    find_correspondent_checksum(., "aba", French, English) # returns "baa"
    find_correspondent_checksum(., "ccc", French, English) # returns None
    ```
    """
    if src_lang == tgt_lang:
        return None
    db_data = read_correspondence_db(root_path)
    if db_data is None: # if the db doesn't exist, then do nothing
        ensure_correspondence_db(root_path)
        return None

    (fields, data_list) = db_data
    if str(src_lang) not in fields or str(tgt_lang) not in fields:
        return None

    for data in data_list:
        if data[str(src_lang)] == src_checksum:
            tgt_checksum = data[str(tgt_lang)]
            if tgt_checksum == "": # if target checksum is an empty string, it means that for such source checksum and these languages there's no correspondence pair, return None
                return None 
            return tgt_checksum

    return None

def set_checksum_pair_to_correspondence_db(root_path: Path, src_checksum: str, src_lang: Language, tgt_checksum: str, tgt_lang: Language) -> None:
    if src_lang == tgt_lang:
        return None

    db_data = read_correspondence_db(root_path)
    if db_data is None: # if the db doesn't exist, then create it
        ensure_correspondence_db(root_path)

    (fields, data_list) = ([], [])
    if db_data is not None:
        (fields, data_list) = db_data

    if str(src_lang) not in fields:
        (fields, data_list) = add_lang_to_db_data(fields, data_list, src_lang)
    if str(tgt_lang) not in fields:
        (fields, data_list) = add_lang_to_db_data(fields, data_list, tgt_lang)

    for i in range(len(data_list)):
        if data_list[i][str(src_lang)] == src_checksum:
            data_list[i][str(tgt_lang)] = tgt_checksum
            write_correspondence_db(root_path, data_list, fields)
            return

    # if the source checksum isn't present in the db, then we create a new row with the pair
    new_row = {}
    for field in fields:
        new_row[field] = ""
    new_row[str(src_lang)] = src_checksum
    new_row[str(tgt_lang)] = tgt_checksum
    data_list.append(new_row)
    write_correspondence_db(root_path, data_list, fields)


    

def read_correspondence_db(root_path: Path) -> tuple[list[str], list[dict]] | None:
    """
    Returns (list of fields, data in dictionary format) or None if the db doesn't exist
    """

    file_path = get_correspondence_db_path(root_path)

    if not os.path.exists(file_path):
        return None

    data_list = []
    field_names = []
    
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        field_names: list[str] = list(csv_reader.fieldnames or [])

        for row in csv_reader:
            data_list.append(row)
            
    return (field_names, data_list)

def write_correspondence_db(root_path: Path, data_list: list[dict], fields: list[str] = []) -> None:
    """
    Writes correspondence db to the file, if the data is empty, then it writes the fields provided fields to the file
    """
    ensure_db_dir(root_path)
    file_path = get_correspondence_db_path(root_path)
    if len(data_list) == 0:
        with open(file_path, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)

            writer.writeheader()
        return

    first_row = data_list[0]
    fields = list(first_row.keys())

    with open(file_path, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)

        writer.writeheader()
        writer.writerows(data_list)
