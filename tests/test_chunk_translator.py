import asyncio
import sys
import types
from pathlib import Path

import pytest


# Provide lightweight shims for optional dependencies required by unified_model_caller imports.
if "xai_sdk" not in sys.modules:  # pragma: no cover - optional dependency stub
    xai_module = types.ModuleType("xai_sdk")

    class _DummyChat:
        def create(self, *, model, messages):
            return types.SimpleNamespace(sample=lambda: types.SimpleNamespace(content=""))

    xai_module.Client = lambda api_key: types.SimpleNamespace(chat=_DummyChat())

    chat_module = types.ModuleType("xai_sdk.chat")
    chat_module.user = lambda prompt: prompt

    sys.modules["xai_sdk"] = xai_module
    sys.modules["xai_sdk.chat"] = chat_module

if "google" not in sys.modules:  # pragma: no cover - optional dependency stub
    google_module = types.ModuleType("google")

    class _DummyModels:
        def generate_content(self, *, model, contents):
            return types.SimpleNamespace(text="")

    class _DummyClient:
        def __init__(self, api_key=None):
            self.models = _DummyModels()

    genai_module = types.ModuleType("google.genai")
    genai_module.Client = _DummyClient

    types_module = types.ModuleType("google.genai.types")

    class _DummyContent:
        def __init__(self, role, parts):
            self.role = role
            self.parts = parts

    class _DummyPart:
        @staticmethod
        def from_text(*, text):
            return text

    types_module.Content = _DummyContent
    types_module.Part = _DummyPart

    genai_module.types = types_module
    google_module.genai = genai_module

    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = types_module


from trans_lib.doc_translator_mod import myst_file_translator, latex_file_translator, notebook_file_translator
from trans_lib.enums import ChunkType, DocumentType, Language
from trans_lib.errors import ChunkTranslationFailed
from trans_lib.translator_retrieval import ChunkTranslator, Meta, ModelOverloadedError
from unified_model_caller.errors import ApiCallError


class InMemoryStore:
    def __init__(self):
        self.persisted: list[tuple[str, str]] = []

    def lookup(self, src_checksum, src_lang, tgt_lang, relative_path):
        return None

    def persist_pair(
        self,
        src_checksum,
        tgt_checksum,
        src_lang,
        tgt_lang,
        src_text,
        tgt_text,
        relative_path,
    ):
        self.persisted.append((src_text, tgt_text))

    def get_best_pair_example_from_cache(self, lang, tgt_lang, txt, relative_path):
        return None

    def get_contents_by_checksum(self, checksum, lang, relative_path):
        return None

    def get_best_match_from_cache(self, lang, txt):
        raise NotImplementedError

    def do_translation_correspond_to_source(
        self,
        src_checksum,
        src_lang,
        tgt_contents,
        tgt_lang,
        relative_path,
    ):
        raise NotImplementedError


class RaisingCaller:
    def __init__(self):
        self.called = False
        self.waited = False

    def call(self, prompt: str) -> str:
        self.called = True
        raise ApiCallError("Gemini API call failed: missing api key")

    def wait_cooldown(self) -> None:
        self.waited = True


class OverloadedThenSucceedCaller:
    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0
        self.waits = 0

    def call(self, prompt: str) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ModelOverloadedError("model overloaded")
        return "<output>Translated chunk</output>"

    def wait_cooldown(self) -> None:
        self.waits += 1


class AlwaysOverloadedCaller:
    def __init__(self):
        self.calls = 0

    def call(self, prompt: str) -> str:
        self.calls += 1
        raise ModelOverloadedError("still overloaded")

    def wait_cooldown(self) -> None:
        pass


class FailingTranslator:
    def __init__(self, error: Exception):
        self.error = error

    async def translate_or_fetch(self, meta: Meta) -> str:
        raise self.error


