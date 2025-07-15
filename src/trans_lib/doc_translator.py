from loguru import logger

from trans_lib.vocab_list import VocabList
from .enums import DocumentType, Language
from .translator import translate_contents_async
from .helpers import read_string_from_file, analyze_document_type
from .errors import TranslationProcessError
from .doc_translator_mod.notebook_file_translator import translate_notebook_async
from pathlib import Path
from .doc_translator_mod import latex_file_translator

async def translate_file_async(source_path: Path, target_language: Language, vocab_list: VocabList | None) -> str:
    """Reads a file, translates its content asynchronously, and returns the translated content."""
    file_contents = read_string_from_file(source_path)
    return await translate_contents_async(file_contents, target_language, 50, vocab_list)


async def translate_file_to_file_async(
    root_path: Path,
    source_path: Path,
    source_language: Language,
    target_path: Path,
    target_language: Language,
    vocab_list: VocabList | None
) -> None:
    """Translates a file and writes the result to another file asynchronously."""
    doc_type = analyze_document_type(source_path)
    logger.trace(doc_type)
    try:
        if doc_type == DocumentType.JupyterNotebook:
            logger.trace("translate jupyter")
            await translate_notebook_async(root_path, source_path, source_language, target_path, target_language, vocab_list)
        elif doc_type == DocumentType.Markdown:
            logger.debug("translate markdown")
            logger.debug("but not implemented yet")
        elif doc_type == DocumentType.LaTeX:
            # logger.trace("translate latex")
            await latex_file_translator.translate_file_async(root_path, source_path, source_language, target_path, target_language, vocab_list)
        else: # any other type
            translated_content = await translate_file_async(source_path, target_language, vocab_list)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(translated_content, encoding="utf-8")
    except IOError as e:
        raise TranslationProcessError(f"Failed to write translated file {target_path}: {e}", original_exception=e)
