from __future__ import annotations 

import os
from pathlib import Path
from typing import List, Optional, Callable

from pydantic import BaseModel, Field
from loguru import logger

from .enums import Language
from .errors import AddTranslatableFileError, NoSourceLanguageError, FileDoesNotExistError


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
    language: Language
    path: Path

    def get_lang(self) -> Language:
        return self.language
    def get_path(self) -> Path:
        return self.path


class ProjectConfig(BaseModel):
    """A struct representing a particular project's config."""
    name: str
    lang_dirs: List[LangDir] = Field(default_factory=list)
    src_dir: Optional[LangDir] = None
    root_path: Path = Path()
    translatable_files: list[Path] = []

    @classmethod
    def new(cls, project_name: str, root_path: Path) -> ProjectConfig:
        return cls(name=project_name, lang_dirs=[], src_dir=None, root_path=root_path, translatable_files=[])

    def get_name(self) -> str:
        return self.name

    def get_root_path(self) -> Path:
        return self.root_path

    def get_src_dir(self) -> Optional[LangDir]:
        return self.src_dir

    def get_lang_dirs(self) -> List[LangDir]: # Returns a copy
        return list(self.lang_dirs)

    def get_src_dir_path(self) -> Optional[Path]:
        if self.src_dir:
            return self.src_dir.get_path()
        return None

    def get_target_dir_path_by_lang(self, lang: Language) -> Optional[Path]:
        for lang_dir_obj in self.lang_dirs:
            if lang_dir_obj.get_lang() == lang:
                return lang_dir_obj.get_path()
        return None

    def rearrange_project(self, curr_root: Path, old_root: Path) -> None:
        """
        Rewrite all the paths accordingly to the new root path.
        This method is called when the project directory has been moved.
        """
        def _update_path(path: Path, new_root: Path, previous_root: Path) -> Path:
            """
            Helper function to update path if the root path has been changed
            """
            try:
                relative_dir_path = path.relative_to(previous_root)
                return new_root / relative_dir_path
            except ValueError:
                logger.warning(f"Path {path} is not within the old project root {previous_root}. Skipping update for this item.")
                return path

        # Update the project's own root_path
        self.root_path = curr_root

        # Update the source directory, if it exists
        if self.src_dir:
            self.src_dir.path = _update_path(self.src_dir.path, curr_root, old_root)

        # Update all target language directories
        for lang_dir in self.lang_dirs:
            lang_dir.path = _update_path(lang_dir.path, curr_root, old_root)

        for i in range(len( self.translatable_files )):
            self.translatable_files[i] = _update_path(self.translatable_files[i], curr_root, old_root)



    def set_src_dir_config(self, dir_path: Path, lang: Language) -> None:
        """
        Sets the source directory in the config.
        """
        self.src_dir = LangDir(language=lang, path=dir_path)

    def add_lang_dir_config(self, dir_path: Path, lang: Language) -> None:
        """
        Adds a target language directory to the config.
        """
        self.lang_dirs.append(LangDir(language=lang, path=dir_path))

    def remove_lang_config(self, lang: Language) -> bool:
        """Removes a language directory from the config. Returns True if removed."""
        original_len = len(self.lang_dirs)
        self.lang_dirs = [ld for ld in self.lang_dirs if ld.get_lang() != lang]
        return len(self.lang_dirs) < original_len
            
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

    def make_file_translatable(self, path: Path, translatable: bool) -> None:
        """Marks a file as translatable or untranslatable."""
        # Resolve path to ensure consistency
        resolved_path = path.resolve()

        src_dir = self.src_dir
        if src_dir is None:
            raise AddTranslatableFileError(NoSourceLanguageError())

        if not translatable:
            # TODO: remove from translatable files list
            if resolved_path not in self.translatable_files:
                raise AddTranslatableFileError("This file is not marked as translatable!")
            self.translatable_files.remove(resolved_path)
        

        src_dir_path = src_dir.get_path().resolve()

        if not resolved_path.relative_to(src_dir_path):
            raise AddTranslatableFileError(f"The provided file {path} is not in the source directory!")
        if not resolved_path.exists() or not resolved_path.is_file():
            raise AddTranslatableFileError(FileDoesNotExistError("This file does not exist"))
        
        if resolved_path not in self.translatable_files:
            self.translatable_files.append(resolved_path)

    def get_translatable_files(self) -> List[Path]:
        """Gets a list of all the translatable files in the source directory."""
        if not self.src_dir:
            return [] 

        return self.translatable_files
