from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from trans_lib.constants import CACHE_DIR_NAME
from trans_lib.enums import Language
from trans_lib.helpers import calculate_path_checksum, get_config_dir_from_root, normalize_relative_path
from trans_lib.translation_cache.cache_backend import (
    PATH_CHECKSUM_COLUMN,
    read_correspondence_cache,
    write_correspondence_cache,
)


@dataclass
class CacheClearStats:
    removed_rows: int = 0
    cleared_fields: int = 0
    removed_source_chunks: int = 0


@dataclass
class CacheDeleteStats:
    removed_rows: int = 0
    cleared_fields: int = 0
    removed_chunk_files: int = 0


def _iter_lang_cache_files(
    cache_dir: Path,
    lang_name: str,
) -> Iterable[tuple[str, str, Path]]:
    lang_dir = cache_dir / lang_name
    if not lang_dir.exists() or not lang_dir.is_dir():
        return []

    def _iter() -> Iterable[tuple[str, str, Path]]:
        for entry in lang_dir.iterdir():
            if entry.is_dir():
                path_hash = entry.name
                for file_path in entry.iterdir():
                    if file_path.is_file():
                        yield path_hash, file_path.name, file_path
            elif entry.is_file():
                yield "", entry.name, entry

    return list(_iter())


def _checksum_file_exists(
    cache_dir: Path,
    lang_name: str,
    path_hash: str,
    checksum: str,
) -> bool:
    if not checksum:
        return False
    lang_dir = cache_dir / lang_name
    if not lang_dir.exists():
        return False
    file_path = lang_dir / path_hash / checksum if path_hash else lang_dir / checksum
    return file_path.is_file()


def _delete_dir_contents(dir_path: Path, remove_dir: bool = True) -> int:
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    removed_files = 0
    for entry in dir_path.iterdir():
        if entry.is_dir():
            removed_files += _delete_dir_contents(entry, remove_dir=True)
        elif entry.is_file():
            entry.unlink()
            removed_files += 1
    if remove_dir:
        try:
            dir_path.rmdir()
        except OSError:
            pass
    return removed_files


def _row_has_any_language_values(row: dict, fields: list[str]) -> bool:
    for field in fields:
        if field == PATH_CHECKSUM_COLUMN:
            continue
        if row.get(field, ""):
            return True
    return False


def clear_missing_chunks(root_path: Path, source_lang: Language) -> CacheClearStats:
    stats = CacheClearStats()
    cache_dir = get_config_dir_from_root(root_path) / CACHE_DIR_NAME
    if not cache_dir.exists():
        return stats

    source_lang_name = str(source_lang)
    source_files = _iter_lang_cache_files(cache_dir, source_lang_name)
    referenced_sources: set[tuple[str, str]] = set()

    cache_data = read_correspondence_cache(root_path)
    if cache_data is None:
        for _, _, file_path in source_files:
            if file_path.exists():
                file_path.unlink()
                stats.removed_source_chunks += 1
        return stats

    fields, data_list = cache_data
    src_col = source_lang_name
    target_cols = [field for field in fields if field not in {PATH_CHECKSUM_COLUMN, src_col}]
    remaining_rows: list[dict] = []

    for row in data_list:
        path_hash = row.get(PATH_CHECKSUM_COLUMN, "")
        src_checksum = row.get(src_col, "")
        if not src_checksum:
            stats.removed_rows += 1
            continue
        if not _checksum_file_exists(cache_dir, src_col, path_hash, src_checksum):
            stats.removed_rows += 1
            continue

        present_targets = 0
        missing_targets: list[str] = []
        for col in target_cols:
            tgt_checksum = row.get(col, "")
            if not tgt_checksum:
                continue
            if _checksum_file_exists(cache_dir, col, path_hash, tgt_checksum):
                present_targets += 1
            else:
                missing_targets.append(col)

        if present_targets == 0:
            stats.removed_rows += 1
            continue

        for col in missing_targets:
            row[col] = ""
        stats.cleared_fields += len(missing_targets)
        remaining_rows.append(row)
        referenced_sources.add((path_hash, src_checksum))

    if stats.removed_rows > 0 or stats.cleared_fields > 0:
        write_correspondence_cache(root_path, remaining_rows, fields)

    for path_hash, checksum, file_path in source_files:
        if (path_hash, checksum) in referenced_sources:
            continue
        if file_path.exists():
            file_path.unlink()
            stats.removed_source_chunks += 1

    return stats


def clear_all(
    root_path: Path,
    lang: Language | None,
    relative_path: str | None,
) -> CacheDeleteStats:
    stats = CacheDeleteStats()
    cache_dir = get_config_dir_from_root(root_path) / CACHE_DIR_NAME
    if not cache_dir.exists():
        return stats

    path_hash = ""
    if relative_path:
        path_hash = calculate_path_checksum(normalize_relative_path(relative_path))

    if lang is not None: # lang provided
        lang_dir = cache_dir / str(lang)
        if path_hash: # file provided
            stats.removed_chunk_files += _delete_dir_contents(lang_dir / path_hash, remove_dir=True)
        else: # file not provided
            stats.removed_chunk_files += _delete_dir_contents(lang_dir, remove_dir=True)
    else: # lang not provided
        if path_hash: # file provided
            for entry in cache_dir.iterdir():
                if not entry.is_dir():
                    continue
                stats.removed_chunk_files += _delete_dir_contents(entry / path_hash, remove_dir=True)
        else: # nor file is provided
            for entry in cache_dir.iterdir():
                if not entry.is_dir():
                    continue
                stats.removed_chunk_files += _delete_dir_contents(entry, remove_dir=True)

    cache_data = read_correspondence_cache(root_path)
    if cache_data is None:
        return stats

    fields, data_list = cache_data
    lang_field = str(lang) if lang is not None else ""
    remaining_rows: list[dict] = []

    for row in data_list:
        row_path_hash = row.get(PATH_CHECKSUM_COLUMN, "")
        if path_hash and row_path_hash != path_hash:
            remaining_rows.append(row)
            continue

        if lang_field:
            if lang_field in fields and row.get(lang_field, ""):
                row[lang_field] = ""
                stats.cleared_fields += 1
            if _row_has_any_language_values(row, fields):
                remaining_rows.append(row)
            else:
                stats.removed_rows += 1
        else:
            stats.removed_rows += 1

    if stats.removed_rows > 0 or stats.cleared_fields > 0:
        write_correspondence_cache(root_path, remaining_rows, fields)

    return stats
