"""MyST/Markdown source splitter.

parse_myst(source) → Chunk
    Splits MyST source into ('text', ...) and ('placeholder', ...) segments.

    'text'        — translatable content, sent to the translator
    'placeholder' — MyST/Markdown syntax, preserved verbatim
"""

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.amsmath import amsmath_plugin
from mdit_py_plugins.colon_fence import colon_fence_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.myst_role import myst_role_plugin
from mdit_py_plugins.myst_blocks import myst_block_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.field_list import fieldlist_plugin
from mdit_py_plugins.attrs import attrs_plugin, attrs_block_plugin
from mdit_py_plugins.substitution import substitution_plugin
from typing import TypeAlias

Chunk: TypeAlias = list[tuple[str, str]]


# ---------------------------------------------------------------------------
# Parser singleton
# ---------------------------------------------------------------------------

def _make_parser() -> MarkdownIt:
    return (
        MarkdownIt("commonmark", {"sourceMap": True, "typographer": True, "html": True})
        .use(dollarmath_plugin, allow_labels=True, allow_space=True, allow_digits=True, double_inline=True)
        .use(amsmath_plugin)
        .use(colon_fence_plugin)
        .use(front_matter_plugin)
        .use(myst_role_plugin)
        .use(myst_block_plugin)
        .use(footnote_plugin)
        .use(deflist_plugin)
        .use(fieldlist_plugin)
        .use(attrs_plugin)
        .use(attrs_block_plugin)
        .use(substitution_plugin)
    )


_parser = _make_parser()


# ---------------------------------------------------------------------------
# Directive classification
# ---------------------------------------------------------------------------

# Directives whose info/title after the type name is translatable text
_DIRECTIVES_TRANSLATABLE_TITLE = {
    "{admonition}", "{attention}", "{caution}", "{danger}", "{error}",
    "{hint}", "{important}", "{note}", "{seealso}", "{tip}", "{warning}",
    "{versionadded}", "{versionchanged}", "{deprecated}",
    "{aside}", "{sidebar}", "{topic}", "{dropdown}",
    "{tab-set}", "{toctree}", "{table}", "{list-table}",
    "{todo}", "{TODO}", "{eval-rst}", "{math}", "{amsmath}",
}