def test_placeholder_only_chunk_skips_model_call():
    store = InMemoryStore()
    caller = RaisingCaller()
    translator = ChunkTranslator(store, caller)

    chunk = "```{code-cell} python3\nprint('Hello')\n```\n"
    meta = Meta(
        chunk=chunk,
        src_lang=Language.ENGLISH,
        tgt_lang=Language.FRENCH,
        doc_type=DocumentType.JupyterNotebook,
        chunk_type=ChunkType.Myst,
        vocab=None,
        rel_path="docs/example.md",
    )

    translated = asyncio.run(translator.translate_or_fetch(meta))

    assert translated == chunk
    assert caller.called is False
    assert store.persisted == [(chunk, chunk)]


def test_chunk_with_text_raises_chunk_translation_failed():
    store = InMemoryStore()
    caller = RaisingCaller()
    translator = ChunkTranslator(store, caller)

    chunk = "This sentence must be translated.\n"
    meta = Meta(
        chunk=chunk,
        src_lang=Language.ENGLISH,
        tgt_lang=Language.FRENCH,
        doc_type=DocumentType.JupyterNotebook,
        chunk_type=ChunkType.Myst,
        vocab=None,
        rel_path="docs/example.md",
    )

    with pytest.raises(ChunkTranslationFailed) as excinfo:
        asyncio.run(translator.translate_or_fetch(meta))

    assert caller.called is True
    assert excinfo.value.chunk == chunk
    assert isinstance(excinfo.value.original_exception, ApiCallError)
    assert store.persisted == []


def test_chunk_with_text_raises_chunk_translation_failed_latex():
    store = InMemoryStore()
    caller = RaisingCaller()
    translator = ChunkTranslator(store, caller)

    chunk = r"This sentence must be translated. \textbf{but we have some placeholders anyway}"
    meta = Meta(
        chunk=chunk,
        src_lang=Language.ENGLISH,
        tgt_lang=Language.FRENCH,
        doc_type=DocumentType.LaTeX,
        chunk_type=ChunkType.LaTeX,
        vocab=None,
        rel_path="docs/example.md",
    )

    with pytest.raises(ChunkTranslationFailed) as excinfo:
        asyncio.run(translator.translate_or_fetch(meta))

    assert caller.called is True
    assert excinfo.value.chunk == chunk
    assert store.persisted == []


def test_chunk_with_ph_only_doesnt_call_model_latex():
    store = InMemoryStore()
    caller = RaisingCaller()
    translator = ChunkTranslator(store, caller)

    chunk = r"\begin{document}\end{document}"
    meta = Meta(
        chunk=chunk,
        src_lang=Language.ENGLISH,
        tgt_lang=Language.FRENCH,
        doc_type=DocumentType.LaTeX,
        chunk_type=ChunkType.LaTeX,
        vocab=None,
        rel_path="docs/example.md",
    )

    translated = asyncio.run(translator.translate_or_fetch(meta))

    assert translated == chunk
    assert caller.called is False
    assert store.persisted == [(chunk, chunk)]


def test_model_overloaded_retries_then_succeeds(monkeypatch):
    store = InMemoryStore()
    caller = OverloadedThenSucceedCaller(fail_times=2)
    translator = ChunkTranslator(
        store,
        caller,
        overload_retry_attempts=4,
        overload_retry_initial_delay=0.01,
        overload_retry_max_delay=0.02,
    )

    monkeypatch.setattr(
        "trans_lib.translator_retrieval.chunk_contains_ph_only",
        lambda *args, **kwargs: False,
    )

    observed_sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        observed_sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    chunk = "Translate me please.\n"
    meta = Meta(
        chunk=chunk,
        src_lang=Language.ENGLISH,
        tgt_lang=Language.FRENCH,
        doc_type=DocumentType.Other,
        chunk_type=ChunkType.Other,
        vocab=None,
        rel_path="docs/example.md",
    )

    translated = asyncio.run(translator.translate_or_fetch(meta))

    assert translated == "Translated chunk"
    assert caller.calls == 3  # two overloads then success
    assert observed_sleeps == [0.01, 0.02]
    assert store.persisted == [(chunk, translated)]


