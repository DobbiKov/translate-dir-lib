from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from typst_syntax import SyntaxKind, parse_source

from trans_lib.xml_manipulator_mod.xml import create_translation_xml

_MATH_TEXT_FUNCTIONS = {"text", "upright", "bold", "italic"}

_STRUCTURAL_CONTAINER_KINDS = {
    SyntaxKind.MARKUP,
    SyntaxKind.CONTENT_BLOCK,
    SyntaxKind.STRONG,
    SyntaxKind.EMPH,
    SyntaxKind.HEADING,
    SyntaxKind.LIST_ITEM,
    SyntaxKind.ENUM_ITEM,
    SyntaxKind.TERM_ITEM,
}

_PLACEHOLDER_ONLY_KINDS = {
    SyntaxKind.RAW,
    SyntaxKind.LABEL,
    SyntaxKind.REF,
    SyntaxKind.LINK,
    SyntaxKind.CODE_BLOCK,
    SyntaxKind.CODE,
    SyntaxKind.MODULE_IMPORT,
    SyntaxKind.MODULE_INCLUDE,
    SyntaxKind.HASH,
    SyntaxKind.LET,
    SyntaxKind.SET,
    SyntaxKind.SHOW,
    SyntaxKind.IMPORT,
    SyntaxKind.INCLUDE,
}

_COMMAND_KINDS_WITH_CONTENT = {
    SyntaxKind.FUNC_CALL,
    SyntaxKind.LET_BINDING,
    SyntaxKind.SET_RULE,
    SyntaxKind.SHOW_RULE,
}


def parse_typst(source: str) -> list[tuple[str, str]]:
    syntax_source = parse_source(source)
    root = syntax_source.root()
    return [segment for segment in _walk_typst_node(root) if segment[1] != ""]


def _walk_typst_node(node: Any) -> Iterable[tuple[str, str]]:
    kind = node.kind()

    if kind == SyntaxKind.TEXT:
        yield ("text", node.text())
        return

    if kind == SyntaxKind.SPACE:
        yield ("placeholder", node.text())
        return

    if kind == SyntaxKind.PARBREAK:
        yield ("placeholder", node.text())
        return

    if kind in _STRUCTURAL_CONTAINER_KINDS:
        for child in node.children():
            yield from _walk_typst_node(child)
        return

    if kind in (SyntaxKind.MATH, SyntaxKind.EQUATION):
        if _contains_translatable_math_call(node):
            yield from _walk_math_node_with_text_calls(node)
            return
        yield ("math", node.full_text())
        return

    if kind in _COMMAND_KINDS_WITH_CONTENT:
        if _contains_content_block(node):
            for child in node.children():
                yield from _walk_typst_node(child)
            return
        yield ("placeholder", node.full_text())
        return

    if kind in _PLACEHOLDER_ONLY_KINDS:
        yield ("placeholder", node.full_text())
        return

    if kind == SyntaxKind.LINE_COMMENT:
        yield from _split_line_comment(node.full_text())
        return

    if kind == SyntaxKind.BLOCK_COMMENT:
        yield from _split_block_comment(node.full_text())
        return

    children = list(node.children())
    if children:
        for child in children:
            yield from _walk_typst_node(child)
        return

    yield ("placeholder", node.full_text())


def _contains_translatable_math_call(node: Any) -> bool:
    if node.kind() == SyntaxKind.FUNC_CALL and _is_math_text_function_call(node):
        return True
    return any(_contains_translatable_math_call(child) for child in node.children())


def _contains_content_block(node: Any) -> bool:
    if node.kind() == SyntaxKind.CONTENT_BLOCK:
        return True
    return any(_contains_content_block(child) for child in node.children())


def _is_math_text_function_call(node: Any) -> bool:
    for child in node.children():
        if child.kind() in (SyntaxKind.IDENT, SyntaxKind.MATH_IDENT):
            return child.text() in _MATH_TEXT_FUNCTIONS
    return False


def _walk_math_node_with_text_calls(node: Any) -> Iterable[tuple[str, str]]:
    kind = node.kind()

    if kind == SyntaxKind.FUNC_CALL and _is_math_text_function_call(node):
        yield from _walk_translatable_math_function_call(node)
        return

    if kind in (SyntaxKind.EQUATION, SyntaxKind.MATH, SyntaxKind.MATH_DELIMITED):
        for child in node.children():
            yield from _walk_math_node_with_text_calls(child)
        return

    yield ("placeholder", node.full_text())


def _walk_translatable_math_function_call(node: Any) -> Iterable[tuple[str, str]]:
    for child in node.children():
        if child.kind() == SyntaxKind.ARGS:
            yield from _walk_translatable_math_args(child)
        else:
            yield ("placeholder", child.full_text())


def _walk_translatable_math_args(node: Any) -> Iterable[tuple[str, str]]:
    for child in node.children():
        kind = child.kind()
        if kind == SyntaxKind.STR:
            yield from _split_string_literal(child.full_text())
        elif kind in (SyntaxKind.CONTENT_BLOCK, SyntaxKind.MARKUP):
            for grandchild in child.children():
                yield from _walk_typst_node(grandchild)
        else:
            yield ("placeholder", child.full_text())


def _split_string_literal(content: str) -> Iterable[tuple[str, str]]:
    if len(content) >= 2 and content[0] == content[-1] and content[0] in {'"', "'"}:
        yield ("placeholder", content[0])
        middle = content[1:-1]
        if middle:
            yield ("text", middle)
        yield ("placeholder", content[-1])
        return
    yield ("placeholder", content)


def _split_line_comment(content: str) -> Iterable[tuple[str, str]]:
    if not content.startswith("//"):
        yield ("placeholder", content)
        return

    if content.startswith("// "):
        yield ("placeholder", "// ")
        body = content[3:]
    else:
        yield ("placeholder", "//")
        body = content[2:]

    if body:
        yield ("text", body)


def _split_block_comment(content: str) -> Iterable[tuple[str, str]]:
    if not (content.startswith("/*") and content.endswith("*/")):
        yield ("placeholder", content)
        return

    middle = content[2:-2]
    opener = "/*"
    closer = "*/"

    if middle.startswith(" "):
        opener += " "
        middle = middle[1:]
    if middle.endswith(" "):
        closer = " " + closer
        middle = middle[:-1]

    yield ("placeholder", opener)
    if middle:
        yield ("text", middle)
    yield ("placeholder", closer)


def typst_to_xml(source: str) -> tuple[str, dict, bool]:
    segments = parse_typst(source)
    segments = [
        ("placeholder", content) if segment_type == "math" else (segment_type, content)
        for segment_type, content in segments
    ]
    return create_translation_xml(segments)
