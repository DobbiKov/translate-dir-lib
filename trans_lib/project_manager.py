import asyncio
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from .enums import Language
from .project_config_models import ProjectConfig, LangDir, DirectoryModel
from .project_config_io import (
    load_project_config,
    write_project_config,
    build_directory_tree,
    copy_untranslatable_files_recursive,
    remove_files_not_in_source_dir
)
from .doc_translator import translate_file_to_file_async # Using the async version
from .helpers import find_file_upwards
from .errors import (
    InitProjectError, InvalidPathError, ProjectAlreadyInitializedError, WriteConfigError as ConfigWriteError,
    LoadProjectError, NoConfigFoundError, LoadConfigError as ConfigLoadError,
    SetSourceDirError, DirectoryDoesNotExistError, NotADirectoryError as PathNotADirectoryError,
    AnalyzeDirError, LangAlreadyInProjectError,
    AddLanguageError, NoSourceLanguageError, LangDirExistsError,
    RemoveLanguageError, LangDirDoesNotExistError, TargetLanguageNotInProjectError,
    SyncFilesError, NoTargetLanguagesError, CopyFileDirError, AddTranslatableFileError,
    FileDoesNotExistError, GetTranslatableFilesError, TranslateFileError, UntranslatableFileError,
    TranslationProcessError
)

CONFIG_FILENAME = "trans_conf.json"
INTER_FILE_TRANSLATION_DELAY_SECONDS = 5 


