from __future__ import annotations 

import os
from pathlib import Path
from typing import List, Optional, Callable
from unified_model_caller import enums as unif_enums

from pydantic import BaseModel, Field, ConfigDict
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
    root_path: Path | None = Field(default=None, exclude=True)

    def get_lang(self) -> Language:
        return self.language

    def attach_root_path(self, root_path: Path) -> None:
        """Stores the project root used to resolve the relative path."""
        self.root_path = root_path.resolve()

    def get_path(self) -> Path:
        if self.path.is_absolute() or not self.root_path:
            return self.path
        return (self.root_path / self.path).resolve()


class ProjectConfig(BaseModel):
    """A struct representing a particular project's config."""
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    lang_dirs: List[LangDir] = Field(default_factory=list)
    src_dir: Optional[LangDir] = None
    translatable_files: List[Path] = Field(default_factory=list)
    runtime_root_path: Path | None = Field(default=None, exclude=True)

    llm_service: str = "google"
    llm_model: str = "gemini-2.0-flash"

    @classmethod
    def new(cls, project_name: str, description: str = "") -> ProjectConfig:
        return cls(
            name=project_name,
            description=description,
            lang_dirs=[],
            src_dir=None,
        )

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def set_description(self, description: str) -> None:
        self.description = description

    def get_src_dir(self) -> Optional[LangDir]:
        return self.src_dir

    def get_lang_dirs(self) -> List[LangDir]: # Returns a copy
        return list(self.lang_dirs)

    def get_src_dir_path(self) -> Optional[Path]:
        if self.src_dir:
            self._attach_root_if_missing(self.src_dir)
            return self.src_dir.get_path()
        return None

    def get_llm_service(self) -> str:
        return self.llm_service

    def get_llm_model(self) -> str:
        return self.llm_model

    def get_target_dir_path_by_lang(self, lang: Language) -> Optional[Path]:
        for lang_dir_obj in self.lang_dirs:
            if lang_dir_obj.get_lang() == lang:
                self._attach_root_if_missing(lang_dir_obj)
                return lang_dir_obj.get_path()
        return None


    def set_src_dir_config(self, dir_path: Path, lang: Language) -> None:
        """
        Sets the source directory in the config.
        """
        rel_path = self._relativize_to_runtime_root(dir_path)
        lang_dir = LangDir(language=lang, path=rel_path)
        lang_dir.attach_root_path(self._get_runtime_root())
        self.src_dir = lang_dir

    def add_lang_dir_config(self, dir_path: Path, lang: Language) -> None:
        """
        Adds a target language directory to the config.
        """
        rel_path = self._relativize_to_runtime_root(dir_path)
        lang_dir = LangDir(language=lang, path=rel_path)
        lang_dir.attach_root_path(self._get_runtime_root())
        self.lang_dirs.append(lang_dir)

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

    def set_llm_service_with_model(self, service: str, model: str) -> None:
        """Set's LLM service and model"""
        corr_service = unif_enums.Service.from_str(service)
        self.llm_service = service
        self.llm_model = model

    def make_file_translatable(self, path: Path, translatable: bool) -> None:
        """Marks a file as translatable or untranslatable."""
        # Resolve path to ensure consistency
        resolved_path = path.resolve()

        src_dir = self.src_dir
        if src_dir is None:
            raise AddTranslatableFileError(NoSourceLanguageError())

        if not translatable:
            rel_path = self._relativize_to_runtime_root(resolved_path)
            if rel_path not in self.translatable_files:
                raise AddTranslatableFileError("This file is not marked as translatable!")
            self.translatable_files.remove(rel_path)
            return  # Exit early after removal - don't continue to add logic
        

        src_dir_path = src_dir.get_path().resolve()

        try:
            resolved_path.relative_to(src_dir_path)
        except ValueError:
            raise AddTranslatableFileError(f"The provided file {path} is not in the source directory!")
        if not resolved_path.exists() or not resolved_path.is_file():
            raise AddTranslatableFileError(FileDoesNotExistError("This file does not exist"))
        
        rel_path = self._relativize_to_runtime_root(resolved_path)
        if rel_path not in self.translatable_files:
            self.translatable_files.append(rel_path)

    def get_translatable_files(self) -> List[Path]:
        """Gets a list of all the translatable files in the source directory."""
        if not self.src_dir:
            return [] 
        root = self._get_runtime_root()
        resolved_files: List[Path] = []
        for stored_path in self.translatable_files:
            if stored_path.is_absolute():
                resolved_files.append(stored_path)
            else:
                resolved_files.append((root / stored_path).resolve())
        return resolved_files

    def set_runtime_root_path(self, root_path: Path) -> bool:
        """Sets the runtime root used to resolve stored relative paths."""
        resolved_root = root_path.resolve()
        self.runtime_root_path = resolved_root

        changed = False
        if self._normalize_lang_dir(self.src_dir, resolved_root):
            changed = True

        for lang_dir in self.lang_dirs:
            if self._normalize_lang_dir(lang_dir, resolved_root):
                changed = True

        normalized_files: List[Path] = []
        for path in self.translatable_files:
            normalized = self._ensure_relative_path(path, resolved_root)
            if normalized != path:
                changed = True
            normalized_files.append(normalized)
        self.translatable_files = normalized_files
        return changed

    def _normalize_lang_dir(self, lang_dir: Optional[LangDir], reference_root: Path) -> bool:
        if not lang_dir:
            return False
        normalized_path = self._ensure_relative_path(lang_dir.path, reference_root)
        changed = normalized_path != lang_dir.path
        lang_dir.path = normalized_path
        lang_dir.attach_root_path(self.runtime_root_path or reference_root)
        return changed

    def _get_runtime_root(self) -> Path:
        if self.runtime_root_path:
            return self.runtime_root_path
        raise ValueError("Project root path is not set, cannot resolve relative paths.")

    def _relativize_to_runtime_root(self, path: Path) -> Path:
        root = self._get_runtime_root()
        resolved_path = path.resolve()
        try:
            return resolved_path.relative_to(root)
        except ValueError:
            raise ValueError(f"Path {resolved_path} is not under the project root {root}")

    def _ensure_relative_path(self, path: Path, reference_root: Path) -> Path:
        if not path.is_absolute():
            return path
        try:
            return path.relative_to(reference_root)
        except ValueError:
            logger.warning(
                f"Path {path} is not within the project root {reference_root}. Keeping absolute path in config."
            )
            return path

    def _attach_root_if_missing(self, lang_dir: Optional[LangDir]) -> None:
        if lang_dir and not lang_dir.root_path:
            lang_dir.attach_root_path(self._get_runtime_root())
