from trans_lib.doc_translator_mod.typst_chunker import split_typst_document_into_chunks


def test_inline_math_stays_in_single_context_chunk() -> None:
    source = "Before $x + y$ after.\n"

    chunks = split_typst_document_into_chunks(source)

    assert len(chunks) == 1
    assert chunks[0]["content"] == source


def test_inline_hash_func_call_stays_with_surrounding_text() -> None:
    source = "Read #link(\"https://example.com\")[this] now.\n"

    chunks = split_typst_document_into_chunks(source)

    assert len(chunks) == 1
    assert chunks[0]["content"] == source
