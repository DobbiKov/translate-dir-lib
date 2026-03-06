from __future__ import annotations

from pathlib import Path

from loguru import logger
from unified_model_caller.core import LLMCaller

from trans_lib.doc_translator_mod.typst_chunker import split_typst_document_into_chunks
from trans_lib.enums import ChunkType, DocumentType, Language
from trans_lib.errors import ChunkTranslationFailed
from trans_lib.helpers import calculate_checksum
from trans_lib.translator_retrieval import Meta, build_translator_with_model
from trans_lib.vocab_list import VocabList


def _format_metadata_block(metadata: dict[str, str]) -> str:
    lines = ["// --- CHUNK_METADATA_START ---"]
    for key, value in metadata.items():
        lines.append(f"// {key}: {value}")
    lines.append("// --- CHUNK_METADATA_END ---")
    return "\n".join(lines) + "\n"


def compile_typst_cells(cells: list[dict]) -> str:
    result = ""
    for cell in cells:
        result += _format_metadata_block(cell["metadata"])
        result += cell["source"]
    return result


def get_typst_cells(source_file_path: Path) -> list[dict]:
    with open(source_file_path, "r", encoding="utf-8") as file:
        source = file.read()

    chunk_list = split_typst_document_into_chunks(source)
    cells = []
    for chunk in chunk_list:
        cells.append({"metadata": {}, "source": chunk["content"]})
    return cells


async def translate_file_async(
    root_path: Path,
    source_file_path: Path,
    source_language: Language,
    target_file_path: Path,
    target_language: Language,
    relative_path: str,
    vocab_list: VocabList | None,
    llm_caller: LLMCaller,
    reasoning_caller: LLMCaller | None = None,
) -> None:
    cells = get_typst_cells(source_file_path)

    for index in range(len(cells)):
        cell = cells[index]
        cells[index] = await translate_chunk_async(
            root_path,
            cell,
            source_language,
            target_language,
            relative_path,
            vocab_list,
            llm_caller,
            reasoning_caller=reasoning_caller,
        )

    with open(target_file_path, "w", encoding="utf-8") as file:
        file.write(compile_typst_cells(cells))


async def translate_chunk_async(
    root_path: Path,
    cell: dict,
    source_language: Language,
    target_language: Language,
    relative_path: str,
    vocab_list: VocabList | None,
    llm_caller: LLMCaller,
    reasoning_caller: LLMCaller | None = None,
) -> dict:
    src_txt = cell["source"]
    logger.debug(f"{src_txt}")
    checksum = calculate_checksum(src_txt)

    cell["metadata"]["needs_review"] = "True"
    cell["metadata"]["src_checksum"] = checksum

    try:
        cell["source"] = await translate_any_chunk_async(
            root_path,
            src_txt,
            source_language,
            target_language,
            relative_path,
            vocab_list,
            llm_caller,
            reasoning_caller=reasoning_caller,
        )
    except ChunkTranslationFailed as exc:
        cell["metadata"]["not-translated-due-to-exception"] = "True"
        cell["source"] = exc.chunk

    return cell


async def translate_any_chunk_async(
    root_path: Path,
    contents: str,
    source_language: Language,
    target_language: Language,
    relative_path: str,
    vocab_list: VocabList | None,
    llm_caller: LLMCaller,
    reasoning_caller: LLMCaller | None = None,
) -> str:
    tr = build_translator_with_model(root_path, llm_caller, reasoning_caller)
    meta = Meta(
        contents,
        source_language,
        target_language,
        DocumentType.Typst,
        ChunkType.Typst,
        vocab_list,
        relative_path,
    )
    return await tr.translate_or_fetch(meta)
