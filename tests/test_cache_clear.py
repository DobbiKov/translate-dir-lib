from pathlib import Path

from trans_lib.constants import CACHE_DIR_NAME, CONF_DIR
from trans_lib.enums import Language
from trans_lib.helpers import calculate_checksum, calculate_path_checksum
from trans_lib.project_config_models import ProjectConfig
from trans_lib.project_manager import Project
from trans_lib.translation_cache.cache_backend import (
    PATH_CHECKSUM_COLUMN,
    read_correspondence_cache,
    write_correspondence_cache,
)


def _write_chunk(cache_dir: Path, lang: Language, path_hash: str, checksum: str, contents: str) -> None:
    chunk_dir = cache_dir / str(lang) / path_hash
    chunk_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / checksum).write_text(contents, encoding="utf-8")


def _make_project(tmp_path: Path) -> Project:
    project_root = tmp_path / "proj"
    src_dir = project_root / "src_en"
    src_dir.mkdir(parents=True)
    (project_root / CONF_DIR).mkdir(parents=True)

    config = ProjectConfig.new(project_name="proj")
    config.set_runtime_root_path(project_root)
    config.set_src_dir_config(src_dir, Language.ENGLISH)
    return Project(project_root, config)


def test_clear_missing_chunks_no_cache_dir(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 0
    assert stats.cleared_fields == 0
    assert stats.removed_source_chunks == 0


def test_clear_missing_chunks_no_csv_deletes_source_chunks(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_hash = calculate_path_checksum("doc.md")

    src_text = "Hello"
    src_checksum = calculate_checksum(src_text)
    _write_chunk(cache_dir, Language.ENGLISH, path_hash, src_checksum, src_text)

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_source_chunks == 1
    assert not (cache_dir / "English" / path_hash / src_checksum).exists()


def test_clear_missing_chunks_empty_source_checksum_row(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    write_correspondence_cache(
        project.root_path,
        [{PATH_CHECKSUM_COLUMN: "", "English": "", "French": "abc"}],
        [PATH_CHECKSUM_COLUMN, "English", "French"],
    )

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 1


def test_clear_missing_chunks_row_without_targets(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_hash = calculate_path_checksum("doc.md")

    src_text = "Hello"
    src_checksum = calculate_checksum(src_text)
    _write_chunk(cache_dir, Language.ENGLISH, path_hash, src_checksum, src_text)

    write_correspondence_cache(
        project.root_path,
        [{PATH_CHECKSUM_COLUMN: path_hash, "English": src_checksum}],
        [PATH_CHECKSUM_COLUMN, "English"],
    )

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 1
    assert stats.removed_source_chunks == 1


def test_clear_missing_chunks_preserves_row_with_targets(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_hash = calculate_path_checksum("doc.md")

    src_text = "Hello"
    fr_text = "Bonjour"
    src_checksum = calculate_checksum(src_text)
    fr_checksum = calculate_checksum(fr_text)

    _write_chunk(cache_dir, Language.ENGLISH, path_hash, src_checksum, src_text)
    _write_chunk(cache_dir, Language.FRENCH, path_hash, fr_checksum, fr_text)

    write_correspondence_cache(
        project.root_path,
        [{PATH_CHECKSUM_COLUMN: path_hash, "English": src_checksum, "French": fr_checksum}],
        [PATH_CHECKSUM_COLUMN, "English", "French"],
    )

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 0
    assert stats.cleared_fields == 0
    assert stats.removed_source_chunks == 0


def test_clear_missing_chunks_handles_top_level_lang_files(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    lang_dir = cache_dir / "English"
    lang_dir.mkdir(parents=True, exist_ok=True)

    src_text = "Hello"
    src_checksum = calculate_checksum(src_text)
    (lang_dir / src_checksum).write_text(src_text, encoding="utf-8")

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_source_chunks == 1
    assert not (lang_dir / src_checksum).exists()


def test_clear_missing_chunks_removes_row_and_source(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_hash = calculate_path_checksum("doc.md")

    src_text = "Hello"
    tgt_text = "Bonjour"
    src_checksum = calculate_checksum(src_text)
    tgt_checksum = calculate_checksum(tgt_text)

    _write_chunk(cache_dir, Language.ENGLISH, path_hash, src_checksum, src_text)
    write_correspondence_cache(
        project.root_path,
        [{PATH_CHECKSUM_COLUMN: path_hash, "English": src_checksum, "French": tgt_checksum}],
        [PATH_CHECKSUM_COLUMN, "English", "French"],
    )

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 1
    assert not (cache_dir / "English" / path_hash / src_checksum).exists()

    cache_data = read_correspondence_cache(project.root_path)
    assert cache_data is not None
    _, data_list = cache_data
    assert data_list == []


def test_clear_missing_chunks_clears_missing_target_fields(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_hash = calculate_path_checksum("doc.md")

    src_text = "Hello"
    fr_text = "Bonjour"
    de_text = "Hallo"
    src_checksum = calculate_checksum(src_text)
    fr_checksum = calculate_checksum(fr_text)
    de_checksum = calculate_checksum(de_text)

    _write_chunk(cache_dir, Language.ENGLISH, path_hash, src_checksum, src_text)
    _write_chunk(cache_dir, Language.FRENCH, path_hash, fr_checksum, fr_text)
    write_correspondence_cache(
        project.root_path,
        [{
            PATH_CHECKSUM_COLUMN: path_hash,
            "English": src_checksum,
            "French": fr_checksum,
            "German": de_checksum,
        }],
        [PATH_CHECKSUM_COLUMN, "English", "French", "German"],
    )

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 0
    assert stats.cleared_fields == 1

    cache_data = read_correspondence_cache(project.root_path)
    assert cache_data is not None
    _, data_list = cache_data
    assert len(data_list) == 1
    assert data_list[0]["German"] == ""
    assert data_list[0]["French"] == fr_checksum


def test_clear_missing_chunks_removes_row_when_source_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_hash = calculate_path_checksum("doc.md")

    src_checksum = calculate_checksum("Hello")
    fr_text = "Bonjour"
    fr_checksum = calculate_checksum(fr_text)

    _write_chunk(cache_dir, Language.FRENCH, path_hash, fr_checksum, fr_text)
    write_correspondence_cache(
        project.root_path,
        [{PATH_CHECKSUM_COLUMN: path_hash, "English": src_checksum, "French": fr_checksum}],
        [PATH_CHECKSUM_COLUMN, "English", "French"],
    )

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 1
    assert (cache_dir / "French" / path_hash / fr_checksum).exists()


def test_clear_missing_chunks_removes_orphan_source_chunks(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_hash = calculate_path_checksum("doc.md")

    src_text = "Hello"
    src_checksum = calculate_checksum(src_text)
    _write_chunk(cache_dir, Language.ENGLISH, path_hash, src_checksum, src_text)

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_source_chunks == 1
    assert not (cache_dir / "English" / path_hash / src_checksum).exists()


def test_clear_missing_chunks_multi_row_mixed_states(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    cache_dir = project.root_path / CONF_DIR / CACHE_DIR_NAME
    path_a = calculate_path_checksum("a.md")
    path_b = calculate_path_checksum("b.md")

    src_a = "Alpha"
    tgt_a = "Alfa"
    src_b = "Beta"
    tgt_b = "Bete"

    src_a_checksum = calculate_checksum(src_a)
    tgt_a_checksum = calculate_checksum(tgt_a)
    src_b_checksum = calculate_checksum(src_b)
    tgt_b_checksum = calculate_checksum(tgt_b)

    _write_chunk(cache_dir, Language.ENGLISH, path_a, src_a_checksum, src_a)
    _write_chunk(cache_dir, Language.FRENCH, path_a, tgt_a_checksum, tgt_a)
    _write_chunk(cache_dir, Language.ENGLISH, path_b, src_b_checksum, src_b)

    write_correspondence_cache(
        project.root_path,
        [
            {PATH_CHECKSUM_COLUMN: path_a, "English": src_a_checksum, "French": tgt_a_checksum},
            {PATH_CHECKSUM_COLUMN: path_b, "English": src_b_checksum, "French": tgt_b_checksum},
        ],
        [PATH_CHECKSUM_COLUMN, "English", "French"],
    )

    stats = project.clear_translation_cache_missing_chunks()
    assert stats.removed_rows == 1
    assert stats.cleared_fields == 0

    cache_data = read_correspondence_cache(project.root_path)
    assert cache_data is not None
    _, data_list = cache_data
    assert len(data_list) == 1
    assert data_list[0][PATH_CHECKSUM_COLUMN] == path_a
