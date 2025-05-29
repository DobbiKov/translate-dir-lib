from trans_lib.trans_db import add_contents_to_db
from pathlib import Path
from trans_lib.enums import Language
from trans_lib.translator import def_prompt_template, translate_chunk_with_prompt, _prepare_prompt_for_language


async def translate_chunk_or_retrieve_from_db_async(root_path: Path, text_chunk: str, source_language: Language, target_language: Language, prompt_placeholder: str = def_prompt_template) -> str:
    """
    Verifies if provided chunk of text exists in the translation database. If
    it exists, looks for the translation in the DB, if it exists, returns the
    translation, if it doesn't translates it using an LLM.
    """
    prompt_for_lang = _prepare_prompt_for_language(prompt_placeholder, target_language)

    # TODO: verify that it doesn't exist in the db
    translated = await translate_chunk_with_prompt(prompt_for_lang, text_chunk)

    # TODO: save to translation db
    add_contents_to_db(root_path, text_chunk, source_language) 
    add_contents_to_db(root_path, translated, target_language) 
    return translated
