from loguru import logger
from trans_lib.helpers import calculate_checksum
from trans_lib.trans_db import add_contents_to_db, find_correspondent_checksum, read_contents_by_checksum_with_lang, set_checksum_pair_to_correspondence_db
from pathlib import Path
from trans_lib.enums import Language
from trans_lib.translator import def_prompt_template, translate_chunk_with_prompt, _prepare_prompt_for_language


async def translate_chunk_or_retrieve_from_db_async(root_path: Path, text_chunk: str, source_language: Language, target_language: Language, prompt_placeholder: str = def_prompt_template) -> str:
    """
    Verifies if provided chunk of text exists in the translation database. If
    it exists, looks for the translation in the DB, if it exists, returns the
    translation, if it doesn't translates it using an LLM.
    """

    # TODO: verify that it doesn't exist in the db
    src_checksum = calculate_checksum(text_chunk)
    tgt_checksum = find_correspondent_checksum(root_path, src_checksum, source_language, target_language)
    translated = "" 
    if tgt_checksum is not None: # if we found existing pair, try to extract translated contents
        logger.debug("Found the translation in the database")
        translated = read_contents_by_checksum_with_lang(root_path, tgt_checksum, target_language)

    if ( translated == "" and text_chunk != "") or translated == None: # if the translation is empty, then we haven't found it and we should translate it
        logger.debug("Didn't find the translation in the database, translate using LLM")
        prompt_for_lang = _prepare_prompt_for_language(prompt_placeholder, target_language)
        translated = await translate_chunk_with_prompt(prompt_for_lang, text_chunk)

        src_checksum = add_contents_to_db(root_path, text_chunk, source_language) 
        tgt_checksum = add_contents_to_db(root_path, translated, target_language) 
        set_checksum_pair_to_correspondence_db(root_path, src_checksum, source_language, tgt_checksum, target_language)
    return translated