class Project:
    """Manages a translation project."""
    
    root_path: Path
    config: ProjectConfig

    # Private constructor, use load() or create_new_for_init()
    def __init__(self, root_path: Path, config: ProjectConfig):
        """
        Private constructor, use load() or create_new_for_init()
        """
        self.root_path = root_path.resolve()
        self.config = config

    @property
    def config_file_path(self) -> Path:
        return self.root_path / CONFIG_FILENAME

    @classmethod
    def _create_new_for_init(cls, project_name: str, project_root_path: Path) -> 'Project':
        """Creates a new Project instance with a new config, for internal use by init_project."""
        abs_path = project_root_path.resolve()
        config = ProjectConfig.new(project_name=project_name)
        return cls(abs_path, config)

    def save_config(self) -> None:
        """Saves the current project configuration (writes to the config file)."""
        try:
            write_project_config(self.config_file_path, self.config)
        except ConfigWriteError as e:
            # Wrap in a more specific error if needed, or re-raise
            raise e # Or ProjectSaveConfigError(e)

    def _get_source_language(self) -> Optional[Language]:
        if self.config.src_dir:
            return self.config.src_dir.language
        return None

    def _get_target_languages(self) -> List[Language]:
        return [ld.language for ld in self.config.lang_dirs]

    def set_source_directory(self, dir_name: str, lang: Language) -> None:
        """Sets the source directory for translations."""
        source_dir_path = self.root_path / dir_name
        if not source_dir_path.exists():
            raise SetSourceDirError(DirectoryDoesNotExistError(f"Directory {source_dir_path} does not exist."))
        if not source_dir_path.is_dir():
            raise SetSourceDirError(PathNotADirectoryError(f"Path {source_dir_path} is not a directory."))

        resolved_source_dir_path = source_dir_path.resolve()

        # Check if lang is already in project (as src or tgt)
        if self._get_source_language() == lang:
            raise SetSourceDirError(LangAlreadyInProjectError(f"Language {lang} is already the source language."))
        if lang in self._get_target_languages():
            raise SetSourceDirError(LangAlreadyInProjectError(f"Language {lang} is already a target language."))

        try:
            self.config.set_src_dir_config(resolved_source_dir_path, lang, build_directory_tree)
            self.save_config()
        except IOError as e: # build_directory_tree or save_config can raise IOError
            raise SetSourceDirError(AnalyzeDirError(f"Error analyzing or saving config for source directory: {e}", e))
        except Exception as e: # Other errors from build_tree or Pydantic
             raise SetSourceDirError(AnalyzeDirError(f"Unexpected error setting source directory: {e}", e))


    def add_target_language(self, lang: Language) -> Path:
        """Adds a target language and creates its directory. Returns path to new lang dir."""
        src_lang = self._get_source_language()
        if not src_lang:
            raise AddLanguageError(NoSourceLanguageError("Cannot add target language: No source language set."))

        if lang == src_lang:
            raise AddLanguageError(LangAlreadyInProjectError("Cannot add language: It's already the source language."))
        if lang in self._get_target_languages():
            raise AddLanguageError(LangAlreadyInProjectError("Cannot add language: It's already a target language."))

        lang_dir_name = f"{self.config.name}{lang.get_dir_suffix()}"
        lang_dir_path = self.root_path / lang_dir_name
        
        if lang_dir_path.exists():
            raise AddLanguageError(LangDirExistsError(f"Directory {lang_dir_path} for language {lang} already exists."))

        try:
            lang_dir_path.mkdir(parents=True) # Create the directory
            resolved_lang_dir_path = lang_dir_path.resolve()
            self.config.add_lang_dir_config(resolved_lang_dir_path, lang, build_directory_tree)
            self.save_config()
            return resolved_lang_dir_path
        except IOError as e:
            # Clean up created directory if subsequent steps fail?
            # For now, let it be and raise error.
            raise AddLanguageError(f"IO error creating directory or saving config for language {lang}: {e}", e)
        except Exception as e:
             raise AddLanguageError(f"Unexpected error adding language {lang}: {e}", e)

    def remove_target_language(self, lang: Language) -> None:
        """Removes a target language and its directory."""
        target_dir_path = self.config.get_target_dir_path_by_lang(lang)
        if not target_dir_path:
            raise RemoveLanguageError(TargetLanguageNotInProjectError(f"Language {lang} is not a configured target language."))

        resolved_target_dir_path = target_dir_path.resolve()
        if not resolved_target_dir_path.exists() or not resolved_target_dir_path.is_dir():
            print(f"Warning: Language directory {resolved_target_dir_path} for {lang} not found or not a dir, removing from config only.")
            # raise RemoveLanguageError(LangDirDoesNotExistError(f"Directory {resolved_target_dir_path} for language {lang} does not exist."))

        try:
            removed_from_config = self.config.remove_lang_config(lang)
            if not removed_from_config:
                 # Should have been caught by get_target_dir_path_by_lang
                 raise RemoveLanguageError(TargetLanguageNotInProjectError(f"Language {lang} could not be removed from config (wasn't found)."))
            
            self.save_config()
            
            if resolved_target_dir_path.exists() and resolved_target_dir_path.is_dir():
                 shutil.rmtree(resolved_target_dir_path)
        except IOError as e:
            raise RemoveLanguageError(f"IO error removing directory or saving config for language {lang}: {e}", e)
        except ConfigWriteError as e:
            raise RemoveLanguageError(f"Failed to save config after removing language {lang}: {e}", e)


    def sync_untranslatable_files(self) -> None:
        """Copies untranslatable files from source to all target directories."""
        if not self.config.src_dir or not self.config.src_dir.dir:
            raise SyncFilesError(NoSourceLanguageError("Cannot sync: No source directory configured."))
        if not self.config.lang_dirs:
            raise SyncFilesError(NoTargetLanguagesError("Cannot sync: No target languages configured."))

        self.update_project_structure()
        source_lang_dir_model = self.config.src_dir.dir
        # This path is already absolute from when it was set.
        source_root_disk_path = source_lang_dir_model.get_path() 

        for target_lang_dir_obj in self.config.lang_dirs:
            target_root_disk_path = target_lang_dir_obj.get_dir().get_path()
            print(f"Syncing untranslatable files from {source_root_disk_path.name} to {target_root_disk_path.name}...")
            try:
                remove_files_not_in_source_dir(
                        from_dir_root_path=source_root_disk_path,
                        to_dir_root_path=target_root_disk_path,
                        source_dir_structure=source_lang_dir_model 
                )
                copy_untranslatable_files_recursive(
                    from_dir_root_path=source_root_disk_path,
                    to_dir_root_path=target_root_disk_path,
                    source_dir_structure=source_lang_dir_model 
                )
            except CopyFileDirError as e:
                raise SyncFilesError(f"Error copying files to {target_root_disk_path.name}: {e}", e)
            except Exception as e: # Other unexpected errors
                raise SyncFilesError(f"Unexpected error syncing to {target_root_disk_path.name}: {e}", e)

        # After copying, re-analyze target directories to update their config structure
        try:
            # Only need to update target LangDir models. Source is unchanged by this op.
            for lang_dir_obj in self.config.lang_dirs:
                path = lang_dir_obj.get_dir().get_path()
                lang_dir_obj.set_dir(build_directory_tree(path))
            self.save_config()
        except IOError as e:
            raise SyncFilesError(ConfigWriteError(f"Error re-analyzing target dirs or saving config after sync: {e}", e))


    def set_file_translatability(self, file_path_str: str, translatable: bool) -> None:
        """Marks a file in the source directory as translatable or untranslatable."""
        try:
            # Ensure file_path is absolute and exists before passing to config
            file_path = Path(file_path_str).resolve(strict=True)
        except FileNotFoundError:
            raise AddTranslatableFileError(FileDoesNotExistError(f"File {file_path_str} not found."))
        
        if not self.config.src_dir:
             raise AddTranslatableFileError(NoSourceLanguageError("Cannot modify file: No source directory set."))

        # The logic to find and modify the file model is in ProjectConfig
        try:
            self.config.make_file_translatable(file_path, translatable)
            self.save_config()
        except AddTranslatableFileError as e: # Catches NoSourceLang, NoFile from Pydantic model
            raise e
        except ConfigWriteError as e:
            raise AddTranslatableFileError(f"Error saving config after changing file translatability: {e}", e)


    def get_translatable_files(self) -> List[Path]:
        """Returns a list of absolute paths to translatable files in the source directory."""
        if not self.config.src_dir:
            raise GetTranslatableFilesError(NoSourceLanguageError("No source language set, cannot get translatable files."))
        return self.config.get_translatable_files_paths()

    def update_project_structure(self: 'Project') -> None:
        """
        Updates source directory structure (if for example it has been changed since the initialization of the project)
        """
        self.config.update_src_dir_config(build_directory_tree)
        self.save_config()


    async def translate_single_file(self, file_path_str: str, target_lang: Language) -> None:
        """Translates a single specified file to the target language."""
        try:
            file_path = Path(file_path_str).resolve(strict=True)
        except FileNotFoundError:
            raise TranslateFileError(FileDoesNotExistError(f"File {file_path_str} not found."))

        source_language = self._get_source_language()
        if source_language is None:
            raise TranslateFileError(NoSourceLanguageError("Cannot translate: No source language set."))
        if target_lang not in self._get_target_languages():
            raise TranslateFileError(TargetLanguageNotInProjectError(f"Cannot translate: Target language {target_lang} not in project."))

        translatable_files = self.get_translatable_files() # Checks for src_dir internally
        if file_path not in translatable_files:
            raise TranslateFileError(UntranslatableFileError(f"File {file_path} is not marked as translatable."))

        if not self.config.src_dir: # Should be caught by get_translatable_files
            raise TranslateFileError(NoSourceLanguageError("Critical: Source directory vanished"))

        src_dir_root_path = self.config.src_dir.dir.get_path()
        target_lang_dir_config = next((ld for ld in self.config.lang_dirs if ld.language == target_lang), None)
        
        if not target_lang_dir_config: # Should be caught by target_lang check
             raise TranslateFileError(TargetLanguageNotInProjectError("Critical: Target language config vanished."))

        target_dir_root_path = target_lang_dir_config.dir.get_path()

        try:
            relative_path = file_path.relative_to(src_dir_root_path)
        except ValueError:
            # This means file_path, though translatable, is not under src_dir_root_path
            # This should ideally not happen if config is consistent.
            raise TranslateFileError(FileDoesNotExistError(f"File {file_path} is translatable but not in source root {src_dir_root_path}."))

        target_file_path = target_dir_root_path / relative_path
        
        print(f"Translating {file_path.name} to {target_lang.value} -> {target_file_path}...")
        try:
            logger.debug("im here")
            await translate_file_to_file_async(self.root_path, file_path, source_language, target_file_path, target_lang)
            await asyncio.sleep(INTER_FILE_TRANSLATION_DELAY_SECONDS)
        except TranslationProcessError as e:
            raise TranslateFileError(f"Translation process failed for {file_path.name}: {e}", e)
        except IOError as e: # From file writing in translate_file_to_file_async
            raise TranslateFileError(f"IO error during translation of {file_path.name}: {e}", e)


    async def translate_all_for_language(self, target_lang: Language) -> None:
        """Translates all translatable files to the specified target language."""
        translatable_files = self.get_translatable_files()
        if not translatable_files:
            print(f"No translatable files found for language {target_lang.value}.")
            return

        print(f"Starting translation of {len(translatable_files)} files to {target_lang.value}...")
        for i, file_path in enumerate(translatable_files):
            print(f"--- File {i+1}/{len(translatable_files)} ---")
            try:
                await self.translate_single_file(str(file_path), target_lang)
            except TranslateFileError as e:
                print(f"ERROR translating {file_path.name}: {e}. Skipping this file.")
            # The sleep is now inside translate_single_file, after each successful API call.
        print(f"Finished translation to {target_lang.value}.")


