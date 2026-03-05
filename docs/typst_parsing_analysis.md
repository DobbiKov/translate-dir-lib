# Typst Parsing Analysis: Text vs Placeholder Segmentation

## Background

This library translates documents by splitting content into `('text', ...)` and `('placeholder', ...)` segments. Text segments are sent to the LLM for translation; placeholders are preserved verbatim. This report analyses how that segmentation works in LaTeX and MyST, and what is possible for Typst.

---

## How Text vs Placeholder Is Marked

### Segment Types

Both existing parsers produce `list[tuple[str, str]]` where each tuple is `(type, content)` with types:

- **`'text'`** — human-readable content that should be translated
- **`'placeholder'`** — syntax/markup that must be preserved verbatim
- **`'math'`** — math blocks (treated as untranslatable by the translator)

---

### LaTeX (`xml_manipulator_mod/latex.py`)

Uses **`pylatexenc`** to walk a proper AST.

**Key rules:**

| Node type | Segment type |
|-----------|-------------|
| `LatexCharsNode` (non-empty, non-whitespace) | `'text'` |
| `LatexCharsNode` (whitespace only) | `'placeholder'` |
| `LatexMacroNode` in `placeholder_commands` (`\ref`, `\cite`, `\frac`, …) | `'placeholder'` (whole macro) |
| Other macros | `'placeholder'` for command, **recurse** into args |
| Math environments | `'placeholder'` unless arg of `math_text_macros` (`\text{}`, `\mathrm{}`, …) |
| Verbatim environments (`verbatim`, `lstlisting`, …) | `'placeholder'` (whole block) |
| `LatexCommentNode` | `% ` → `'placeholder'`, comment text → `'text'` |

Two configuration sets drive the logic:
- `placeholder_commands` — always a placeholder, never recurse into
- `math_text_macros` — inside math mode, recurse into argument to find translatable text

Pre-processing extracts `\verb|...|` and custom pipe-delimited commands before AST walking, then restores them after.

---

### MyST (`xml_manipulator_mod/myst.py`)

Uses **`myst-parser`** / **`markdown-it`** token stream. Each token handler decides the segment type:

| Token type | Segment type |
|-----------|-------------|
| `"text"` | `('text', content)` |
| `"heading_open"`, `"em_open"`, `"strong_open"`, `"paragraph_close"`, etc. | `('placeholder', markup)` |
| `"math_inline"`, `"math_block"`, `"amsmath"` | `('math', ...)` |
| `"fence"` / `"colon_fence"` with `{code-block}`, `{eval-rst}` | `('placeholder', ...)` |
| `"fence"` with `{note}`, `{warning}`, admonitions, etc. | Recurse into content for text |
| `"myst_role"`, `"code_inline"`, `"html_block"` | `('placeholder', ...)` |
| `"myst_line_comment"` | `% ` → placeholder, comment text → `'text'` |

---

## Typst: What Is Possible

### Language Structure

Typst has three clearly separated modes that interleave in documents:

- **Markup mode** — prose and document structure (headings, emphasis, lists)
- **Code mode** — scripting (variables, functions, loops, conditionals)
- **Math mode** — mathematical expressions

This separation maps directly onto the `text`/`placeholder` distinction.

### Target Segmentation

| Typst construct | Segment type |
|----------------|-------------|
| Markup plain text | `'text'` |
| Heading content (`= Title`) | `'text'` (recurse) |
| Emphasis (`_text_`), strong (`*text*`) content | `'text'` (recurse) |
| List item content | `'text'` (recurse) |
| Raw inline (`` `code` ``) | `'placeholder'` |
| Raw block (` ```lang ... ``` `) | `'placeholder'` |
| Math expressions (`$ ... $`) | `'math'` |
| `text(...)` inside math | `'text'` (recurse, analogous to `\text{}`) |
| Labels (`<label>`), references (`@ref`) | `'placeholder'` |
| Code blocks `{ ... }` | `'placeholder'` |
| Function calls, `let`, `for`, `if`, `show`, `set` | `'placeholder'` |
| Comments `// ...` and `/* ... */` | `'placeholder'` for syntax, `'text'` for comment body |

---

## Available Parsing Libraries

### Option 1: `tree-sitter` + `tree-sitter-language-pack` ✅ Recommended

