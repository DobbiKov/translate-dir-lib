import json
from pathlib import Path

import pytest

from trans_lib.enums import Language
from trans_lib.project_config_models import LangDir, ProjectConfig
from trans_lib.project_config_io import write_project_config
from trans_lib.project_manager import load_project
from trans_lib.constants import CONF_DIR, CONFIG_FILENAME


def test_config_stores_relative_paths(tmp_path):
    root = tmp_path
    src_dir = root / "src_en"
    tgt_dir = root / "proj_fr"
    src_dir.mkdir()
    tgt_dir.mkdir()
    file_path = src_dir / "doc.txt"
    file_path.write_text("hello", encoding="utf-8")

    config = ProjectConfig.new(project_name="proj")
    config.set_runtime_root_path(root)

    config.set_src_dir_config(src_dir, Language.ENGLISH)
    config.add_lang_dir_config(tgt_dir, Language.FRENCH)

    assert config.src_dir is not None
    assert config.src_dir.path == Path("src_en")
    assert config.lang_dirs[0].path == Path("proj_fr")

    assert config.get_src_dir_path() == src_dir.resolve()
    assert config.get_target_dir_path_by_lang(Language.FRENCH) == tgt_dir.resolve()

    config.make_file_translatable(file_path, True)
    assert config.translatable_files == [Path("src_en/doc.txt")]
    assert config.get_translatable_files() == [file_path.resolve()]


def test_config_handles_project_move(tmp_path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    (old_root / "src").mkdir()
    (new_root / "src").mkdir()

    config = ProjectConfig.new(project_name="proj")
    config.set_runtime_root_path(old_root)
    config.set_src_dir_config(old_root / "src", Language.ENGLISH)

    # Simulate loading the project from a new location.
    config.set_runtime_root_path(new_root)
    assert config.get_src_dir_path() == (new_root / "src").resolve()

    # Model dump should not persist any runtime root information.
    dumped = config.model_dump()
    assert "root_path" not in dumped


def test_runtime_root_must_be_set_before_using_paths(tmp_path):
    config = ProjectConfig.new(project_name="proj")
    with pytest.raises(ValueError):
        config.set_src_dir_config(tmp_path, Language.ENGLISH)


def test_rejects_paths_outside_root(tmp_path):
    project_root = tmp_path / "proj"
    external = tmp_path / "elsewhere"
    project_root.mkdir()
    external.mkdir()

    config = ProjectConfig.new(project_name="proj")
    config.set_runtime_root_path(project_root)

    with pytest.raises(ValueError):
        config.set_src_dir_config(external, Language.ENGLISH)


def test_normalizes_existing_absolute_entries(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    src_dir = root / "src"
    src_dir.mkdir()
    tgt_dir = root / "target"
    tgt_dir.mkdir()
    trans_file = src_dir / "note.md"
    trans_file.write_text("doc", encoding="utf-8")

    config = ProjectConfig.new(project_name="proj")
    config.lang_dirs.append(LangDir(language=Language.FRENCH, path=tgt_dir.resolve()))
    config.src_dir = LangDir(language=Language.ENGLISH, path=src_dir.resolve())
    config.translatable_files = [trans_file.resolve()]

    config.set_runtime_root_path(root)

    assert config.src_dir is not None
    assert config.src_dir.path == Path("src")
    assert config.lang_dirs[0].path == Path("target")
    assert config.translatable_files == [Path("src/note.md")]
    assert config.get_src_dir_path() == src_dir.resolve()
    assert config.get_target_dir_path_by_lang(Language.FRENCH) == tgt_dir.resolve()
    assert config.get_translatable_files() == [trans_file.resolve()]


def test_translatable_file_round_trip(tmp_path):
    root = tmp_path
    src_dir = root / "src"
    src_dir.mkdir()
    file_path = src_dir / "doc.txt"
    file_path.write_text("text", encoding="utf-8")

    config = ProjectConfig.new(project_name="proj")
    config.set_runtime_root_path(root)
    config.set_src_dir_config(src_dir, Language.ENGLISH)

    config.make_file_translatable(file_path, True)
    assert config.translatable_files == [Path("src/doc.txt")]
    assert config.get_translatable_files() == [file_path.resolve()]

    config.make_file_translatable(file_path, False)
    assert config.translatable_files == []


def test_load_project_rewrites_config_file(tmp_path):
    root = tmp_path / "proj"
    src_dir = root / "src"
    conf_dir = root / CONF_DIR
    root.mkdir()
    src_dir.mkdir()
    conf_dir.mkdir()

    config = ProjectConfig.new(project_name="proj")
    config.src_dir = LangDir(language=Language.ENGLISH, path=src_dir.resolve())

    config_path = conf_dir / CONFIG_FILENAME
    write_project_config(config_path, config)

    load_project(str(root))

    contents = json.loads(config_path.read_text(encoding="utf-8"))
    assert contents["src_dir"]["path"] == "src"
