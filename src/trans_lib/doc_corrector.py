
from pathlib import Path

import jupytext
from loguru import logger

from trans_lib.doc_translator_mod.latex_chunker import read_chunks_with_metadata_from_latex
from trans_lib.doc_translator_mod.myst_file_translator import read_chunks_with_metadata_from_myst
from trans_lib.enums import DocumentType, Language
from trans_lib.errors import CorrectingTranslationError
from trans_lib.helpers import analyze_document_type
from trans_lib.translation_store.translation_store import TranslationStoreCsv
from trans_lib.translator_corrector import correct_chunk_translation

def correct_jupyter_notebook_translation(root_path: Path, tgt_path: Path, tgt_lang: Language, src_lang: Language) -> bool:
    nb = jupytext.read(tgt_path)
    res = False
    for i in range(len(nb.cells)):
        res = correct_jupyter_cell(root_path, nb.cells[i], tgt_lang, src_lang) or res 
    return res

def correct_jupyter_cell(root_path: Path, cell: dict, target_language: Language, source_language: Language) -> bool:
    tgt_txt = cell["source"]
    metadata = cell.get("metadata")
    if metadata is None:
        return False
    src_checksum = metadata.get("src_checksum")
    if src_checksum is None:
        return False
    logger.debug("found metadata src_checksum")

    if TranslationStoreCsv(root_path).do_translation_correspond_to_source(root_path, src_checksum, source_language, tgt_txt, target_language):
        return False
    correct_chunk_translation(root_path, src_checksum, source_language, tgt_txt, target_language)
    return True

def correct_latex_cell(root_path: Path, cell: dict, target_language: Language, source_language: Language) -> bool:
    tgt_txt = cell["source"]
    src_checksum = cell["src_checksum"]
    logger.debug("found metadata src_checksum")

    if TranslationStoreCsv(root_path).do_translation_correspond_to_source(root_path, src_checksum, source_language, tgt_txt, target_language):
        return False
    correct_chunk_translation(root_path, src_checksum, source_language, tgt_txt, target_language)
    return True

def correct_myst_cell(root_path: Path, cell: dict, target_language: Language, source_language: Language) -> bool:
    tgt_txt = cell["source"]
    src_checksum = cell["src_checksum"]
    logger.debug("found metadata src_checksum")

    if TranslationStoreCsv(root_path).do_translation_correspond_to_source(root_path, src_checksum, source_language, tgt_txt, target_language):
        return False
    correct_chunk_translation(root_path, src_checksum, source_language, tgt_txt, target_language)
    return True

def correct_latex_document_translation(root_path: Path, tgt_path: Path, tgt_lang: Language, src_lang: Language) -> bool:
   cells = read_chunks_with_metadata_from_latex(tgt_path) 
   res = False
   for i in range(len(cells)):
       res = correct_latex_cell(root_path, cells[i], tgt_lang, src_lang) or res 
   return res

def correct_myst_document_translation(root_path: Path, tgt_path: Path, tgt_lang: Language, src_lang: Language) -> bool:
   cells = read_chunks_with_metadata_from_myst(tgt_path) 
   res = False
   for i in range(len(cells)):
       res = correct_myst_cell(root_path, cells[i], tgt_lang, src_lang) or res 
   return res

def correct_file_translation(root_path: Path, translated_file_path: Path, translate_lang: Language, source_language: Language) -> bool:
    doc_type = analyze_document_type(translated_file_path)
    logger.trace(doc_type)
    try:
        if doc_type == DocumentType.JupyterNotebook:
            return correct_jupyter_notebook_translation(root_path, translated_file_path, translate_lang, source_language)
        elif doc_type == DocumentType.Markdown:
            return correct_myst_document_translation(root_path, translated_file_path, translate_lang, source_language)
        elif doc_type == DocumentType.LaTeX:
            return correct_latex_document_translation(root_path, translated_file_path, translate_lang, source_language)
        else:
            # TODO: proper chunking
            # TODO: DB saving
            raise NotImplementedError
    except IOError as e:
        raise CorrectingTranslationError(f"Failed to write corrected file {translated_file_path}: {e}", original_exception=e)
