import asyncio
from dataclasses import dataclass
import time
from typing import Callable
from loguru import logger
from trans_lib.helpers import calculate_checksum, extract_translated_from_response
from pathlib import Path
from trans_lib.enums import ChunkType, DocumentType, Language
from trans_lib.translation_cache.translation_cache import TranslationCache, TranslationCacheCsv
from trans_lib.translator import finalize_prompt, finalize_xml_prompt, _prepare_prompt_for_language, _prepare_prompt_for_vocab_list, _prepare_prompt_for_content_type, _prepare_prompt_for_translation_example
from trans_lib.vocab_list import VocabList
from trans_lib.xml_manipulator_mod.xml import reconstruct_from_xml
from trans_lib.xml_manipulator_mod.mod import chunk_contains_ph_only, chunk_to_xml, code_to_xml
from trans_lib.prompts import xml_translation_prompt
from trans_lib.translator import _ask_gemini_model
from trans_lib.prompts import prompt4, xml_with_previous_translation_prompt
from unified_model_caller.core import LLMCaller
from unified_model_caller.errors import ApiCallError
from trans_lib.errors import ChunkTranslationFailed
try:
    from unified_model_caller.errors import ModelOverloadedError
except ImportError:  # pragma: no cover - unified_model_caller may not expose the new error yet
    class ModelOverloadedError(ApiCallError):
        """Fallback stub when unified_model_caller doesn't expose ModelOverloadedError."""
        pass


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
    rel_path: str

@dataclass
class CodeMeta(Meta):
    chunk: str
    src_lang: Language
    tgt_lang: Language
    doc_type: DocumentType
    chunk_type: ChunkType
    vocab: VocabList | None
    rel_path: str
    prog_lang: str

@dataclass
class WithExampleMeta(Meta):
    chunk: str
    src_lang: Language
    tgt_lang: Language
    doc_type: DocumentType
    chunk_type: ChunkType
    vocab: VocabList | None
    rel_path: str
    ex_src: str
    ex_tgt: str

# ====================== Prompt / Strategy layer ===================== #

class TranslateStrategy:
    """Callable bundle: build prompt  → ask LLM → post‑process."""

    def __init__(
        self,
        prompt_builder: Callable[[Meta], tuple[str, bool]],
        call_model: Callable[[str], str],
        postprocess: Callable[[str], str],
    ) -> None:
        self._prompt_builder = prompt_builder
        self._call_model = call_model
        self._post = postprocess

    def set_call_model(self, call_mode: Callable[[str], str]) -> None:
        self._call_model = call_mode

    async def run(
        self,
        params: Meta
    ) -> str:
        prompt, is_xml = self._prompt_builder(params)
        raw = self._call_model(prompt)
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

        # lang = None
        if chunk_type == ChunkType.Code:
            if isinstance(params, CodeMeta):
                logger.debug("Preparing XML chunk for code translation.")
                xml_chunk = code_to_xml(chunk, params.prog_lang)[0]
        else:
            xml_chunk = chunk_to_xml(chunk, chunk_type)

        prompt = xml_translation_prompt
        if isinstance(params, WithExampleMeta) and chunk_type != ChunkType.Code:
            prompt = xml_with_previous_translation_prompt
            ex_src = chunk_to_xml(params.ex_src, chunk_type)
            ex_tgt = chunk_to_xml(params.ex_tgt, chunk_type)
            prompt = _prepare_prompt_for_translation_example(prompt, ex_src, ex_tgt)

        prompt = _prepare_prompt_for_language(prompt, tgt, src)
        def get_content_type() -> str:
            if doc_type == DocumentType.LaTeX:
                return "LaTeX"
            if (doc_type == DocumentType.JupyterNotebook and chunk_type == ChunkType.Myst) or doc_type == DocumentType.Markdown:
                return "MyST"
            if doc_type == DocumentType.JupyterNotebook and chunk_type == ChunkType.Code and type(params) is CodeMeta:
                prog_lang = params.prog_lang
                return f"{prog_lang} code"
            else:
                return "any document"
        prompt = _prepare_prompt_for_content_type(prompt, get_content_type())
        prompt = _prepare_prompt_for_vocab_list(prompt, vocab)
        prompt = finalize_xml_prompt(prompt, xml_chunk)
        return prompt, True

    return _builder

def _identity_prompt_builder():
    def _builder(params: Meta):
        return params.chunk, False

    return _builder

async def _call_model_func(text: str) -> str:
    # print("=======================")
    # print("prompt:")
    # print(text)
    return await _ask_gemini_model(text, model_name="gemini-2.0-flash")

def _dont_call_model(text: str) -> str:
    return text