def test_model_overloaded_exhausts_retries(monkeypatch):
    store = InMemoryStore()
    caller = AlwaysOverloadedCaller()
    translator = ChunkTranslator(
        store,
        caller,
        overload_retry_attempts=2,
        overload_retry_initial_delay=0.01,
        overload_retry_max_delay=0.02,
    )

    monkeypatch.setattr(
        "trans_lib.translator_retrieval.chunk_contains_ph_only",
        lambda *args, **kwargs: False,
    )

    async def fake_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    chunk = "Stuck chunk.\n"
    meta = Meta(
        chunk=chunk,
        src_lang=Language.ENGLISH,
        tgt_lang=Language.FRENCH,
        doc_type=DocumentType.Other,
        chunk_type=ChunkType.Other,
        vocab=None,
        rel_path="docs/example.md",
    )

    with pytest.raises(ChunkTranslationFailed) as excinfo:
        asyncio.run(translator.translate_or_fetch(meta))

    assert excinfo.value.chunk == chunk
    assert store.persisted == []
    assert caller.calls == 2


def test_myst_chunk_metadata_tagged_on_failure(monkeypatch):
    chunk = "Paragraph needing translation.\n"
    cell = {"metadata": {}, "source": chunk}

    error = ChunkTranslationFailed(chunk, RuntimeError("boom"))
    failing_translator = FailingTranslator(error)

    monkeypatch.setattr(
        "trans_lib.doc_translator_mod.myst_file_translator.build_translator_with_model",
        lambda *args, **kwargs: failing_translator,
    )

    result_cell = asyncio.run(
        myst_file_translator.translate_chunk_async(
            root_path=Path("."),
            cell=cell,
            source_language=Language.ENGLISH,
            target_language=Language.FRENCH,
            relative_path="docs/example.md",
            vocab_list=None,
            llm_caller=types.SimpleNamespace(),
        )
    )

    assert result_cell["source"] == chunk
    assert result_cell["metadata"].get("not-translated-due-to-exception") == "True"


def test_latex_chunk_metadata_tagged_on_failure(monkeypatch):
    chunk = "\\section{Title}"
    cell = {"metadata": {}, "source": chunk}

    error = ChunkTranslationFailed(chunk, RuntimeError("boom"))
    failing_translator = FailingTranslator(error)

    monkeypatch.setattr(
        "trans_lib.doc_translator_mod.latex_file_translator.build_translator_with_model",
        lambda *args, **kwargs: failing_translator,
    )

    result_cell = asyncio.run(
        latex_file_translator.translate_chunk_async(
            root_path=Path("."),
            cell=cell,
            source_language=Language.ENGLISH,
            target_language=Language.FRENCH,
            relative_path="docs/example.md",
            vocab_list=None,
            llm_caller=types.SimpleNamespace(),
        )
    )

    assert result_cell["source"] == chunk
    assert result_cell["metadata"].get("not-translated-due-to-exception") == "True"


def test_notebook_cell_metadata_tagged_on_failure(monkeypatch):
    chunk = "Notebook cell text."
    cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": chunk,
    }

    error = ChunkTranslationFailed(chunk, RuntimeError("boom"))
    failing_translator = FailingTranslator(error)

    monkeypatch.setattr(
        "trans_lib.doc_translator_mod.notebook_file_translator.build_translator_with_model",
        lambda *args, **kwargs: failing_translator,
    )

    result_cell = asyncio.run(
        notebook_file_translator.translate_jupyter_cell_async(
            root_path=Path("."),
            cell=cell,
            source_language=Language.ENGLISH,
            target_language=Language.FRENCH,
            vocab_list=None,
            llm_caller=types.SimpleNamespace(),
            relative_path="docs/example.md",
        )
    )

    assert result_cell["source"] == chunk
    assert "not-translated-due-to-exception" in result_cell["metadata"].get("tags", [])
