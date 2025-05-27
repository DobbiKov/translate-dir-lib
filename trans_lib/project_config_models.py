from __future__ import annotations 

from collections import Counter
import os
from pathlib import Path
from typing import List, Optional, Any, Callable

from pydantic import BaseModel, Field, model_validator
from loguru import logger

from .enums import Language
from .errors import AddTranslatableFileError, NoSourceDirError, NoSourceLanguageError, FileDoesNotExistError


class FileModel(BaseModel):
    """A config for a file."""
    name: str
    path: Path
    translatable: bool = False

    class Config:
        arbitrary_types_allowed = True 

    def get_name(self) -> str:
        return self.name

    def get_path(self) -> Path:
        return self.path

    def is_translatable(self) -> bool:
        return self.translatable

class DirectoryModel(BaseModel):
    """A config representation of a directory."""
    name: str
    path: Path
    dirs: List[DirectoryModel] = Field(default_factory=list)
    files: List[FileModel] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def new_from_path(cls, path: Path) -> DirectoryModel:
        name = path.name
        return cls(name=name, path=path, dirs=[], files=[])

    def get_dir_name(self) -> str:
        return self.name

    def get_path(self) -> Path:
        return self.path

    def get_files(self) -> List[FileModel]: # Returns a copy
        return list(self.files)

    def get_dirs(self) -> List[DirectoryModel]: # Returns a copy
        return list(self.dirs)


class LangDir(BaseModel):
    """A master directory for a language."""
    dir: DirectoryModel
    language: Language

    def get_lang(self) -> Language:
        return self.language

    def get_dir(self) -> DirectoryModel:
        return self.dir
    
    def set_dir(self, directory: DirectoryModel) -> None:
        self.dir = directory


