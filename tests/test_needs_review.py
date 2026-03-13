"""Tests verifying needs_review tag is set only when LLM is called,
not on cache hits, and is preserved from an existing translated file."""

import asyncio
from pathlib import Path

import pytest

from trans_lib.enums import Language
from trans_lib.doc_translator_mod import (
    myst_file_translator,
    latex_file_translator,
    typst_file_translator,
    notebook_file_translator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeTranslator:
    """Fake ChunkTranslator that returns a fixed (text, from_cache) pair."""

    def __init__(self, result: str, from_cache: bool):
        self._result = result
        self._from_cache = from_cache

    async def translate_or_fetch(self, meta):
        return self._result, self._from_cache


def _make_build_translator(result: str, from_cache: bool):
    def _build(root_path, caller, reasoning_caller=None):
        return FakeTranslator(result, from_cache)
    return _build


SRC = Language.ENGLISH
TGT = Language.FRENCH
REL = "docs/example.md"
TRANSLATED = "Texte traduit."


# ---------------------------------------------------------------------------
# MyST
# ---------------------------------------------------------------------------

class TestMystNeedsReview:
    def _run(self, monkeypatch, from_cache: bool, existing_meta=None):
        monkeypatch.setattr(
            myst_file_translator,
            "build_translator_with_model",
            _make_build_translator(TRANSLATED, from_cache),
        )
        cell = {"metadata": {}, "source": "Some text."}
        return asyncio.run(
            myst_file_translator.translate_chunk_async(
                Path("/tmp"), cell, SRC, TGT, REL, None, None,
                existing_meta=existing_meta,
            )
        )

    def test_llm_call_adds_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=False)
        assert cell["metadata"].get("needs_review") == "True"

    def test_cache_hit_does_not_add_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=True, existing_meta={})
        assert "needs_review" not in cell["metadata"]

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        from trans_lib.helpers import calculate_checksum
        src = "Some text."
        checksum = calculate_checksum(src)
        existing_meta = {checksum: {"needs_review": "True", "src_checksum": checksum}}
        cell = self._run(monkeypatch, from_cache=True, existing_meta=existing_meta)
        assert cell["metadata"].get("needs_review") == "True"


# ---------------------------------------------------------------------------
# LaTeX
# ---------------------------------------------------------------------------

class TestLatexNeedsReview:
    def _run(self, monkeypatch, from_cache: bool, existing_meta=None):
        monkeypatch.setattr(
            latex_file_translator,
            "build_translator_with_model",
            _make_build_translator(TRANSLATED, from_cache),
        )
        cell = {"metadata": {}, "source": "Some text."}
        return asyncio.run(
            latex_file_translator.translate_chunk_async(
                Path("/tmp"), cell, SRC, TGT, REL, None, None,
                existing_meta=existing_meta,
            )
        )

    def test_llm_call_adds_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=False)
        assert cell["metadata"].get("needs_review") == "True"

    def test_cache_hit_does_not_add_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=True, existing_meta={})
        assert "needs_review" not in cell["metadata"]

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        from trans_lib.helpers import calculate_checksum
        src = "Some text."
        checksum = calculate_checksum(src)
        existing_meta = {checksum: {"needs_review": "True", "src_checksum": checksum}}
        cell = self._run(monkeypatch, from_cache=True, existing_meta=existing_meta)
        assert cell["metadata"].get("needs_review") == "True"


# ---------------------------------------------------------------------------
# Typst
# ---------------------------------------------------------------------------

class TestTypstNeedsReview:
    def _run(self, monkeypatch, from_cache: bool, existing_meta=None):
        monkeypatch.setattr(
            typst_file_translator,
            "build_translator_with_model",
            _make_build_translator(TRANSLATED, from_cache),
        )
        cell = {"metadata": {}, "source": "Some text."}
        return asyncio.run(
            typst_file_translator.translate_chunk_async(
                Path("/tmp"), cell, SRC, TGT, REL, None, None,
                existing_meta=existing_meta,
            )
        )

    def test_llm_call_adds_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=False)
        assert cell["metadata"].get("needs_review") == "True"

    def test_cache_hit_does_not_add_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=True, existing_meta={})
        assert "needs_review" not in cell["metadata"]

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        from trans_lib.helpers import calculate_checksum
        src = "Some text."
        checksum = calculate_checksum(src)
        existing_meta = {checksum: {"needs_review": "True", "src_checksum": checksum}}
        cell = self._run(monkeypatch, from_cache=True, existing_meta=existing_meta)
        assert cell["metadata"].get("needs_review") == "True"


# ---------------------------------------------------------------------------
# Notebook  (needs_review lives in cell["metadata"]["tags"])
# ---------------------------------------------------------------------------

class TestNotebookNeedsReview:
    def _run(self, monkeypatch, from_cache: bool, existing_meta=None):
        monkeypatch.setattr(
            notebook_file_translator,
            "build_translator_with_model",
            _make_build_translator(TRANSLATED, from_cache),
        )
        cell = {"cell_type": "markdown", "source": "Some text.", "metadata": {"tags": []}}
        return asyncio.run(
            notebook_file_translator.translate_jupyter_cell_async(
                Path("/tmp"), cell, SRC, TGT, None, None, REL,
                existing_meta=existing_meta,
            )
        )

    def test_llm_call_adds_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=False)
        assert "needs_review" in cell["metadata"]["tags"]

    def test_cache_hit_does_not_add_needs_review(self, monkeypatch, tmp_path):
        cell = self._run(monkeypatch, from_cache=True, existing_meta={})
        assert "needs_review" not in cell["metadata"]["tags"]

    def test_cache_hit_preserves_needs_review_from_existing_target(self, monkeypatch, tmp_path):
        from trans_lib.helpers import calculate_checksum
        src = "Some text."
        checksum = calculate_checksum(src)
        existing_meta = {checksum: {"tags": ["needs_review"], "src_checksum": checksum}}
        cell = self._run(monkeypatch, from_cache=True, existing_meta=existing_meta)
        assert "needs_review" in cell["metadata"]["tags"]
