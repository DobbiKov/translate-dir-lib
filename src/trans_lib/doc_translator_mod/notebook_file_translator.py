from unified_model_caller.core import LLMCaller
from ..prompts import prompt_jupyter_code, prompt_jupyter_md 
from pathlib import Path

from trans_lib.translator_retrieval import CodeMeta, Meta, build_translator_with_model
from trans_lib.errors import ChunkTranslationFailed
from trans_lib.vocab_list import VocabList
from ..enums import ChunkType, DocumentType, Language
from ..helpers import calculate_checksum
import jupytext

async def translate_notebook_async(
    root_path: Path,
    source_file_path: Path,
    source_language: Language,
    target_file_path: Path,
    target_language: Language,
    vocab_list: VocabList | None,
    llm_caller: LLMCaller,
    relative_path: str,
    project_description: str = "",
) -> None:
    nb = jupytext.read(source_file_path)
    # TODO: read target file
    for i in range(len(nb.cells)):
        nb.cells[i] = await translate_jupyter_cell_async(root_path, nb.cells[i], source_language, target_language, vocab_list, llm_caller, relative_path, project_description)
    jupytext.write(nb, target_file_path)

async def translate_jupyter_cell_async(
    root_path: Path,
    cell: dict,
    source_language: Language,
    target_language: Language,
    vocab_list: VocabList | None,
    llm_caller: LLMCaller,
    relative_path: str,
    project_description: str = "",
) -> dict:
    src_txt = cell["source"]
    cell_type = cell["cell_type"]
    checksum = calculate_checksum(src_txt)

    cell.setdefault("metadata", {})
    cell["metadata"].setdefault("tags", [])
    cell["metadata"]["tags"].append("needs_review")
    cell["metadata"]["src_checksum"] = checksum

    try:
        if cell_type == "code":
            cell["source"] = await translate_code_cell_async(root_path, src_txt, source_language, target_language, vocab_list, llm_caller, relative_path, project_description)
        else:
            cell["source"] = await translate_markdown_cell_async(root_path, src_txt, source_language, target_language, vocab_list, llm_caller, relative_path, project_description)
    except ChunkTranslationFailed as exc:
        tags = cell["metadata"].setdefault("tags", [])
        if "not-translated-due-to-exception" not in tags:
            tags.append("not-translated-due-to-exception")
        cell["metadata"]["not-translated-due-to-exception"] = "True"
        cell["source"] = exc.chunk

    return cell


def get_markdown_prompt_text() -> str:
    """Returns the default prompt for translating markdown prompt of the jupyter notebook"""
    return prompt_jupyter_md

def get_code_prompt_text() -> str:
    """Returns the default prompt for translating code part of the jupyter notebook"""
    return prompt_jupyter_code

async def translate_markdown_cell_async(
    root_path: Path,
    contents: str,
    source_language: Language,
    target_language: Language,
    vocab_list: VocabList | None,
    llm_caller: LLMCaller,
    relative_path: str,
    project_description: str = "",
) -> str:
    tr = build_translator_with_model(root_path, llm_caller)
    meta = Meta(
        chunk=contents,
        src_lang=source_language,
        tgt_lang=target_language,
        doc_type=DocumentType.JupyterNotebook,
        chunk_type=ChunkType.Myst,
        vocab=vocab_list,
        rel_path=relative_path,
        project_description=project_description,
    )
    return await tr.translate_or_fetch(meta)


async def translate_code_cell_async(
    root_path: Path,
    contents: str,
    source_language: Language,
    target_language: Language,
    vocab_list: VocabList | None,
    llm_caller: LLMCaller,
    relative_path: str,
    project_description: str = "",
) -> str:
    tr = build_translator_with_model(root_path, llm_caller)
    meta = CodeMeta(
        chunk=contents,
        src_lang=source_language,
        tgt_lang=target_language,
        doc_type=DocumentType.JupyterNotebook,
        chunk_type=ChunkType.Code,
        vocab=vocab_list,
        rel_path=relative_path,
        prog_lang="python", # TODO: the language must be set accordingly to the cell
        project_description=project_description,
    )
    return await tr.translate_or_fetch(meta)
