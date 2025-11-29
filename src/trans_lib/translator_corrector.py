

from pathlib import Path

from loguru import logger
from trans_lib.enums import Language
from trans_lib.errors import ChecksumNotFoundError
from trans_lib.helpers import calculate_checksum
from trans_lib.translation_store.translation_store import TranslationStoreCsv



def correct_chunk_translation(root_path: Path, src_checksum: str, src_lang: Language, new_translation: str, tgt_lang: Language, relative_path: str) -> None:
    """
    Corrects the translation pair (in the correspondence database) by changing the target language translation result to the new given translation
    """
    store = TranslationStoreCsv(root_path)
    _src_contents = store.get_contents_by_checksum(src_checksum, src_lang, relative_path)
    if _src_contents is None:
        raise ChecksumNotFoundError(f"Given source checksum ({src_checksum}) isn't found in the database")

    if store.do_translation_correspond_to_source(src_checksum, src_lang, new_translation, tgt_lang, relative_path):
        return 

    tgt_checksum = calculate_checksum(new_translation)
    logger.debug(f"Correcting: src({src_checksum}) and tgt({tgt_checksum})")
    store.persist_pair(src_checksum, tgt_checksum, src_lang, tgt_lang, _src_contents, new_translation, relative_path)
    
