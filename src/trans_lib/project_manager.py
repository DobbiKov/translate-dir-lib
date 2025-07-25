import os
import shutil
from pathlib import Path
from typing import List, Optional

from loguru import logger

from trans_lib.doc_corrector import correct_file_translation
from trans_lib.translation_store.translation_store import TranslationStoreCsv
from trans_lib.vocab_list import VocabList

from .enums import Language
from .project_config_models import ProjectConfig, LangDir
from .project_config_io import (
    load_project_config,
    write_project_config,
    copy_untranslatable_files_recursive
)
from .doc_translator import translate_file_to_file_async # Using the async version
from .helpers import find_dir_upwards
from .constants import CONF_DIR, CONFIG_FILENAME
from .errors import (
    CorrectTranslationError, CorrectingTranslationError, InitProjectError, InvalidPathError, NoSourceFileError, ProjectAlreadyInitializedError, SetLLMServiceError, WriteConfigError as ConfigWriteError,
    LoadProjectError, NoConfigFoundError, LoadConfigError as ConfigLoadError,
    SetSourceDirError, DirectoryDoesNotExistError, NotADirectoryError as PathNotADirectoryError,
    AnalyzeDirError, LangAlreadyInProjectError,
    AddLanguageError, NoSourceLanguageError, LangDirExistsError,
    RemoveLanguageError, TargetLanguageNotInProjectError,
    SyncFilesError, NoTargetLanguagesError, CopyFileDirError, AddTranslatableFileError,
    FileDoesNotExistError, GetTranslatableFilesError, TranslateFileError, UntranslatableFileError,
    TranslationProcessError
)


