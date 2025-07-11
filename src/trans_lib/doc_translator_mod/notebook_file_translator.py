from ..prompts import prompt_jupyter_code, prompt_jupyter_md 
from pathlib import Path

from trans_lib.translator_retrieval import CodeMeta, Meta, build_default_translator
from trans_lib.vocab_list import VocabList
from ..enums import ChunkType, DocumentType, Language
from ..helpers import calculate_checksum
import jupytext

async def translate_notebook_async(root_path: Path, source_file_path: Path, source_language: Language, target_file_path: Path, target_language: Language, vocab_list: VocabList | None) -> None:
    nb = jupytext.read(source_file_path)
    # TODO: read target file
    for i in range(len(nb.cells)):
        nb.cells[i] = await translate_jupyter_cell_async(root_path, nb.cells[i], source_language, target_language, vocab_list) 
    jupytext.write(nb, target_file_path)

async def translate_jupyter_cell_async(root_path: Path, cell: dict, source_language: Language, target_language: Language, vocab_list: VocabList | None) -> dict:
    src_txt = cell["source"]
    cell_type = cell["cell_type"]
    checksum = calculate_checksum(src_txt)

    cell["metadata"].setdefault("tags", [])
    cell["metadata"]["tags"].append("needs_review")
    cell["metadata"]["src_checksum"] = checksum
    match cell_type:
        case "code":
            cell["source"] = await translate_code_cell_async(root_path, src_txt, source_language, target_language, vocab_list)
        case _:
            cell["source"] = await translate_markdown_cell_async(root_path, src_txt, source_language, target_language, vocab_list)

    return cell


def get_markdown_prompt_text() -> str:
    """Returns the default prompt for translating markdown prompt of the jupyter notebook"""
    return prompt_jupyter_md

def get_code_prompt_text() -> str:
    """Returns the default prompt for translating code part of the jupyter notebook"""
    return prompt_jupyter_code

async def translate_markdown_cell_async(root_path: Path, contents: str, source_language: Language, target_language: Language, vocab_list: VocabList | None) -> str:
    tr = build_default_translator(root_path)
    meta = Meta(contents, source_language, target_language, DocumentType.JupyterNotebook, ChunkType.Myst, vocab_list)
    return await tr.translate_or_fetch(meta)


async def translate_code_cell_async(root_path: Path, contents: str, source_language: Language, target_language: Language, vocab_list: VocabList | None) -> str:
    tr = build_default_translator(root_path)
    meta = CodeMeta(contents, source_language, target_language, DocumentType.JupyterNotebook, ChunkType.Code, vocab_list, "python") # TODO: the language must be set accordingly to the cell
    return await tr.translate_or_fetch(meta)


