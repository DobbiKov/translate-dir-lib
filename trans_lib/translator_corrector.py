

from pathlib import Path
from trans_lib.enums import Language
from trans_lib.errors import ChecksumNotFoundError
from trans_lib.helpers import calculate_checksum
from trans_lib.trans_db import add_contents_to_db, read_contents_by_checksum_with_lang, set_checksum_pair_to_correspondence_db


def correct_chunk_translation(root_path: Path, src_checksum: str, src_lang: Language, new_translation: str, tgt_lang: Language) -> None:
    """
    Corrects the translation pair by changing the target language translation result to the new given translation
    """
    _src_contents = read_contents_by_checksum_with_lang(root_path, src_checksum, src_lang)
    if _src_contents is None:
        raise ChecksumNotFoundError

    tgt_checksum = add_contents_to_db(root_path, new_translation, tgt_lang)

    set_checksum_pair_to_correspondence_db(root_path, src_checksum, src_lang, tgt_checksum, tgt_lang)
    