# TODO: add refine translation command

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
        return self.root_path / CONF_DIR / CONFIG_FILENAME

    @property
    def config_dir_path(self) -> Path:
        return self.root_path / CONF_DIR

    @classmethod
    def _create_new_for_init(cls, project_name: str, project_root_path: Path) -> 'Project':
        """Creates a new Project instance with a new config, for internal use by init_project."""
        abs_path = project_root_path.resolve()
        config = ProjectConfig.new(project_name=project_name, root_path=project_root_path)
        return cls(abs_path, config)

    def save_config(self) -> None:
        """Saves the current project configuration (writes to the config file)."""
        try:
            os.makedirs(self.config_dir_path, exist_ok=True)
            write_project_config(self.config_file_path, self.config)
        except ConfigWriteError as e:
            # Wrap in a more specific error if needed, or re-raise
            raise e # Or ProjectSaveConfigError(e)

    def _get_source_language(self) -> Optional[Language]:
        if self.config.src_dir:
            return self.config.src_dir.language
        return None

    def _get_target_language_dirs(self) -> List[LangDir]:
        return self.config.get_lang_dirs()

    def _get_target_languages(self) -> List[Language]:
        return [ld.language for ld in self.config.lang_dirs]
    
    def get_source_langugage(self) -> Language:
        """
        Returns a source language of the project if such is set, otherwise raises an exception.
        """
        res = self._get_source_language()
        if res is None:
            raise NoSourceLanguageError
        return res

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
            self.config.set_src_dir_config(resolved_source_dir_path, lang)
            self.save_config()
        except IOError as e: # build_directory_tree or save_config can raise IOError
            raise SetSourceDirError(AnalyzeDirError(f"Error analyzing or saving config for source directory: {e}", e))
        except Exception as e: # Other errors from build_tree or Pydantic
             raise SetSourceDirError(AnalyzeDirError(f"Unexpected error setting source directory: {e}", e))


    def add_target_language(self, lang: Language, tgt_dir: Path | None = None) -> Path:
        """
        Adds a target language to the project.

        If a directory path is provided, it will be used as the target language's directory.
        If no directory is provided, a new one will be created automatically, and its full path will be returned.
        """
        src_lang = self._get_source_language()
        if not src_lang:
            raise AddLanguageError(NoSourceLanguageError("Cannot add target language: No source language set."))

        if lang == src_lang:
            raise AddLanguageError(LangAlreadyInProjectError("Cannot add language: It's already the source language."))

        if tgt_dir is not None:
            if not tgt_dir.exists():
                raise AddLanguageError(InvalidPathError(f"The provided directory {tgt_dir} does not exist!"))
            if not os.path.isdir(tgt_dir):
                raise AddLanguageError(InvalidPathError(f"The provided path {tgt_dir} must be a path to a directory!"))

            resolved_lang_dir_path = tgt_dir.resolve()

            if not resolved_lang_dir_path.is_relative_to(self.root_path):
                raise AddLanguageError(InvalidPathError(f"{tgt_dir} must be inside the project root"))

            try:
                self.config.remove_lang_config(lang)
                self.config.add_lang_dir_config(resolved_lang_dir_path, lang)
                self.save_config()
                return resolved_lang_dir_path
            except IOError as e:
                # Clean up created directory if subsequent steps fail?
                # For now, let it be and raise error.
                raise AddLanguageError(f"Error on saving config for language {lang}: {e}", e)
            except Exception as e:
                 raise AddLanguageError(f"Unexpected error adding language {lang} and setting directory {tgt_dir}: {e}", e)
        else:
            if lang in self._get_target_languages():
                raise AddLanguageError(LangAlreadyInProjectError("Cannot add language: It's already a target language."))

            lang_dir_name = f"{self.config.name}{lang.get_dir_suffix()}"
            lang_dir_path = self.root_path / lang_dir_name
            
            if lang_dir_path.exists():
                raise AddLanguageError(LangDirExistsError(f"Directory {lang_dir_path} for language {lang} already exists."))

            try:
                lang_dir_path.mkdir(parents=True) # Create the directory
                resolved_lang_dir_path = lang_dir_path.resolve()
                self.config.add_lang_dir_config(resolved_lang_dir_path, lang)
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


    def sync_untranslatable_files(self) -> None: # TODO: 
        """Copies untranslatable files from source to all target directories."""
        if not self.config.src_dir:
            raise SyncFilesError(NoSourceLanguageError("Cannot sync: No source directory configured."))
        if not self.config.lang_dirs:
            raise SyncFilesError(NoTargetLanguagesError("Cannot sync: No target languages configured."))

        # This path is already absolute from when it was set.
        source_root_disk_path = self.config.src_dir.get_path() 

        for target_lang_dir in self.config.lang_dirs:
            target_root_disk_path = target_lang_dir.get_path()
            print(f"Syncing untranslatable files from {source_root_disk_path.name} to {target_root_disk_path.name}...")
            try:
                copy_untranslatable_files_recursive(
                    from_dir_root_path=source_root_disk_path,
                    to_dir_root_path=target_root_disk_path,
                    translatable_files=self.get_translatable_files()
                )
            except CopyFileDirError as e:
                raise SyncFilesError(f"Error copying files to {target_root_disk_path.name}: {e}", e)
            except Exception as e: # Other unexpected errors
                raise SyncFilesError(f"Unexpected error syncing to {target_root_disk_path.name}: {e}", e)

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
        """Returns a list of translatable files in the source directory."""
        if not self.config.src_dir:
            raise GetTranslatableFilesError(NoSourceLanguageError("No source language set, cannot get translatable files."))
        return self.config.get_translatable_files()

    def set_llm_service_and_model(self, service: str, model: str) -> None:
        """Sets the service and the model that will be used for translation."""
        try:
            self.config.set_llm_service_with_model(service, model)
            self.save_config()
        except Exception as e: # Other errors from build_tree or Pydantic
            raise SetLLMServiceError(f"Error while setting llm service: {e}")

    def _find_correspondent_translatable_file(self, target_path: Path) -> Path | None:
        """
        Returns a correspondent source language translatable file for the given translated one or None
        """
        trans_files = self.get_translatable_files()
        file_name = target_path.name
        for file in trans_files:
            if file.name == file_name:
                return file
        return None

    def _correct_translation_file(self, target_path: Path, target_lang: Language) -> None:
        """Corrects the translation of a single specified file."""
        print(f"Verifying {target_path.name} for the corrected translations ...")
        source_language = self._get_source_language()
        if source_language is None:
            raise CorrectTranslationError(NoSourceLanguageError("Cannot find the source file: No source language set."))
        try:
            if correct_file_translation(self.root_path, target_path, target_lang, source_language):
                print(f"Successfully corrected the translation in {target_path.name}")
            else:
                print("The file doesn't need any corrections to be saved")
        except CorrectingTranslationError as e:
            raise CorrectTranslationError(f"Correcting process failed for {target_path.name}: {e}", e)
        except IOError as e: # From file writing in translate_file_to_file_async
            raise CorrectTranslationError(f"IO error during correction of {target_path.name}: {e}", e)

    def correct_translation_for_lang(self, target_lang: Language) -> None:
        """
        Corrects translation (updates the translation DB) for the given language
        """
        if target_lang not in self._get_target_languages():
            raise CorrectTranslationError(TargetLanguageNotInProjectError(f"Cannot correct translation: Target language {target_lang} not in project."))
        source_language = self._get_source_language()
        src_dir = self.config.src_dir
        if source_language is None or src_dir is None:
            raise CorrectTranslationError(NoSourceLanguageError("Cannot find the source file: No source language set."))
        src_path = src_dir.get_path()
        translatable_files = self.get_translatable_files()   
        target_lang_dir_config = next((ld for ld in self.config.lang_dirs if ld.language == target_lang), None)
        
        if not target_lang_dir_config: # Should be caught by target_lang check
             raise CorrectTranslationError(TargetLanguageNotInProjectError("Critical: Target language config vanished."))
        tgt_lang_dir = target_lang_dir_config.get_path()
        translated_pathes = [tgt_lang_dir.joinpath(path.relative_to(src_path)) for path in translatable_files]
        for tr_path in translated_pathes:
            self._correct_translation_file(tr_path, target_lang)

    def correct_translation_single_file(self, file_path_str: str) -> None:
        """
        Corrects translation (updates the translation DB) for a given file
        """
        try:
            file_path = Path(file_path_str).resolve(strict=True)
        except FileNotFoundError:
            raise CorrectTranslationError(FileDoesNotExistError(f"File {file_path_str} not found."))

        source_language = self._get_source_language()
        if source_language is None:
            raise CorrectTranslationError(NoSourceLanguageError("Cannot find the source file: No source language set."))
        target_lang_dirs = self._get_target_language_dirs()

        src_lang_dir = self.config.src_dir
        if src_lang_dir is None:
            raise CorrectTranslationError(NoSourceLanguageError("Cannot find the source file: No source language set."))
        root_path = self.root_path
        if not file_path.is_relative_to(root_path):
            raise CorrectTranslationError(UntranslatableFileError("The file doesn't have any correspondent source translatable file"))

        target_lang = None
        for tgt_lang_dir in target_lang_dirs:
            if file_path.is_relative_to(tgt_lang_dir.get_path()):
                target_lang = tgt_lang_dir.language
                break

        if target_lang is None:
            raise CorrectTranslationError(UntranslatableFileError("The file doesn't have any correspondent source translatable file"))

        if target_lang not in self._get_target_languages():
            raise CorrectTranslationError(TargetLanguageNotInProjectError(f"Cannot correct translation: Target language {target_lang} not in project."))

        src_file = self._find_correspondent_translatable_file(file_path) # Checks for src_dir internally
        if src_file is None:
            raise CorrectTranslationError(NoSourceFileError(f"There's no source file for the given {file_path_str}"))

        if not self.config.src_dir: # Should be caught by get_translatable_files
            raise CorrectTranslationError(NoSourceLanguageError("Critical: Source directory vanished"))

        target_lang_dir_config = next((ld for ld in self.config.lang_dirs if ld.language == target_lang), None)
        
        if not target_lang_dir_config: # Should be caught by target_lang check
             raise CorrectTranslationError(TargetLanguageNotInProjectError("Critical: Target language config vanished."))

        self._correct_translation_file(file_path, target_lang)

    def get_llm_service(self) -> str:
        return self.config.get_llm_service()
    def get_llm_model(self) -> str:
        return self.config.get_llm_model()

    async def translate_single_file(self, file_path_str: str, target_lang: Language, vocab_list: VocabList | None) -> None:
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

        src_dir_root_path = self.config.src_dir.get_path()
        target_lang_dir_config = next((ld for ld in self.config.lang_dirs if ld.language == target_lang), None)
        
        if not target_lang_dir_config: # Should be caught by target_lang check
             raise TranslateFileError(TargetLanguageNotInProjectError("Critical: Target language config vanished."))

        target_dir_root_path = target_lang_dir_config.get_path()

        try:
            relative_path = file_path.relative_to(src_dir_root_path)
        except ValueError:
            # This means file_path, though translatable, is not under src_dir_root_path
            # This should ideally not happen if config is consistent.
            raise TranslateFileError(FileDoesNotExistError(f"File {file_path} is translatable but not in source root {src_dir_root_path}."))

        target_file_path = target_dir_root_path / relative_path
        
        print(f"Translating {file_path.name} to {target_lang.value} -> {target_file_path}...")
        try:
            await translate_file_to_file_async(self.root_path, file_path, source_language, target_file_path, target_lang, vocab_list, self.get_llm_service(), self.get_llm_model())
        except TranslationProcessError as e:
            raise TranslateFileError(f"Translation process failed for {file_path.name}: {e}", e)
        except IOError as e: # From file writing in translate_file_to_file_async
            raise TranslateFileError(f"IO error during translation of {file_path.name}: {e}", e)


    async def translate_all_for_language(self, target_lang: Language, vocab_list: VocabList | None) -> None:
        """Translates all translatable files to the specified target language."""
        translatable_files = self.get_translatable_files()
        if not translatable_files:
            print(f"No translatable files found for language {target_lang.value}.")
            return

        print(f"Starting translation of {len(translatable_files)} files to {target_lang.value}...")
        for i, file_path in enumerate(translatable_files):
            print(f"--- File {i+1}/{len(translatable_files)} ---")
            try:
                await self.translate_single_file(str(file_path), target_lang, vocab_list)
            except TranslateFileError as e:
                print(f"ERROR translating {file_path.name}: {e}. Skipping this file.")
            # The sleep is now inside translate_single_file, after each successful API call.
        print(f"Finished translation to {target_lang.value}.")

    def _verify_project_placement(self) -> None:
        """
        Verifies that the project hasn't been moved to another directory, if it has, then all the paths are corrected.
        """
        pass
        curr_root = Path(os.path.realpath(self.root_path))
        old_root = self.config.get_root_path()

        if curr_root != old_root:
            logger.debug("Config root path doesn't correspond to the corrent one!")
            self.config.rearrange_project(curr_root, old_root) 
            self.save_config()

