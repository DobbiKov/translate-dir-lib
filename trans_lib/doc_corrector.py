
from pathlib import Path

import jupytext
from loguru import logger

from trans_lib.enums import DocumentType, Language
from trans_lib.errors import CorrectingTranslationError
from trans_lib.helpers import analyze_document_type, calculate_checksum
from trans_lib.trans_db import do_translation_correspond_to_source
from trans_lib.translator_corrector import correct_chunk_translation

def correct_jupyter_notebook_translation(root_path: Path, tgt_path: Path, tgt_lang: Language, src_lang: Language) -> None:
    nb = jupytext.read(tgt_path)
    for i in range(len(nb.cells)):
        correct_jupyter_cell(root_path, nb.cells[i], tgt_lang, src_lang)

def correct_jupyter_cell(root_path: Path, cell: dict, target_language: Language, source_language: Language) -> None:
    tgt_txt = cell["source"]
    metadata = cell.get("metadata")
    if metadata is None:
        return
    src_checksum = metadata.get("src_checksum")
    if src_checksum is None:
        return
    logger.debug("found metadata src_checksum")

    if do_translation_correspond_to_source(root_path, src_checksum, source_language, tgt_txt, target_language):
        return
    correct_chunk_translation(root_path, src_checksum, source_language, tgt_txt, target_language)
    
def correct_file_translation(root_path: Path, translated_file_path: Path, translate_lang: Language, source_language: Language) -> None:
    doc_type = analyze_document_type(translated_file_path)
    logger.trace(doc_type)
    try:
        if doc_type == DocumentType.Markdown or doc_type == DocumentType.JupyterNotebook:
            correct_jupyter_notebook_translation(root_path, translated_file_path, translate_lang, source_language)
        else:
            # TODO: proper chunking
            # TODO: DB saving
            raise NotImplementedError
    except IOError as e:
        raise CorrectingTranslationError(f"Failed to write corrected file {translated_file_path}: {e}", original_exception=e)