class ProjectConfig(BaseModel):
    """A struct representing a particular project's config."""
    name: str
    lang_dirs: List[LangDir] = Field(default_factory=list)
    src_dir: Optional[LangDir] = None

    @classmethod
    def new(cls, project_name: str) -> ProjectConfig:
        return cls(name=project_name, lang_dirs=[], src_dir=None)

    def get_name(self) -> str:
        return self.name

    def get_src_dir(self) -> Optional[LangDir]:
        return self.src_dir

    def get_lang_dirs(self) -> List[LangDir]: # Returns a copy
        return list(self.lang_dirs)

    def get_src_dir_path(self) -> Optional[Path]:
        if self.src_dir:
            return self.src_dir.get_dir().get_path()
        return None

    def get_target_dir_path_by_lang(self, lang: Language) -> Optional[Path]:
        for lang_dir_obj in self.lang_dirs:
            if lang_dir_obj.get_lang() == lang:
                return lang_dir_obj.get_dir().get_path()
        return None

    def update_src_dir_config(self, build_tree_func: Callable[[Path], DirectoryModel]) -> None:
        """
        Updates the source directory structure in the config
        """
        src_lang_dir  = self.get_src_dir()
        if src_lang_dir is None:
            raise NoSourceDirError("The source directory isn't set")
        dir_path = src_lang_dir.get_dir().get_path()
        lang = src_lang_dir.get_lang()

        old_dir = src_lang_dir.get_dir()
        logger.debug("old_dir: ", old_dir)
        new_dir = build_tree_func(dir_path)
        logger.debug("new_dir: ", new_dir)
        directory = compare_and_submit_dir_structures(old_dir, new_dir)
        logger.debug("res_dir: ", directory)
        self.src_dir = LangDir(dir=directory, language=lang)

    def set_src_dir_config(self, dir_path: Path, lang: Language, build_tree_func: Callable[[Path], DirectoryModel]) -> None:
        """
        Sets the source directory in the config.
        Requires a build_tree_func to construct the DirectoryModel.
        """
        directory = build_tree_func(dir_path)
        self.src_dir = LangDir(dir=directory, language=lang)

    def add_lang_dir_config(self, dir_path: Path, lang: Language, build_tree_func: Callable[[Path], DirectoryModel]) -> None:
        """
        Adds a target language directory to the config.
        Requires a build_tree_func.
        """
        directory = build_tree_func(dir_path)
        self.lang_dirs.append(LangDir(dir=directory, language=lang))

    def remove_lang_config(self, lang: Language) -> bool:
        """Removes a language directory from the config. Returns True if removed."""
        original_len = len(self.lang_dirs)
        self.lang_dirs = [ld for ld in self.lang_dirs if ld.get_lang() != lang]
        return len(self.lang_dirs) < original_len

    def analyze_and_update_lang_dirs(self, build_tree_func: Callable[[Path], DirectoryModel]) -> None:
        """
        Re-analyzes all language directories (source and target) and updates their structure.
        """
        if self.src_dir:
            src_dir_path = self.src_dir.get_dir().get_path()
            self.src_dir.set_dir(build_tree_func(src_dir_path))
        
        for lang_dir_obj in self.lang_dirs:
            path = lang_dir_obj.get_dir().get_path()
            lang_dir_obj.set_dir(build_tree_func(path))
            
    def _find_file_and_apply(self, dir_model: DirectoryModel, path: Path, func: Callable[[FileModel], None]) -> bool:
        """
        Helper to find a file and apply a function.
        Note: This modifies the FileModel in-place.
        """
        for file_obj in dir_model.files:
            # Compare resolved paths for robustness
            if os.path.samefile(file_obj.path.resolve(), path.resolve()):
                func(file_obj)
                return True
        
        for sub_dir_model in dir_model.dirs:
            if not path.is_relative_to(sub_dir_model.path):
                continue
            if self._find_file_and_apply(sub_dir_model, path, func):
                return True
        return False

    def _get_source_directory_model_for_modification(self) -> DirectoryModel:
        if not self.src_dir:
            raise AddTranslatableFileError(NoSourceLanguageError("Source language/directory not set."))
        return self.src_dir.dir


    def make_file_translatable(self, path: Path, translatable: bool) -> None:
        """Marks a file as translatable or untranslatable."""
        # Resolve path to ensure consistency
        resolved_path = path.resolve()

        def action(file_model: FileModel):
            file_model.translatable = translatable
        
        src_dir_model = self._get_source_directory_model_for_modification()

        if not self._find_file_and_apply(src_dir_model, resolved_path, action):
            raise AddTranslatableFileError(FileDoesNotExistError(f"File not found in source directory: {path}"))


    def get_translatable_files_paths(self) -> List[Path]:
        """Gets a list of paths for all translatable files in the source directory."""
        if not self.src_dir:
            return [] 

        translatable_files: List[Path] = []
        
        from collections import deque 
        
        queue: deque[DirectoryModel] = deque()
        queue.append(self.src_dir.dir)
        
        while queue:
            current_dir = queue.popleft()
            for file_obj in current_dir.files:
                if file_obj.is_translatable():
                    translatable_files.append(file_obj.path)
            for sub_dir_obj in current_dir.dirs:
                queue.append(sub_dir_obj)
                
        return translatable_files


def compare_and_submit_dir_structures(old_dir: DirectoryModel, new_dir: DirectoryModel) -> DirectoryModel:
    """
    Compares old directory structure and new one and returns the merge of both.
    If it encounters a file or a directory in both structures, it keeps the one
    from the old structure, if it encounters a directory or a file present in
    the new structure but not in the old, it will add it to the result.
    """
    return _compare_and_submit_dir_structs_inner(old_dir, new_dir) 

def _compare_and_submit_dir_structs_inner(old_dir: DirectoryModel, new_dir: DirectoryModel) -> DirectoryModel:
    new_model = DirectoryModel.new_from_path(new_dir.get_path())

    for new_file in new_dir.files:
        added = False
        for old_file in old_dir.files:
            if new_file.path == old_file.path: # if we found a file that is in the old structure and in the new one, we keep the old one
                new_model.files.append(old_file)
                added = True
        if not added: # if it is a new file, than we just add it to the result
            new_model.files.append(new_file)

    for new_subdir in new_dir.dirs:
        added = False
        for old_subdir in old_dir.dirs:
            if new_subdir.path == old_subdir.path: # if we find a directory that is in the old struct and in the new one, we will analyze it recursively and add the result
                res_subdir = _compare_and_submit_dir_structs_inner(old_subdir, new_subdir)
                new_model.dirs.append(res_subdir)
                added = True
        if not added: # if it is a new directory than we just add it to the result
            new_model.dirs.append(new_subdir)

    return new_model
