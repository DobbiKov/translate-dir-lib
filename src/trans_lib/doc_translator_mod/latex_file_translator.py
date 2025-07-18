from unified_model_caller.core import LLMCaller
from ..prompts import prompt4
from pathlib import Path

from trans_lib.doc_translator_mod.latex_chunker import split_latex_document_into_chunks
from trans_lib.translator_retrieval import Meta, build_translator_with_model
from trans_lib.vocab_list import VocabList
from ..enums import ChunkType, DocumentType, Language
from ..helpers import calculate_checksum
from loguru import logger


def _format_metadata_block(metadata: dict[str, str]) -> str:
    """Formats a dictionary into a LaTeX comment metadata block."""
    lines = ["% --- CHUNK_METADATA_START ---"]
    for key, value in metadata.items():
        lines.append(f"% {key}: {value}")
    lines.append("% --- CHUNK_METADATA_END ---")
    return "\n".join(lines) + "\n" # Add a newline at the end for separation

def compile_latex_cells(cells: list[dict]) -> str:
    """Takes a list of latex cells and compiles a final file contents and returns it in string format."""
    res = ""
    for cell in cells:
        temp_res = _format_metadata_block(cell["metadata"])
        temp_res += cell["source"]
        res += temp_res
    return res

def get_latex_cells(source_file_path: Path) -> list[dict]:
    """Get's a path to the file and returns it in the cells format"""
    latex_document_string = ""
    with open(source_file_path, "r") as f:
        latex_document_string = f.read()

    chunk_list = split_latex_document_into_chunks(latex_document_string)

    cells = []
    # dividing into cells
    for chunk in chunk_list:
        contents = chunk["content"]
        cell = {
                "metadata": {},
                "source": contents
                }
        cells.append(cell)

    return cells

async def translate_file_async(root_path: Path, source_file_path: Path, source_language: Language, target_file_path: Path, target_language: Language, vocab_list: VocabList | None, llm_caller: LLMCaller) -> None:
    """Handler for a latex file-to-file translation"""
    cells = get_latex_cells(source_file_path)

    for i in range(len(cells)):
        cell = cells[i]
        cells[i] = await translate_chunk_async(root_path, cell, source_language, target_language, vocab_list, llm_caller)

    with open(target_file_path, "w") as f:
        f.write(compile_latex_cells(cells))


async def translate_chunk_async(root_path: Path, cell: dict, source_language: Language, target_language: Language, vocab_list: VocabList | None, llm_caller: LLMCaller) -> dict:
   """Handler for a latex chunk translation"""
   src_txt = cell["source"] 
   logger.debug(f"{src_txt}")
   checksum = calculate_checksum(src_txt)

   cell["metadata"]["needs_review"] = "True"
   cell["metadata"]["src_checksum"] = checksum

   cell["source"] = await translate_any_chunk_async(root_path, src_txt, source_language, target_language, vocab_list, llm_caller)

   return cell

def get_latex_prompt_text() -> str:
    """Returns the default prompt for translating LaTeX documents"""
    return prompt4

async def translate_any_chunk_async(root_path: Path, contents: str, source_language: Language, target_language: Language, vocab_list: VocabList | None, llm_caller: LLMCaller) -> str:
    tr = build_translator_with_model(root_path, llm_caller)
    meta = Meta(contents, source_language, target_language, DocumentType.LaTeX, ChunkType.LaTeX, vocab_list)
    return await tr.translate_or_fetch(meta)
