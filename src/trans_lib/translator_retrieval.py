from loguru import logger
from trans_lib.helpers import calculate_checksum
from trans_lib.trans_db import add_contents_to_db, find_correspondent_checksum, read_contents_by_checksum_with_lang, set_checksum_pair_to_correspondence_db
from pathlib import Path
from trans_lib.enums import DocumentType, Language
from trans_lib.translator import def_prompt_template, translate_chunk_with_prompt, _prepare_prompt_for_language, _prepare_prompt_for_vocab_list, _prepare_prompt_for_content_type
from trans_lib.vocab_list import VocabList
from trans_lib.xml_manipulator_mod.mod import chunk_to_xml, reconstruct_from_xml
from trans_lib.prompts import xml_translation_prompt

def is_whitespace(text: str) -> bool:
    return not text or text.isspace()

async def translate_chunk_or_retrieve_from_db_async(root_path: Path, text_chunk: str, source_language: Language, target_language: Language, prompt_placeholder: str = def_prompt_template, vocab_list: VocabList | None = None, doc_type: DocumentType = DocumentType.Other) -> str:
    """
    Verifies if provided chunk of text exists in the translation database. If
    it exists, looks for the translation in the DB, if it exists, returns the
    translation, if it doesn't translates it using an LLM.
    """

    src_checksum = calculate_checksum(text_chunk)
    tgt_checksum = find_correspondent_checksum(root_path, src_checksum, source_language, target_language)
    if src_checksum == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855":
        logger.info(f"src: {src_checksum} | {tgt_checksum}")
    translated = "" 
    found_in_db = False

    if tgt_checksum is not None: # if we found existing pair, try to extract translated contents
        logger.debug("Found the translation in the database")
        found_in_db = True
        translated = read_contents_by_checksum_with_lang(root_path, tgt_checksum, target_language)
    elif is_whitespace(text_chunk):
        logger.debug("It is a whitespace, add to db but no need to translate")
        translated = text_chunk
        src_checksum = add_contents_to_db(root_path, text_chunk, source_language) 
        tgt_checksum = add_contents_to_db(root_path, translated, target_language) 
        set_checksum_pair_to_correspondence_db(root_path, src_checksum, source_language, tgt_checksum, target_language)

    if ( translated == "" and not found_in_db) or translated is None: # if the translation is empty, then we haven't found it and we should translate it
        translated = ""
        match doc_type:
            case DocumentType.LaTeX:
                xml_text = chunk_to_xml(text_chunk, doc_type)
                prompt_for_lang = xml_translation_prompt
                prompt_for_lang = _prepare_prompt_for_language(prompt_for_lang, target_language, source_language)
                prompt_for_lang = _prepare_prompt_for_content_type(prompt_for_lang, "LaTeX")
                xml_translated = await translate_chunk_with_prompt(prompt_for_lang, xml_text, True)
                translated = reconstruct_from_xml(xml_translated)
            case _:
                logger.debug("Didn't find the translation in the database, translate using LLM")
                prompt_for_lang = _prepare_prompt_for_language(prompt_placeholder, target_language)
                prompt_for_lang = _prepare_prompt_for_vocab_list(prompt_for_lang, vocab_list)
                translated = await translate_chunk_with_prompt(prompt_for_lang, text_chunk)

        # always be here
        src_checksum = add_contents_to_db(root_path, text_chunk, source_language) 
        tgt_checksum = add_contents_to_db(root_path, translated, target_language) 
        set_checksum_pair_to_correspondence_db(root_path, src_checksum, source_language, tgt_checksum, target_language)
    return translated
