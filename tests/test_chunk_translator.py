import asyncio

import pytest

from trans_lib.enums import ChunkType, DocumentType, Language
from trans_lib.translator_retrieval import ChunkTranslator, Meta
from unified_model_caller.errors import ApiCallError


class InMemoryStore:
    def __init__(self):
        self.persisted = []

    def lookup(self, src_checksum, src_lang, tgt_lang):
        return None

    def persist_pair(
        self,
        src_checksum,
        tgt_checksum,
        src_lang,
        tgt_lang,
        src_text,
        tgt_text,
    ):
        self.persisted.append((src_text, tgt_text))

    def get_best_pair_example_from_db(self, lang, tgt_lang, txt):
        return None

    def get_contents_by_checksum(self, checksum, lang):
        return None

    def get_best_match_from_db(self, lang, txt):
        raise NotImplementedError

    def do_translation_correspond_to_source(
        self,
        root_path,
        src_checksum,
        src_lang,
        tgt_contents,
        tgt_lang,
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
    )

    translated = asyncio.run(translator.translate_or_fetch(meta))

    assert translated == chunk
    assert caller.called is False
    assert store.persisted == [(chunk, chunk)]


def test_chunk_with_text_calls_model_and_propagates_missing_key_error():
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
    )

    with pytest.raises(ApiCallError) as excinfo:
        asyncio.run(translator.translate_or_fetch(meta))

    assert caller.called is True
    assert "missing api key" in str(excinfo.value).lower()
    assert store.persisted == []

def test_chunk_with_text_calls_model_and_propagates_missing_key_error_2():
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
    )

    with pytest.raises(ApiCallError) as excinfo:
        asyncio.run(translator.translate_or_fetch(meta))

    assert caller.called is True
    assert "missing api key" in str(excinfo.value).lower()
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
    )

    translated = asyncio.run(translator.translate_or_fetch(meta))

    assert translated == chunk
    assert caller.called is False
    assert store.persisted == [(chunk, chunk)]
