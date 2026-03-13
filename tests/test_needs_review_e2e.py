"""End-to-end tests verifying that needs_review is correctly embedded in
(or absent from) the actual translated output files written to disk."""

import asyncio
from pathlib import Path

import jupytext
import nbformat
import pytest

from trans_lib.enums import Language
from trans_lib.helpers import calculate_checksum
from trans_lib.doc_translator_mod import (
    myst_file_translator,
    latex_file_translator,
    typst_file_translator,
    notebook_file_translator,
)
from trans_lib.doc_translator_mod.myst_file_translator import (
    compile_myst_cells,
    get_myst_cells,
    read_chunks_with_metadata_from_myst,
)
from trans_lib.doc_translator_mod.latex_file_translator import (
    compile_latex_cells,
    get_latex_cells,
)
from trans_lib.doc_translator_mod.latex_chunker import read_chunks_with_metadata_from_latex
from trans_lib.doc_translator_mod.typst_file_translator import (
    compile_typst_cells,
    get_typst_cells,
)
from trans_lib.doc_translator_mod.typst_chunker import read_chunks_with_metadata_from_typst


SRC = Language.ENGLISH
TGT = Language.FRENCH
TRANSLATED = "Texte traduit."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeTranslator:
    def __init__(self, result: str, from_cache: bool):
        self._result = result
        self._from_cache = from_cache

    async def translate_or_fetch(self, meta):
        return self._result, self._from_cache


def _patch(monkeypatch, module, from_cache: bool):
    monkeypatch.setattr(
        module,
        "build_translator_with_model",
        lambda root, caller, reasoning_caller=None: FakeTranslator(TRANSLATED, from_cache),
    )


# ---------------------------------------------------------------------------
# MyST
# ---------------------------------------------------------------------------

MYST_SOURCE = "Hello world."


class TestMystFileNeedsReview:
    def _src(self, tmp_path: Path) -> Path:
        p = tmp_path / "source.md"
        p.write_text(MYST_SOURCE, encoding="utf-8")
        return p

    def _translate(self, monkeypatch, src: Path, tgt: Path, from_cache: bool):
        _patch(monkeypatch, myst_file_translator, from_cache)
        asyncio.run(myst_file_translator.translate_file_async(
            src.parent, src, SRC, tgt, TGT, "source.md", None, None,
        ))

    def _read(self, tgt: Path) -> list[dict]:
        return read_chunks_with_metadata_from_myst(tgt)

    def test_llm_call_writes_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.md"
        self._translate(monkeypatch, src, tgt, from_cache=False)
        chunks = self._read(tgt)
        assert any(c.get("needs_review") == "True" for c in chunks)

    def test_cache_hit_does_not_write_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.md"
        self._translate(monkeypatch, src, tgt, from_cache=True)
        chunks = self._read(tgt)
        assert all(c.get("needs_review") is None for c in chunks)

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.md"

        # Write a pre-existing target file that has needs_review
        src_cells = get_myst_cells(src)
        checksum = calculate_checksum(src_cells[0]["source"])
        tgt.write_text(compile_myst_cells([{
            "metadata": {"src_checksum": checksum, "needs_review": "True"},
            "source": "Old translation.",
        }]), encoding="utf-8")

        self._translate(monkeypatch, src, tgt, from_cache=True)
        chunks = self._read(tgt)
        assert any(c.get("needs_review") == "True" for c in chunks)


# ---------------------------------------------------------------------------
# LaTeX
# ---------------------------------------------------------------------------

LATEX_SOURCE = r"\documentclass{article}\begin{document}Hello world.\end{document}"


class TestLatexFileNeedsReview:
    def _src(self, tmp_path: Path) -> Path:
        p = tmp_path / "source.tex"
        p.write_text(LATEX_SOURCE, encoding="utf-8")
        return p

    def _translate(self, monkeypatch, src: Path, tgt: Path, from_cache: bool):
        _patch(monkeypatch, latex_file_translator, from_cache)
        asyncio.run(latex_file_translator.translate_file_async(
            src.parent, src, SRC, tgt, TGT, "source.tex", None, None,
        ))

    def _read(self, tgt: Path) -> list[dict]:
        return read_chunks_with_metadata_from_latex(tgt)

    def test_llm_call_writes_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.tex"
        self._translate(monkeypatch, src, tgt, from_cache=False)
        chunks = self._read(tgt)
        assert any(c.get("needs_review") == "True" for c in chunks)

    def test_cache_hit_does_not_write_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.tex"
        self._translate(monkeypatch, src, tgt, from_cache=True)
        chunks = self._read(tgt)
        assert all(c.get("needs_review") is None for c in chunks)

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.tex"

        src_cells = get_latex_cells(src)
        # Find the content chunk (not preamble/macro declarations)
        content_cells = [c for c in src_cells if c["source"].strip() == "Hello world."]
        assert content_cells, "expected a content chunk with 'Hello world.'"
        checksum = calculate_checksum(content_cells[0]["source"])
        tgt.write_text(compile_latex_cells([{
            "metadata": {"src_checksum": checksum, "needs_review": "True"},
            "source": "Old translation.",
        }]), encoding="utf-8")

        self._translate(monkeypatch, src, tgt, from_cache=True)
        chunks = self._read(tgt)
        assert any(c.get("needs_review") == "True" for c in chunks)


