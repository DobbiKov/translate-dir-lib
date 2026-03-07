from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from typst_syntax import SyntaxKind, parse_source

MAX_INLINE_CHUNK_LENGTH = 600

_BLOCK_LEVEL_KINDS = {
    SyntaxKind.HEADING,
    SyntaxKind.RAW,
    SyntaxKind.EQUATION,
    SyntaxKind.CODE_BLOCK,
    SyntaxKind.SHOW_RULE,
    SyntaxKind.SET_RULE,
    SyntaxKind.LET_BINDING,
    SyntaxKind.MODULE_IMPORT,
    SyntaxKind.MODULE_INCLUDE,
}

_INLINE_ACCUMULATION_KINDS = {
    SyntaxKind.TEXT,
    SyntaxKind.STRONG,
    SyntaxKind.EMPH,
    SyntaxKind.SPACE,
    SyntaxKind.MATH,
    SyntaxKind.MATH_DELIMITED,
}

_HASH_PREFIXABLE_KINDS = {
    SyntaxKind.SHOW_RULE,
    SyntaxKind.SET_RULE,
    SyntaxKind.LET_BINDING,
    SyntaxKind.MODULE_IMPORT,
    SyntaxKind.MODULE_INCLUDE,
    SyntaxKind.CODE_BLOCK,
}


def _slice_bytes(source_text: str, start_byte: int, end_byte: int) -> str:
    raw = source_text.encode("utf-8")[start_byte:end_byte]
    return raw.decode("utf-8")


def _node_range(source: Any, node: Any) -> tuple[int, int]:
    result = source.range(node.span)
    if result is None:
        return 0, 0
    return result


def _simple_chunk(
    chunk_type: str,
    start_byte: int,
    end_byte: int,
    source_text: str,
) -> dict[str, Any]:
    return {
        "type": chunk_type,
        "byte_range": (start_byte, end_byte),
        "content": _slice_bytes(source_text, start_byte, end_byte),
    }


def _typst_to_simple_chunks(source_text: str) -> list[dict[str, Any]]:
    parsed = parse_source(source_text)
    root = parsed.root()
    root_children = list(root.children())

    chunks: list[dict[str, Any]] = []
    inline_start_byte: int | None = None
    inline_end_byte: int | None = None
    inline_content = ""

    def flush_inline_buffer() -> None:
        nonlocal inline_start_byte, inline_end_byte, inline_content
        if inline_start_byte is None or inline_end_byte is None:
            return
        if inline_content:
            chunks.append(
                {
                    "type": "INLINE",
                    "byte_range": (inline_start_byte, inline_end_byte),
                    "content": inline_content,
                }
            )
        inline_start_byte = None
        inline_end_byte = None
        inline_content = ""

    def append_inline(node: Any) -> None:
        nonlocal inline_start_byte, inline_end_byte, inline_content
        start_byte, end_byte = _node_range(parsed, node)
        piece = _slice_bytes(source_text, start_byte, end_byte)

        if inline_start_byte is None:
            inline_start_byte = start_byte
            inline_end_byte = end_byte
        else:
            inline_end_byte = end_byte

        inline_content += piece
        if len(inline_content) >= MAX_INLINE_CHUNK_LENGTH:
            flush_inline_buffer()

    idx = 0
    while idx < len(root_children):
        node = root_children[idx]
        kind = node.kind()

        if (
            kind == SyntaxKind.HASH
            and idx + 1 < len(root_children)
            and root_children[idx + 1].kind() == SyntaxKind.FUNC_CALL
        ):
            append_inline(node)
            append_inline(root_children[idx + 1])
            idx += 2
            continue

        if (
            kind == SyntaxKind.HASH
            and idx + 1 < len(root_children)
            and root_children[idx + 1].kind() in _HASH_PREFIXABLE_KINDS
        ):
            flush_inline_buffer()
            next_node = root_children[idx + 1]
            start_byte, _ = _node_range(parsed, node)
            _, end_byte = _node_range(parsed, next_node)
            chunks.append(
                _simple_chunk(
                    next_node.kind().name.upper().replace(" ", "_"),
                    start_byte,
                    end_byte,
                    source_text,
                )
            )
            idx += 2
            continue

        if kind in _BLOCK_LEVEL_KINDS:
            flush_inline_buffer()
            start_byte, end_byte = _node_range(parsed, node)
            chunks.append(
                _simple_chunk(
                    kind.name.upper().replace(" ", "_"),
                    start_byte,
                    end_byte,
                    source_text,
                )
            )
            idx += 1
            continue

        if kind in _INLINE_ACCUMULATION_KINDS:
            append_inline(node)
            idx += 1
            continue

        if kind == SyntaxKind.PARBREAK:
            append_inline(node)
            flush_inline_buffer()
            idx += 1
            continue

        flush_inline_buffer()
        start_byte, end_byte = _node_range(parsed, node)
        chunks.append(
            _simple_chunk(
                kind.name.upper().replace(" ", "_"),
                start_byte,
                end_byte,
                source_text,
            )
        )
        idx += 1

    flush_inline_buffer()
    return chunks


