import json
import os
from pathlib import Path
from typing import Callable, List, Optional
import shutil

from .project_config_models import DirectoryModel, FileModel, ProjectConfig
from .errors import LoadConfigError, WriteConfigError, CopyFileDirError

def build_directory_tree(root_path: Path) -> DirectoryModel:
    """
    Builds a DirectoryModel tree rooted at `root_path`.
    Skips symlinks.
    """
    if not root_path.is_dir():
        # Or raise a more specific error
        raise ValueError(f"Path {root_path} is not a directory or does not exist.")

    dir_model = DirectoryModel.new_from_path(root_path)

    for entry in root_path.iterdir():
        try:
            if entry.is_symlink():
                continue

            if entry.is_dir():
                dir_model.dirs.append(build_directory_tree(entry))
            elif entry.is_file():
                file_model = FileModel(
                    name=entry.name,
                    path=entry.resolve(), 
                    translatable=False 
                )
                dir_model.files.append(file_model)
        except OSError: 
            # TODO: decide how to handle
            # print(f"Warning: Could not access {entry}, skipping.") 
            # continue
            raise
            
    return dir_model


def write_project_config(config_file_path: Path, config: ProjectConfig) -> None:
    """Writes the project configuration to a JSON file."""
    try:
        json_str = config.model_dump_json(indent=2)
        config_file_path.write_text(json_str, encoding="utf-8")
    except IOError as e:
        raise WriteConfigError(f"IO error writing config to {config_file_path}: {e}", original_exception=e)
    except Exception as e: # Pydantic validation or serialization errors
        raise WriteConfigError(f"Serialization error writing config: {e}", original_exception=e)


def load_project_config(config_file_path: Path) -> ProjectConfig:
    """Loads project configuration from a JSON file."""
    if not config_file_path.is_file():
        raise LoadConfigError(f"Config file not found: {config_file_path}")
    try:
        contents = config_file_path.read_text(encoding="utf-8")
        config = ProjectConfig.model_validate_json(contents)
        return config
    except FileNotFoundError: # Should be caught by is_file, but good practice
        raise LoadConfigError(f"Config file not found: {config_file_path}")
    except json.JSONDecodeError as e:
        raise LoadConfigError(f"Incorrect config file format (JSON decode error): {config_file_path}", original_exception=e)
    except Exception as e: # Pydantic validation errors
        raise LoadConfigError(f"Incorrect config file format (validation error): {config_file_path} - {e}", original_exception=e)

def copy_untranslatable_files_recursive(
    from_dir_root_path: Path, # Absolute path to the root of the source directory being copied (e.g. /path/to/project/src_en)
    to_dir_root_path: Path,   # Absolute path to the root of the target directory (e.g. /path/to/project/target_fr)
    source_dir_structure: DirectoryModel # The DirectoryModel of the from_dir (relative paths within this structure)
) -> None:
    """
    Recursively copies untranslatable files from a source structure to a target directory.
    - from_dir_root_path: The actual disk path of the source directory (e.g., project_root/src_dir_name).
    - to_dir_root_path: The actual disk path of the target directory (e.g., project_root/target_dir_name).
    - source_dir_structure: The DirectoryModel representing the 'from_dir_root_path'.
                            Paths within this model are absolute but need to be made relative
                            to from_dir_root_path to map to to_dir_root_path.
    """
    # Ensure target root exists
    to_dir_root_path.mkdir(parents=True, exist_ok=True)

    for file_model in source_dir_structure.get_files():
        if file_model.is_translatable():
            continue
        target_file_abs_path = None
        try:
            # file_model.path is absolute. We need path relative to from_dir_root_path
            # Example: file_model.path = /abs/path/to/project/src_en/subdir/file.txt
            #          from_dir_root_path = /abs/path/to/project/src_en
            #          relative_path = subdir/file.txt
            relative_path = file_model.path.relative_to(from_dir_root_path)
            
            source_file_abs_path = file_model.path # This is already absolute and resolved
            target_file_abs_path = to_dir_root_path / relative_path
            
            target_file_abs_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file_abs_path, target_file_abs_path) # copy2 preserves metadata
        except ValueError as e: # relative_to fails if not a subpath
            raise CopyFileDirError(f"File path {file_model.path} not relative to source root {from_dir_root_path}: {e}", original_exception=e)
        except IOError as e:
            raise CopyFileDirError(f"IO error copying {file_model.path} to {target_file_abs_path}: {e}", original_exception=e)

    for sub_dir_model in source_dir_structure.get_dirs():
        # sub_dir_model.path is absolute.
        # Example: sub_dir_model.path = /abs/path/to/project/src_en/subdir
        #          from_dir_root_path = /abs/path/to/project/src_en
        #          relative_sub_dir_path = subdir
        try:
            relative_sub_dir_path = sub_dir_model.path.relative_to(from_dir_root_path)
        except ValueError as e:
             raise CopyFileDirError(f"Sub-directory path {sub_dir_model.path} not relative to source root {from_dir_root_path}: {e}", original_exception=e)

        new_target_sub_dir_path = to_dir_root_path / relative_sub_dir_path
        new_target_sub_dir_path.mkdir(parents=True, exist_ok=True) # Ensure target subdir exists
        
        copy_untranslatable_files_recursive(
            from_dir_root_path=from_dir_root_path, 
            to_dir_root_path=to_dir_root_path,     
            source_dir_structure=sub_dir_model     # We explore this sub-structure
        )

def remove_files_not_in_source_dir(
    from_dir_root_path: Path, # Absolute path to the root of the source directory being copied (e.g. /path/to/project/src_en) 
    to_dir_root_path: Path,   # Absolute path to the root of the target directory (e.g. /path/to/project/target_fr)
    source_dir_structure: DirectoryModel # The DirectoryModel of the from_dir (relative paths within this structure)
) -> None:
    """
    Verifies and removes all the files and directories in the target directory that are not in the source directory.
    - from_dir_root_path: The actual disk path of the source directory (e.g., project_root/src_dir_name).
    - to_dir_root_path: The actual disk path of the target directory (e.g., project_root/target_dir_name).
    - source_dir_structure: The DirectoryModel representing the 'from_dir_root_path'.
                            Paths within this model are absolute but need to be made relative
                            to from_dir_root_path to map to to_dir_root_path.
    """
    to_dir_root_path.mkdir(parents=True, exist_ok=True)

    # getting the files and the directories of the current directory of the source dir
    files = [file.get_name() for file in source_dir_structure.get_files()]
    dirs = [dir.get_dir_name() for dir in source_dir_structure.get_dirs()]

    # iterating over the files and dirs of the target directory
    for entry in to_dir_root_path.iterdir():
        try:
            entry_name = entry.name 
            if entry.is_dir() and entry_name not in dirs:
                if entry.is_symlink():
                    os.remove(entry)
                else:
                    shutil.rmtree(entry)
            elif entry.is_dir(): # so it is indeed in dirs list
                for sub_dir in source_dir_structure.get_dirs(): # now continue the process of removal in this sub directory
                    if sub_dir.get_dir_name() == entry_name:
                        remove_files_not_in_source_dir(from_dir_root_path.joinpath(entry), to_dir_root_path.joinpath(entry), sub_dir)
                        break
            elif entry.is_file() and entry_name not in files:
                os.remove(entry)
        except OSError: 
            # TODO: decide how to handle
            # print(f"Warning: Could not access {entry}, skipping.") 
            # continue
            raise
            