# ---- Strategies map ------------------------------------------------ #
LATEX_STRATEGY   = TranslateStrategy(_xml_prompt_builder(DocumentType.LaTeX, ChunkType.LaTeX), _dont_call_model, lambda r: reconstruct_from_xml(extract_translated_from_response(r)))
MYST_STRATEGY    = TranslateStrategy(_xml_prompt_builder(DocumentType.JupyterNotebook, ChunkType.Myst), _dont_call_model,  lambda r: reconstruct_from_xml(extract_translated_from_response(r)))
PLAIN_STRATEGY   = TranslateStrategy(_plain_prompt_builder(prompt4), _dont_call_model,                    extract_translated_from_response)
CODE_STRATEGY    = TranslateStrategy(_identity_prompt_builder(), _dont_call_model,  lambda r: r) 
MD_STRATEGY    = TranslateStrategy(_xml_prompt_builder(DocumentType.Markdown, ChunkType.Myst), _dont_call_model,  lambda r: reconstruct_from_xml(extract_translated_from_response(r)))

STRATEGY_MAP: dict[tuple[DocumentType, ChunkType], TranslateStrategy] = {
    (DocumentType.LaTeX,            ChunkType.LaTeX): LATEX_STRATEGY,
    (DocumentType.JupyterNotebook,  ChunkType.Myst):  MYST_STRATEGY,
    (DocumentType.JupyterNotebook,  ChunkType.Code):  CODE_STRATEGY,
    (DocumentType.Markdown,         ChunkType.Myst):  MD_STRATEGY,
    (DocumentType.Other,            ChunkType.Other): PLAIN_STRATEGY,
}


class ChunkTranslator:
    """Facade: one method replaces legacy free‑function."""

    def __init__(
        self,
        store: TranslationCache,
        model_caller: LLMCaller | None = None,
        *,
        overload_retry_attempts: int = 5,
        overload_retry_initial_delay: float = 1.0,
        overload_retry_max_delay: float = 16.0,
    ):
        self._store = store
        self._caller: LLMCaller | None = model_caller
        self._overload_attempts = max(1, overload_retry_attempts)
        self._overload_initial_delay = max(0.0, overload_retry_initial_delay)
        self._overload_max_delay = max(self._overload_initial_delay, overload_retry_max_delay)

    async def translate_or_fetch(self, meta: Meta) -> str:
        chunk = meta.chunk
        if not chunk.strip():
            return chunk  # whitespace → passthrough

        src_checksum = calculate_checksum(chunk)
        cached = self._store.lookup(src_checksum, meta.src_lang, meta.tgt_lang, meta.rel_path)
        if cached is not None:
            logger.debug(f"cache hit ({meta.src_lang} -> {meta.tgt_lang})")
            return cached

        strategy = STRATEGY_MAP[(meta.doc_type, meta.chunk_type)]
        ph_only = chunk_contains_ph_only(chunk, meta.chunk_type)
        caller = self._caller
        if caller is not None and strategy != CODE_STRATEGY: # we don't want to call model on code, we leave it unchanged
            strategy.set_call_model(lambda t: caller.call(t))

            def f_call_model(t):
                res = caller.call(t)
                caller.wait_cooldown()
                return res

            strategy.set_call_model(f_call_model)

        example = self._store.get_best_pair_example_from_cache(meta.src_lang, meta.tgt_lang, meta.chunk, meta.rel_path)
        if example is not None:
            src_ex, tgt_ex, score = example
            if score > 0.7:
                logger.debug("Found an example for a chunk")
                meta = WithExampleMeta(
                    meta.chunk,
                    meta.src_lang,
                    meta.tgt_lang,
                    meta.doc_type,
                    meta.chunk_type,
                    meta.vocab,
                    meta.rel_path,
                    src_ex,
                    tgt_ex,
                )

        if ph_only:
            translated = chunk
        else:
            try:
                translated = await self._translate_with_retry(strategy, meta)
            except Exception as exc:  # noqa: BLE001 - we intentionally downgrade translation errors
                logger.error(
                    f"Chunk translation failed due to {exc.__class__.__name__}: {exc}",
                )
                raise ChunkTranslationFailed(chunk, exc) from exc

        tgt_checksum = calculate_checksum(translated)

        if ph_only:
            logger.trace("ph only")

        self._store.persist_pair(
            src_checksum,
            tgt_checksum,
            meta.src_lang,
            meta.tgt_lang,
            chunk,
            translated,
            meta.rel_path,
        )
        return translated

    async def _translate_with_retry(self, strategy: TranslateStrategy, meta: Meta) -> str:
        delay = self._overload_initial_delay or 1.0
        for attempt in range(1, self._overload_attempts + 1):
            try:
                return await strategy.run(meta)
            except ModelOverloadedError as exc:
                if attempt >= self._overload_attempts:
                    logger.error(
                        f"Model overloaded after {attempt} attempts, giving up.",
                    )
                    raise exc

                wait_seconds = min(delay, self._overload_max_delay)
                logger.warning(
                    f"Model overloaded (attempt {attempt}/{self._overload_attempts}). Retrying in {wait_seconds:.2f}s...",
                )
                await asyncio.sleep(wait_seconds)
                delay = min(delay * 2, self._overload_max_delay)

def build_translator_with_model(root_path: Path, caller: LLMCaller | None = None) -> ChunkTranslator:
    """Constructs default translation factory with a particular model"""
    return ChunkTranslator(TranslationCacheCsv(root_path), caller)