def _simple_chunks_to_section_chunks(simple_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = {"elems": [], "content": "", "byte_range": None}
    chunks: list[dict[str, Any]] = []

    for simple_chunk in simple_chunks:
        if simple_chunk["type"] == "HEADING" and current["elems"]:
            chunks.append(current)
            current = {"elems": [], "content": "", "byte_range": None}

        current["elems"].append(simple_chunk)
        current["content"] += simple_chunk["content"]

        if current["byte_range"] is None:
            current["byte_range"] = simple_chunk["byte_range"]
        else:
            start_byte = current["byte_range"][0]
            end_byte = simple_chunk["byte_range"][1]
            current["byte_range"] = (start_byte, end_byte)

    if current["elems"]:
        chunks.append(current)

    return chunks


def _complete_section_chunks(
    section_chunks: list[dict[str, Any]],
    max_chars_num: int = 2000,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for chunk in section_chunks:
        if len(chunk["content"]) > max_chars_num:
            result.extend(chunk["elems"])
            continue

        first_type = chunk["elems"][0]["type"] if chunk["elems"] else "SECTION"
        result.append(
            {
                "type": first_type,
                "byte_range": chunk["byte_range"],
                "content": chunk["content"],
            }
        )

    return result


def split_typst_document_into_chunks(source: str) -> list[dict[str, Any]]:
    simple_chunks = _typst_to_simple_chunks(source)
    section_chunks = _simple_chunks_to_section_chunks(simple_chunks)
    complete_chunks = _complete_section_chunks(section_chunks)

    return [
        {
            "id": f"auto_chunk_{index + 1}",
            "content": chunk["content"],
            "chunk_type": "content",
        }
        for index, chunk in enumerate(complete_chunks)
        if chunk["content"]
    ]


def _parse_metadata_block(block_str: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in block_str.splitlines():
        stripped = line.strip()
        if not stripped.startswith("//"):
            continue
        stripped = stripped[2:].strip()
        if stripped.startswith("--- CHUNK_METADATA_START ---") or stripped.startswith(
            "--- CHUNK_METADATA_END ---"
        ):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def read_chunks_with_metadata_from_typst(filepath: Path) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as file:
        full_content = file.read()

    chunks_data: list[dict] = []
    metadata_pattern = re.compile(
        r"(?s)(// --- CHUNK_METADATA_START ---\n.*?\n// --- CHUNK_METADATA_END ---\n)"
    )

    parts = metadata_pattern.split(full_content)
    current_chunk_content = ""
    current_metadata: dict[str, str] = {}

    start_index = 0
    if not parts[0].strip() and len(parts) > 1:
        current_metadata = _parse_metadata_block(parts[1])
        start_index = 2

    for index in range(start_index, len(parts)):
        part = parts[index]
        if index % 2 == 1:
            if current_chunk_content.strip():
                chunks_data.append({"source": current_chunk_content.strip(), **current_metadata})
            current_metadata = _parse_metadata_block(part)
            current_chunk_content = ""
        else:
            current_chunk_content += part

    if current_chunk_content.strip():
        chunks_data.append({"source": current_chunk_content.strip(), **current_metadata})

    return chunks_data
