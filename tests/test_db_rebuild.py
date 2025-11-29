from pathlib import Path

import nbformat

from trans_lib.enums import Language
from trans_lib.helpers import calculate_checksum
from trans_lib.project_config_models import ProjectConfig
from trans_lib.project_manager import Project
from trans_lib.translation_store.translation_store import TranslationStoreCsv


def _write_notebook(path: Path, cells: list[nbformat.NotebookNode]) -> None:
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nbformat.write(nb, path)


def test_rebuild_translation_database_from_notebook(tmp_path):
    project_root = tmp_path / "proj"
    src_dir = project_root / "src_en"
    tgt_dir = project_root / "proj_fr"
    src_dir.mkdir(parents=True)
    tgt_dir.mkdir(parents=True)
    (project_root / ".translate_dir").mkdir(parents=True)

    source_file = src_dir / "notebook.ipynb"
    target_file = tgt_dir / "notebook.ipynb"

    source_cells = [
        nbformat.v4.new_markdown_cell("Alpha chunk"),
        nbformat.v4.new_markdown_cell("Beta chunk"),
    ]
    _write_notebook(source_file, source_cells)

    translated_texts = ["Alpha traduit", "Beta traduit"]
    target_cells = []
    for cell, translated in zip(source_cells, translated_texts):
        checksum = calculate_checksum(cell["source"])
        new_cell = nbformat.v4.new_markdown_cell(translated)
        new_cell.metadata = {"src_checksum": checksum}
        target_cells.append(new_cell)
    _write_notebook(target_file, target_cells)

    config = ProjectConfig.new(project_name="proj")
    config.set_runtime_root_path(project_root)
    config.set_src_dir_config(src_dir, Language.ENGLISH)
    config.add_lang_dir_config(tgt_dir, Language.FRENCH)
    config.make_file_translatable(source_file, True)

    project = Project(project_root, config)
    project.rebuild_translation_database()

    store = TranslationStoreCsv(project_root)
    relative_path = source_file.relative_to(src_dir).as_posix()

    for original_cell, translated in zip(source_cells, translated_texts):
        checksum = calculate_checksum(original_cell["source"])
        cached = store.lookup(checksum, Language.ENGLISH, Language.FRENCH, relative_path)
        assert cached == translated