# TODO: remove this, as it is diff, it must be implemented in the translation, after XML tagging
# DEBUG!
    def diff(self, txt: str, lang: Language) -> tuple[str, float]:
        return TranslationStoreCsv(self.root_path).get_best_match_from_db(lang, txt)


# --- Module-level functions for project init and load ---
def init_project(project_name: str, root_dir_str: str) -> Project:
    """Initializes a new project configuration in the specified directory."""
    root_path = Path(root_dir_str)
    if not root_path.is_dir(): # Also checks existence
        raise InitProjectError(InvalidPathError(f"Invalid path: {root_dir_str} is not an existing directory."))
    
    abs_root_path = root_path.resolve()
    config_file = abs_root_path / CONF_DIR / CONFIG_FILENAME
    
    if config_file.exists():
        raise InitProjectError(ProjectAlreadyInitializedError(f"Project already initialized at {abs_root_path} ({CONFIG_FILENAME} exists)."))

    try:
        # Create a Project instance with an empty config, then save it.
        project = Project._create_new_for_init(project_name, abs_root_path)
        project.save_config() # This writes the initial trans_conf.json
        print(f"{CONF_DIR} directory has been successfully created!")
        return project
    except ConfigWriteError as e:
        raise InitProjectError(f"Failed to write initial config file: {e}", e)
    except Exception as e:
        raise InitProjectError(f"An unexpected error occurred during project initialization: {e}", e)


def load_project(path_str: str) -> Project:
    """Loads an existing project from the given path (can be project root or any child path)."""
    start_path = Path(path_str).resolve()
    
    config_dir_path = find_dir_upwards(start_path, CONF_DIR)
    if not config_dir_path:
        raise LoadProjectError(NoConfigFoundError(f"No '{CONF_DIR}' found in or above {start_path}."))

    project_root = config_dir_path.parent

    config_file_path = config_dir_path / CONFIG_FILENAME
    
    try:
        config_model = load_project_config(config_file_path)
        project = Project(project_root, config_model)
        project._verify_project_placement()
        print(f"Project '{project.config.name}' loaded from {project_root}")
        return project
    except ConfigLoadError as e:
        raise LoadProjectError(f"Failed to load project configuration: {e}", e)
    except Exception as e:
        raise LoadProjectError(f"An unexpected error occurred during project loading: {e}", e)