# ---------------------------------------------------------------------------
# Typst
# ---------------------------------------------------------------------------

TYPST_SOURCE = "Hello world."


class TestTypstFileNeedsReview:
    def _src(self, tmp_path: Path) -> Path:
        p = tmp_path / "source.typ"
        p.write_text(TYPST_SOURCE, encoding="utf-8")
        return p

    def _translate(self, monkeypatch, src: Path, tgt: Path, from_cache: bool):
        _patch(monkeypatch, typst_file_translator, from_cache)
        asyncio.run(typst_file_translator.translate_file_async(
            src.parent, src, SRC, tgt, TGT, "source.typ", None, None,
        ))

    def _read(self, tgt: Path) -> list[dict]:
        return read_chunks_with_metadata_from_typst(tgt)

    def test_llm_call_writes_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.typ"
        self._translate(monkeypatch, src, tgt, from_cache=False)
        chunks = self._read(tgt)
        assert any(c.get("needs_review") == "True" for c in chunks)

    def test_cache_hit_does_not_write_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.typ"
        self._translate(monkeypatch, src, tgt, from_cache=True)
        chunks = self._read(tgt)
        assert all(c.get("needs_review") is None for c in chunks)

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.typ"

        src_cells = get_typst_cells(src)
        checksum = calculate_checksum(src_cells[0]["source"])
        tgt.write_text(compile_typst_cells([{
            "metadata": {"src_checksum": checksum, "needs_review": "True"},
            "source": "Old translation.",
        }]), encoding="utf-8")

        self._translate(monkeypatch, src, tgt, from_cache=True)
        chunks = self._read(tgt)
        assert any(c.get("needs_review") == "True" for c in chunks)


# ---------------------------------------------------------------------------
# Notebook
# ---------------------------------------------------------------------------

class TestNotebookFileNeedsReview:
    def _src(self, tmp_path: Path) -> Path:
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("Hello world.")]
        p = tmp_path / "source.ipynb"
        nbformat.write(nb, p)
        return p

    def _translate(self, monkeypatch, src: Path, tgt: Path, from_cache: bool):
        _patch(monkeypatch, notebook_file_translator, from_cache)
        asyncio.run(notebook_file_translator.translate_notebook_async(
            src.parent, src, SRC, tgt, TGT, None, None, "source.ipynb",
        ))

    def _read_tags(self, tgt: Path) -> list[list[str]]:
        nb = jupytext.read(tgt)
        return [cell.get("metadata", {}).get("tags", []) for cell in nb.cells]

    def test_llm_call_writes_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.ipynb"
        self._translate(monkeypatch, src, tgt, from_cache=False)
        all_tags = self._read_tags(tgt)
        assert any("needs_review" in tags for tags in all_tags)

    def test_cache_hit_does_not_write_needs_review_to_file(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.ipynb"
        self._translate(monkeypatch, src, tgt, from_cache=True)
        all_tags = self._read_tags(tgt)
        assert all("needs_review" not in tags for tags in all_tags)

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        src = self._src(tmp_path)
        tgt = tmp_path / "target.ipynb"

        # Write a pre-existing target notebook with needs_review tag
        src_nb = jupytext.read(src)
        src_text = src_nb.cells[0]["source"]
        checksum = calculate_checksum(src_text)

        pre_nb = nbformat.v4.new_notebook()
        pre_nb.cells = [nbformat.v4.new_markdown_cell("Old translation.")]
        pre_nb.cells[0]["metadata"] = {"src_checksum": checksum, "tags": ["needs_review"]}
        nbformat.write(pre_nb, tgt)

        self._translate(monkeypatch, src, tgt, from_cache=True)
        all_tags = self._read_tags(tgt)
        assert any("needs_review" in tags for tags in all_tags)