# --- Module-level functions for project init and load ---

def init_project(project_name: str, root_dir_str: str) -> Project:
    """Initializes a new project configuration in the specified directory."""
    root_path = Path(root_dir_str)
    if not root_path.is_dir(): # Also checks existence
        raise InitProjectError(InvalidPathError(f"Invalid path: {root_dir_str} is not an existing directory."))
    
    abs_root_path = root_path.resolve()
    config_file = abs_root_path / CONFIG_FILENAME
    
    if config_file.exists():
        raise InitProjectError(ProjectAlreadyInitializedError(f"Project already initialized at {abs_root_path} ({CONFIG_FILENAME} exists)."))

    try:
        # Create a Project instance with an empty config, then save it.
        project = Project._create_new_for_init(project_name, abs_root_path)
        project.save_config() # This writes the initial trans_conf.json
        print(f"Project '{project_name}' initialized at {abs_root_path}")
        return project
    except ConfigWriteError as e:
        raise InitProjectError(f"Failed to write initial config file: {e}", e)
    except Exception as e:
        raise InitProjectError(f"An unexpected error occurred during project initialization: {e}", e)


def load_project(path_str: str) -> Project:
    """Loads an existing project from the given path (can be project root or any child path)."""
    start_path = Path(path_str).resolve()
    
    config_file_path = find_file_upwards(start_path, CONFIG_FILENAME)
    if not config_file_path:
        raise LoadProjectError(NoConfigFoundError(f"No '{CONFIG_FILENAME}' found in or above {start_path}."))

    project_root = config_file_path.parent
    
    try:
        config_model = load_project_config(config_file_path)
        project = Project(project_root, config_model)
        print(f"Project '{project.config.name}' loaded from {project_root}")
        return project
    except ConfigLoadError as e:
        raise LoadProjectError(f"Failed to load project configuration: {e}", e)
    except Exception as e:
        raise LoadProjectError(f"An unexpected error occurred during project loading: {e}", e)
