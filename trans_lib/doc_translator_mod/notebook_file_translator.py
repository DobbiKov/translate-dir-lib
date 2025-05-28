from asyncio import sleep
from pathlib import Path
from ..enums import Language
from ..helpers import read_string_from_file
from ..translator import _prepare_prompt_for_language, _ask_gemini_model, translate_chunk_with_prompt
import jupytext
import hashlib
from loguru import logger

async def translate_notebook_async(source_file_path: Path, target_file_path: Path, target_language: Language) -> None:
    nb = jupytext.read(source_file_path)
    for i in range(len(nb.cells)):
        src_txt = nb.cells[i].source
        cell_type = nb.cells[i].cell_type
        checksum = hashlib.md5(src_txt.encode()).hexdigest()
        nb.cells[i].metadata.setdefault("tags", [])
        nb.cells[i].metadata["tags"].append("needs_review")
        nb.cells[i].metadata["checksum"] = checksum
        await sleep(5)
        match cell_type:
            case "code":
                nb.cells[i].source = await translate_code_cell_async(src_txt, target_language)
                nb.cells[i].metadata
            case _:
                nb.cells[i].source = await translate_markdown_cell_async(src_txt, target_language)
    jupytext.write(nb, target_file_path)

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

async def translate_markdown_cell_async(contents: str, target_language: Language) -> str:
    prompt = get_markdown_prompt_text()
    prompt = _prepare_prompt_for_language(prompt, target_language)
    return await translate_chunk_with_prompt(prompt, contents)


async def translate_code_cell_async(contents: str, target_language: Language) -> str:
    prompt = get_code_prompt_text()
    prompt = _prepare_prompt_for_language(prompt, target_language)
    logger.debug(f"prompt: {prompt}")
    return await translate_chunk_with_prompt(prompt, contents)