**`tree-sitter-language-pack`** bundles a Typst grammar (from [uben0/tree-sitter-typst](https://github.com/uben0/tree-sitter-typst)) and is installable today with no extra build steps.

```bash
pip install tree-sitter tree-sitter-language-pack
```

```python
from tree_sitter_language_pack import get_parser

parser = get_parser("typst")
tree = parser.parse(bytes(source, "utf8"))
root = tree.root_node

def walk(node):
    if node.type == "text":
        yield ("text", node.text.decode())
    elif node.type in ("raw_span", "raw_blck", "label", "ref",
                        "math", "code", "block"):
        yield ("placeholder", node.text.decode())
    elif node.type in ("emph", "strong", "heading",
                        "list_item", "enum_item", "term_item", "content"):
        # Emit surrounding syntax as placeholder, recurse into children for text
        for child in node.children:
            yield from walk(child)
    else:
        yield ("placeholder", node.text.decode())
```

**Key node types:**

| Node type | Description |
|-----------|-------------|
| `text` | Plain markup text — primary source of `'text'` segments |
| `emph` | `_emphasized_` content |
| `strong` | `*bold*` content |
| `heading` | `= Heading` |
| `raw_span` | Inline raw `` `code` `` |
| `raw_blck` | Raw block ` ```...``` ` |
| `math` | Math expression `$...$` |
| `label` | `<label>` |
| `ref` | `@reference` |
| `code` / `block` | Code expressions |
| `let`, `for`, `branch`, `import` | Code mode constructs |

Tree-sitter gives a **Concrete Syntax Tree** (CST) with source byte offsets, so reconstruction of the original document from segments is lossless — the same guarantee `pylatexenc` provides for LaTeX.

---

### Option 2: `typst-syntax` Rust crate (via subprocess/FFI)

The official [typst-syntax](https://crates.io/crates/typst-syntax) crate is the ground-truth parser — it is what Typst itself uses internally. It exposes rich AST types: `Text`, `Emph`, `Strong`, `Heading`, `Raw`, `Math`, `CodeBlock`, `FuncCall`, `SetRule`, `ShowRule`, etc.

**Pros:** Perfect language parity, handles every edge case correctly.
**Cons:** No Python bindings exist yet. Would require either:
- A small Rust CLI that parses and outputs JSON, called as a subprocess
- PyO3 bindings (significant effort)

---

### Option 3: Regex / Manual Parser

Typst markup is simpler than LaTeX — there is no arbitrary macro redefinition. A regex/state-machine approach could cover most practical markup cases. Similar to how `_extract_verb_commands` pre-processes LaTeX before AST walking.

**Pros:** Zero dependencies, full control.
**Cons:** Fragile for nested structures, will fail on complex code-in-markup interleaving.

---

## Key Differences from LaTeX/MyST to Plan For

1. **No fixed macro dictionary.** Typst functions are first-class and user-definable. Heuristic: any `funcname(content: [...])` call → check if argument is a content block and recurse for text. Known text-in-math functions: `text()`, `upright()`, `bold()`, `italic()`.

2. **Three modes interleave.** Code blocks can appear inline in markup (`#let x = 1`), and content blocks appear in code (`[markup here]`). Tree-sitter handles this naturally through its grammar rules.

3. **Raw blocks are always placeholders.** Both `` `inline` `` and ` ```block``` ` → `'placeholder'`, analogous to `\verb` and `verbatim` in LaTeX.

4. **`text()` in math.** Analogous to `\text{}` in LaTeX — the argument should be recursed into to produce `'text'` segments, not treated as a monolithic placeholder.

5. **Comments are `//` and `/* */`.** Unlike LaTeX's `%` comments, but the same pattern applies: syntax → placeholder, comment body → text.

---

## Recommended Implementation Path

1. Install `tree-sitter` and `tree-sitter-language-pack`
2. Create `src/trans_lib/xml_manipulator_mod/typst.py` mirroring `latex.py` / `myst.py`
3. Walk the CST recursively: `text` nodes → `'text'`; structural wrappers (`emph`, `strong`, `heading`) → emit delimiter nodes as `'placeholder'` and recurse into content children; code/math/raw → `'placeholder'`
4. Handle `text()` calls inside math analogously to `math_text_macros` in the LaTeX parser
5. Add `DocumentType.Typst` and `ChunkType.Typst` to `enums.py`
6. Create a `typst_file_translator.py` and `typst_chunker.py` modelled on the LaTeX equivalents

---

## References

- [frozolotl/tree-sitter-typst](https://github.com/frozolotl/tree-sitter-typst) — correctness-focused grammar
- [uben0/tree-sitter-typst](https://github.com/uben0/tree-sitter-typst) — grammar bundled in tree-sitter-language-pack
- [tree-sitter-language-pack · PyPI](https://pypi.org/project/tree-sitter-language-pack/)
- [typst-syntax crate docs](https://docs.rs/typst-syntax/latest/typst_syntax/ast/index.html)
- [py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter)
- [Typst documentation](https://typst.app/docs/)
