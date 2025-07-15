
from pathlib import Path

from loguru import logger
from trans_lib.doc_translator_mod.myst_chunker import split_myst_document_into_chunks
from trans_lib.enums import ChunkType, DocumentType, Language
from trans_lib.helpers import calculate_checksum
from trans_lib.translator_retrieval import Meta, build_default_translator
from trans_lib.vocab_list import VocabList


def _format_metadata_block(metadata: dict[str, str]) -> str:
    """Formats a dictionary into a LaTeX comment metadata block."""
    lines = ["<!-- --- CHUNK_METADATA_START ---"]
    for key, value in metadata.items():
        lines.append(f"% {key}: {value}")
    lines.append(" --- CHUNK_METADATA_END --- -->")
    return "\n".join(lines) + "\n" # Add a newline at the end for separation


def compile_myst_cells(cells: list[dict]) -> str:
    """Takes a list of MyST cells and compiles a final file contents and returns it in string format."""
    res = ""
    for cell in cells:
        temp_res = _format_metadata_block(cell["metadata"])
        temp_res += cell["source"]
        res += temp_res
    return res

def get_myst_cells(source_file_path: Path) -> list[dict]:
    """Get's a path to the file and returns it in the cells format"""
    source_text = ""
    with open(source_file_path, "r") as f:
        source_text = f.read()

    chunk_list = split_myst_document_into_chunks(source_text)

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

async def translate_file_async(root_path: Path, source_file_path: Path, source_language: Language, target_file_path: Path, target_language: Language, vocab_list: VocabList | None) -> None:
    """Handler for a latex file-to-file translation"""
    cells = get_myst_cells(source_file_path)

    for i in range(len(cells)):
        cell = cells[i]
        cells[i] = await translate_chunk_async(root_path, cell, source_language, target_language, vocab_list)

    with open(target_file_path, "w") as f:
        f.write(compile_myst_cells(cells))


async def translate_chunk_async(root_path: Path, cell: dict, source_language: Language, target_language: Language, vocab_list: VocabList | None) -> dict:
   """Handler for a latex chunk translation"""
   src_txt = cell["source"] 
   logger.debug(f"{src_txt}")
   checksum = calculate_checksum(src_txt)

   cell["metadata"]["needs_review"] = "True"
   cell["metadata"]["src_checksum"] = checksum

   cell["source"] = await translate_any_chunk_async(root_path, src_txt, source_language, target_language, vocab_list)

   return cell

async def translate_any_chunk_async(root_path: Path, contents: str, source_language: Language, target_language: Language, vocab_list: VocabList | None) -> str:
    tr = build_default_translator(root_path)
    meta = Meta(contents, source_language, target_language, DocumentType.Markdown, ChunkType.Myst, vocab_list)
    return await tr.translate_or_fetch(meta)
