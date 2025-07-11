from dataclasses import dataclass
import re
from typing import Any, Callable, Coroutine
from loguru import logger
from trans_lib.helpers import calculate_checksum
from pathlib import Path
from trans_lib.enums import ChunkType, DocumentType, Language
from trans_lib.translation_store.translation_store import TranslationStore, TranslationStoreCsv
from trans_lib.translator import def_prompt_template, finalize_prompt, finalize_xml_prompt, translate_chunk_with_prompt, _prepare_prompt_for_language, _prepare_prompt_for_vocab_list, _prepare_prompt_for_content_type
from trans_lib.vocab_list import VocabList
from trans_lib.xml_manipulator_mod.xml import reconstruct_from_xml
from trans_lib.xml_manipulator_mod.mod import chunk_to_xml, code_to_xml
from trans_lib.prompts import xml_translation_prompt
from trans_lib.translator import _ask_gemini_model
from trans_lib.prompts import prompt4, prompt_jupyter_md


def is_whitespace(text: str) -> bool:
    return not text or text.isspace()

@dataclass
class Meta:
    chunk: str
    src_lang: Language
    tgt_lang: Language
    doc_type: DocumentType
    chunk_type: ChunkType
    vocab: VocabList | None

@dataclass
class CodeMeta(Meta):
    src_lang: Language
    tgt_lang: Language
    doc_type: DocumentType
    chunk_type: ChunkType
    vocab: VocabList | None
    prog_lang: str

# ====================== Prompt / Strategy layer ===================== #

def _extract_output(raw_response: str) -> str:
    """Collect everything between <output> tags (can appear multiple times)."""
    parts = re.findall(r"<output>(.*?)</output>", raw_response, flags=re.S)
    return "\n".join(parts)


class TranslateStrategy:
    """Callable bundle: build prompt  → ask LLM → post‑process."""

    def __init__(
        self,
        prompt_builder: Callable[[Meta], tuple[str, bool]],
        call_model: Callable[[str], Coroutine[Any, Any, str]],
        postprocess: Callable[[str], str],
    ) -> None:
        self._prompt_builder = prompt_builder
        self._call_model = call_model
        self._post = postprocess

    async def run(
        self,
        params: Meta
    ) -> str:
        prompt, is_xml = self._prompt_builder(params)
        raw = await self._call_model(prompt)
        return self._post(raw)


# ---- Prompt builders ---------------------------------------------- #

def _plain_prompt_builder(template: str):
    def _builder(params: Meta):
        chunk = params.chunk
        tgt = params.tgt_lang
        src = params.src_lang
        vocab = params.vocab
        p = _prepare_prompt_for_language(template, tgt, src)
        p = _prepare_prompt_for_vocab_list(p, vocab)
        p = finalize_prompt(p, chunk)
        return p, False

    return _builder


def _xml_prompt_builder(doc_type: DocumentType, chunk_type: ChunkType):
    def _builder(params: Meta):
        chunk = params.chunk
        tgt = params.tgt_lang
        src = params.src_lang
        xml_chunk = ""
        vocab = params.vocab

        lang = None
        if chunk_type == ChunkType.Code:
            if type(params) is CodeMeta:
                xml_chunk, _ = code_to_xml(chunk, params.prog_lang)
        else:
            xml_chunk = chunk_to_xml(chunk, doc_type, chunk_type)

        prompt = xml_translation_prompt
        prompt = _prepare_prompt_for_language(prompt, tgt, src)
        def get_content_type() -> str:
            if doc_type == DocumentType.LaTeX:
                return "LaTeX"
            if doc_type == DocumentType.JupyterNotebook and chunk_type == ChunkType.Myst:
                return "MyST"
            if doc_type == DocumentType.JupyterNotebook and chunk_type == ChunkType.Code:
                return f"{lang} code"
            else:
                return "any document"
        prompt = _prepare_prompt_for_content_type(prompt, get_content_type())
        prompt = _prepare_prompt_for_vocab_list(prompt, vocab)
        prompt = finalize_xml_prompt(prompt, xml_chunk)
        return prompt, True

    return _builder

async def _call_model_func(text: str) -> str:
    print("=======================")
    print("prompt:")
    print(text)
    return await _ask_gemini_model(text, model_name="gemini-2.0-flash")

# ---- Strategies map ------------------------------------------------ #
LATEX_STRATEGY   = TranslateStrategy(_xml_prompt_builder(DocumentType.LaTeX, ChunkType.LaTeX), _call_model_func, lambda r: reconstruct_from_xml(_extract_output(r)))
MYST_STRATEGY    = TranslateStrategy(_xml_prompt_builder(DocumentType.JupyterNotebook, ChunkType.Myst), _call_model_func,  lambda r: reconstruct_from_xml(_extract_output(r)))
PLAIN_STRATEGY   = TranslateStrategy(_plain_prompt_builder(prompt4), _call_model_func,                    _extract_output)
CODE_STRATEGY    = TranslateStrategy(_xml_prompt_builder(DocumentType.JupyterNotebook, ChunkType.Code), _call_model_func,        _extract_output)
MD_STRATEGY      = TranslateStrategy(_plain_prompt_builder(prompt_jupyter_md), _call_model_func,          _extract_output)

STRATEGY_MAP: dict[tuple[DocumentType, ChunkType], TranslateStrategy] = {
    (DocumentType.LaTeX,            ChunkType.LaTeX): LATEX_STRATEGY,
    (DocumentType.JupyterNotebook,  ChunkType.Myst):  MYST_STRATEGY,
    (DocumentType.JupyterNotebook,  ChunkType.Code):  CODE_STRATEGY,
    (DocumentType.Markdown,         ChunkType.Myst):  MD_STRATEGY,
    (DocumentType.Other,            ChunkType.Other): PLAIN_STRATEGY,
}


class ChunkTranslator:
    """Facade: one method replaces legacy free‑function."""

    def __init__(self, store: TranslationStore):
        self._store = store

    async def translate_or_fetch(self, meta: Meta) -> str:
        chunk = meta.chunk
        if not chunk.strip():
            return chunk  # whitespace → passthrough

        src_checksum = calculate_checksum(chunk)
        cached = self._store.lookup(src_checksum, meta.src_lang, meta.tgt_lang)
        if cached is not None:
            logger.debug("cache hit (%s → %s)", meta.src_lang, meta.tgt_lang)
            return cached

        strategy = STRATEGY_MAP[(meta.doc_type, meta.chunk_type)]
        translated = await strategy.run(meta)
        tgt_checksum = calculate_checksum(translated)

        self._store.persist_pair(
            src_checksum,
            tgt_checksum,
            meta.src_lang,
            meta.tgt_lang,
            chunk,
            translated,
        )
        return translated

def build_default_translator(root_path: Path) -> ChunkTranslator:
    """Constructs default translation factory"""
    return ChunkTranslator(TranslationStoreCsv(root_path))