# Directives whose body is MyST and should be parsed recursively
_DIRECTIVES_RECURSIVE_BODY = {
    "{admonition}", "{attention}", "{caution}", "{danger}", "{error}",
    "{hint}", "{important}", "{note}", "{seealso}", "{tip}", "{warning}",
    "{versionadded}", "{versionchanged}", "{deprecated}",
    "{aside}", "{sidebar}", "{topic}", "{dropdown}",
    "{tab-set}", "{toctree}", "{table}", "{list-table}",
    "{todo}", "{TODO}",
    "{figure}", "{image}", "{iframe}", "{embed}", "{include}", "{literalinclude}",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opening_token(node: SyntaxTreeNode):
    return node.nester_tokens.opening if node.nester_tokens else node.token


def _find_inline(node: SyntaxTreeNode) -> SyntaxTreeNode | None:
    return next((c for c in node.children if c.type == "inline"), None)


def _src(node: SyntaxTreeNode, lines: list[str]) -> Chunk:
    """Return exact source lines for a node as a single placeholder."""
    if node.map:
        start, end = node.map
        return [('placeholder', ''.join(lines[start:end]))]
    return []


# ---------------------------------------------------------------------------
# Inline rendering
# ---------------------------------------------------------------------------

def _render_inline(node: SyntaxTreeNode, out: Chunk, softbreak_indent: str = '') -> None:
    """Recursively render an inline (or inline container) node."""
    for child in node.children:
        _render_inline_node(child, out, softbreak_indent)


def _render_inline_node(node: SyntaxTreeNode, out: Chunk, softbreak_indent: str = '') -> None:
    match node.type:
        case "inline":
            _render_inline(node, out, softbreak_indent)

        case "text":
            out.append(('text', node.content))

        case "softbreak":
            out.append(('placeholder', '\n' + softbreak_indent))

        case "hardbreak":
            out.append(('placeholder', '\\\n' + softbreak_indent))

        case "code_inline":
            out.append(('placeholder', f'`{node.content}`'))

        case "html_inline":
            out.append(('placeholder', node.content))

        case "math_inline":
            out.append(('placeholder', '$' + node.content + '$'))

        case "math_inline_double":
            out.append(('placeholder', '$$' + node.content + '$$'))

        case "em":
            tok = _opening_token(node)
            markup = tok.markup if tok else '*'
            out.append(('placeholder', markup))
            for child in node.children:
                _render_inline_node(child, out, softbreak_indent)
            out.append(('placeholder', markup))

        case "strong":
            tok = _opening_token(node)
            markup = tok.markup if tok else '**'
            out.append(('placeholder', markup))
            for child in node.children:
                _render_inline_node(child, out, softbreak_indent)
            out.append(('placeholder', markup))

        case "link":
            tok = _opening_token(node)
            href = tok.attrs.get('href', '') if tok and tok.attrs else ''
            title = tok.attrs.get('title', '') if tok and tok.attrs else ''
            out.append(('placeholder', '['))
            for child in node.children:
                _render_inline_node(child, out, softbreak_indent)
            suffix = f']({href} "{title}")' if title else f']({href})'
            out.append(('placeholder', suffix))

        case "image":
            tok = _opening_token(node)
            src = tok.attrs.get('src', '') if tok and tok.attrs else ''
            title = tok.attrs.get('title', '') if tok and tok.attrs else ''
            out.append(('placeholder', '!['))
            for child in node.children:
                _render_inline_node(child, out, softbreak_indent)
            suffix = f']({src} "{title}")' if title else f']({src})'
            out.append(('placeholder', suffix))

        case "myst_role":
            name = node.meta.get('name', '') if node.meta else ''
            out.append(('placeholder', f'{{{name}}}`{node.content}`'))

        case "footnote_ref":
            label = node.meta.get('label', '') if node.meta else ''
            out.append(('placeholder', f'[^{label}]'))

        case "substitution_inline":
            out.append(('placeholder', '{{' + node.content + '}}'))

        case "attrs_inline":
            pass  # attribute metadata, no output

        case _:
            out.append(('placeholder', node.content or ''))


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

def _get_align(node: SyntaxTreeNode) -> str | None:
    tok = _opening_token(node)
    if tok and tok.attrs:
        style = tok.attrs.get('style', '')
        if 'right' in style:
            return 'right'
        if 'center' in style:
            return 'center'
        if 'left' in style:
            return 'left'
    return None


def _align_marker(align: str | None) -> str:
    return {'left': ':---', 'center': ':---:', 'right': '---:'}.get(align or '', '---')


def _render_table(node: SyntaxTreeNode, out: Chunk) -> None:
    thead = next((c for c in node.children if c.type == "thead"), None)
    tbody = next((c for c in node.children if c.type == "tbody"), None)

    if thead:
        header_row = next((c for c in thead.children if c.type == "tr"), None)
        if header_row:
            out.append(('placeholder', '|'))
            aligns = []
            for th in header_row.children:
                if th.type != "th":
                    continue
                inline = _find_inline(th)
                if inline:
                    _render_inline(inline, out)
                aligns.append(_get_align(th))
                out.append(('placeholder', '|'))
            out.append(('placeholder', '\n|'))
            for align in aligns:
                out.append(('placeholder', _align_marker(align) + '|'))
            out.append(('placeholder', '\n'))

    if tbody:
        for tr in tbody.children:
            if tr.type != "tr":
                continue
            out.append(('placeholder', '|'))
            for td in tr.children:
                if td.type != "td":
                    continue
                inline = _find_inline(td)
                if inline:
                    _render_inline(inline, out)
                out.append(('placeholder', '|'))
            out.append(('placeholder', '\n'))


# ---------------------------------------------------------------------------
# Deflist rendering
# ---------------------------------------------------------------------------

def _render_deflist(node: SyntaxTreeNode, out: Chunk) -> None:
    for child in node.children:
        if child.type == "dt":
            inline = _find_inline(child)
            if inline:
                _render_inline(inline, out)
            out.append(('placeholder', '\n'))
        elif child.type == "dd":
            out.append(('placeholder', ':   '))
            for subchild in child.children:
                if subchild.type == "paragraph":
                    inline = _find_inline(subchild)
                    if inline:
                        _render_inline(inline, out)
            out.append(('placeholder', '\n'))
    out.append(('placeholder', '\n'))


# ---------------------------------------------------------------------------
# Field list rendering
# ---------------------------------------------------------------------------

def _render_field_list(node: SyntaxTreeNode, out: Chunk) -> None:
    children = node.children
    i = 0
    while i < len(children):
        child = children[i]
        if child.type == "fieldlist_name":
            inline = _find_inline(child)
            name_text = inline.content if inline else ""
            line = f":{name_text}:"
            i += 1
            if i < len(children) and children[i].type == "fieldlist_body":
                body = children[i]
                para = next((c for c in body.children if c.type == "paragraph"), None)
                if para:
                    inline_body = _find_inline(para)
                    body_text = inline_body.content if inline_body else ""
                else:
                    body_text = ""
                line += f" {body_text}"
                i += 1
            out.append(('placeholder', line + '\n'))
        else:
            i += 1
    out.append(('placeholder', '\n'))


# ---------------------------------------------------------------------------
# Fence rendering
# ---------------------------------------------------------------------------

def _render_fence(node: SyntaxTreeNode, lines: list[str], out: Chunk) -> None:
    tok = node.token
    info = tok.info
    content = tok.content  # already ends with '\n' or is empty
    markup = tok.markup

    # Extract directive type from info string
    table_type = ''
    if info and '{' in info:
        end = info.find('}')
        if end != -1:
            table_type = info[:end + 1]
            info = info[end + 1:]

    # For non-directive and opaque directive fences: use source lines verbatim
    if table_type not in _DIRECTIVES_TRANSLATABLE_TITLE and table_type not in _DIRECTIVES_RECURSIVE_BODY:
        out.extend(_src(node, lines))
        return

    # Directive fence: extract indentation prefix from source
    indent_prefix = ''
    if node.map and lines:
        first_line = lines[node.map[0]]
        indent_prefix = first_line[:len(first_line) - len(first_line.lstrip())]

    # Opening line: [indent][markup][table_type][info]
    out.append(('placeholder', indent_prefix + markup + table_type))
    if info and table_type in _DIRECTIVES_TRANSLATABLE_TITLE:
        out.append(('text', info))
    else:
        out.append(('placeholder', info))
    out.append(('placeholder', '\n'))

    # Body: recurse for directives with MyST content
    if table_type in _DIRECTIVES_RECURSIVE_BODY and content:
        inner = parse_myst(content)
        out.extend(inner)

    # Closing line: [indent][markup]
    out.append(('placeholder', indent_prefix + markup + '\n'))


# ---------------------------------------------------------------------------
# List rendering
# ---------------------------------------------------------------------------

def _render_list(node: SyntaxTreeNode, lines: list[str], out: Chunk, level: int = 0) -> None:
    items = [c for c in node.children if c.type == "list_item"]
    for i, item in enumerate(items):
        _render_list_item(item, lines, out, level)
        if i < len(items) - 1:
            out.append(('placeholder', '\n'))
    if level == 0:
        out.append(('placeholder', '\n'))


def _render_list_item(item: SyntaxTreeNode, lines: list[str], out: Chunk, level: int) -> None:
    tok = _opening_token(item)
    prefix = '\t' * level

    # Determine marker from token
    if item.parent and item.parent.type == "ordered_list":
        info = tok.info if tok and tok.info else "1"
        marker = f"{info}. "
    else:
        marker = "- "

    continuation_indent = prefix + ' ' * len(marker)
    out.append(('placeholder', prefix + marker))

    for child in item.children:
        if child.type == "paragraph":
            # Render inline content (no trailing '\n' — list handles separators)
            inline = _find_inline(child)
            if inline:
                _render_inline(inline, out, softbreak_indent=continuation_indent)
        elif child.type in ("bullet_list", "ordered_list"):
            out.append(('placeholder', '\n'))
            _render_list(child, lines, out, level + 1)
        elif child.type in ("fence", "colon_fence"):
            out.append(('placeholder', '\n'))
            _render_fence(child, lines, out)
        else:
            _render_block(child, lines, out)


# ---------------------------------------------------------------------------
# Footnote reference rendering
# ---------------------------------------------------------------------------

def _render_footnote_reference(node: SyntaxTreeNode, lines: list[str], out: Chunk) -> None:
    label = node.meta.get('label', '') if node.meta else ''
    out.extend([
        ('placeholder', '['),
        ('placeholder', f'^{label}'),
        ('placeholder', ']'),
        ('placeholder', ': '),
    ])
    for child in node.children:
        _render_block(child, lines, out)


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------

def _render_block(node: SyntaxTreeNode, lines: list[str], out: Chunk) -> None:
    match node.type:
        case "paragraph":
            inline = _find_inline(node)
            if inline:
                _render_inline(inline, out)
            out.append(('placeholder', '\n'))

        case "heading":
            tok = _opening_token(node)
            markup = tok.markup if tok else '#'
            if markup == '=':
                markup = '#'
            elif markup == '-':
                markup = '##'
            out.append(('placeholder', markup + ' '))
            inline = _find_inline(node)
            if inline:
                _render_inline(inline, out)
            out.append(('placeholder', '\n'))

        case "fence" | "colon_fence":
            _render_fence(node, lines, out)

        case "bullet_list" | "ordered_list":
            _render_list(node, lines, out)

        case "table":
            _render_table(node, out)

        case "blockquote":
            out.append(('placeholder', '> '))
            for child in node.children:
                _render_block(child, lines, out)

        case "hr":
            out.extend(_src(node, lines))

        case "html_block" | "html_inline":
            out.append(('placeholder', node.content))

        case "math_block":
            out.append(('placeholder', '$$' + node.content + '$$'))

        case "amsmath":
            out.append(('placeholder', node.content))

        case "myst_target":
            out.append(('placeholder', f'({node.content})=\n'))

        case "myst_line_comment":
            out.append(('placeholder', '% '))
            out.append(('text', node.content))
            out.append(('placeholder', '\n'))

        case "myst_block_break":
            out.append(('placeholder', f'+++ {node.content}\n'))

        case "front_matter":
            out.append(('placeholder', f'---\n{node.content}\n---\n'))

        case "footnote_reference":
            _render_footnote_reference(node, lines, out)

        case "field_list":
            _render_field_list(node, out)

        case "dl":
            _render_deflist(node, out)

        case "substitution_block":
            out.append(('placeholder', '{{' + node.content + '}}'))

        case "attrs_block":
            out.extend(_src(node, lines))

        case _:
            out.extend(_src(node, lines))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_myst(source: str) -> Chunk:
    """
    Split MyST markdown source into ('text'|'placeholder', content) segments.

    'text' segments contain translatable content.
    'placeholder' segments contain MyST syntax that must be preserved verbatim.
    """
    lines = source.splitlines(keepends=True)
    tokens = _parser.parse(source)
    tree = SyntaxTreeNode(tokens)

    out: Chunk = []
    children = tree.children
    for i, child in enumerate(children):
        _render_block(child, lines, out)
        # Preserve blank lines between top-level blocks using source maps
        if i < len(children) - 1:
            nxt = children[i + 1]
            gap_start = child.map[1] if child.map else 0
            gap_end = nxt.map[0] if nxt.map else gap_start
            blanks = gap_end - gap_start
            if blanks > 0:
                out.append(('placeholder', '\n' * blanks))
    return out
