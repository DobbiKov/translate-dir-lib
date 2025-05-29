from asyncio import sleep
import os
from pathlib import Path

from trans_lib.translator_retrieval import translate_chunk_or_retrieve_from_db_async
from ..enums import Language
from ..helpers import read_string_from_file
from ..translator import _prepare_prompt_for_language, _ask_gemini_model, translate_chunk_with_prompt
import jupytext
import hashlib
from loguru import logger

async def translate_notebook_async(root_path: Path, source_file_path: Path, source_language: Language, target_file_path: Path, target_language: Language) -> None:
    nb = jupytext.read(source_file_path)
    # TODO: read target file
    for i in range(len(nb.cells)):
        nb.cells[i] = await translate_jupyter_cell_async(root_path, nb.cells[i], source_language, target_language) 
    jupytext.write(nb, target_file_path)

async def translate_jupyter_cell_async(root_path: Path, cell: dict, source_language: Language, target_language: Language) -> dict:
    src_txt = cell["source"]
    cell_type = cell["cell_type"]
    checksum = hashlib.md5(src_txt.encode()).hexdigest()
    # TODO: verify that current checksum isn't in the database

    cell["metadata"].setdefault("tags", [])
    cell["metadata"]["tags"].append("needs_review")
    cell["metadata"]["src_checksum"] = checksum
    await sleep(5)
    match cell_type:
        case "code":
            cell["source"] = await translate_code_cell_async(root_path, src_txt, source_language, target_language)
        case _:
            cell["source"] = await translate_markdown_cell_async(root_path, src_txt, source_language, target_language)

    return cell

MARKDOWN_PROMPT_PATH = Path("/Users/dobbikov/Desktop/stage/prompts/doc_specific/markdown_prompt")
CODE_PROMPT_PATH = Path("/Users/dobbikov/Desktop/stage/prompts/doc_specific/code_prompt")

def get_markdown_prompt_text() -> str:
    """Reads the markdown prompt text from the configured path."""
    try:
        return read_string_from_file(MARKDOWN_PROMPT_PATH)
    except Exception as e:
        print(f"Warning: Could not load default prompt from {MARKDOWN_PROMPT_PATH}: {e}. Using a fallback.")
        # Fallback prompt to avoid complete failure if file is missing
        return "Translate the following document to [TARGET_LANGUAGE]. Maintain the original structure and formatting as much as possible. Only output the translated document text inside <output> tags.\nDocument text:\n"

def get_code_prompt_text() -> str:
    """Reads the code prompt text from the configured path."""
    try:
        return read_string_from_file(CODE_PROMPT_PATH)
    except Exception as e:
        print(f"Warning: Could not load default prompt from {CODE_PROMPT_PATH}: {e}. Using a fallback.")
        # Fallback prompt to avoid complete failure if file is missing
        return "Translate the following document to [TARGET_LANGUAGE]. Maintain the original structure and formatting as much as possible. Only output the translated document text inside <output> tags.\nDocument text:\n"

async def translate_markdown_cell_async(root_path: Path, contents: str, source_language: Language, target_language: Language) -> str:
    prompt = get_markdown_prompt_text()
    return await translate_chunk_or_retrieve_from_db_async(root_path, contents, source_language, target_language, prompt)


async def translate_code_cell_async(root_path: Path, contents: str, source_language: Language, target_language: Language) -> str:
    prompt = get_code_prompt_text()
    return await translate_chunk_or_retrieve_from_db_async(root_path, contents, source_language, target_language, prompt)


