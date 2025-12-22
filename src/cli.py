import asyncio
import os
import csv
import sys
from pathlib import Path
from typing import List, Optional

import typer
from loguru import logger
from typing_extensions import Annotated # For Typer < 0.7 or for more complex annotations

from trans_lib.enums import Language, CLI_LANGUAGE_CHOICES
from trans_lib.project_manager import Project, init_project, load_project
from trans_lib import errors
from trans_lib.vocab_list import VocabList, vocab_list_from_vocab_db # Import the errors module

# Create the Typer app
app = typer.Typer(
    name="dir-translator",
    help="A tool for managing and translating directory structures.",
    no_args_is_help=True
)

@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show diagnostic logs.")] = False,
) -> None:
    logger.remove()
    if verbose:
        logger.add(sys.stderr, level="TRACE")

# Shared callback to load project (or handle not being in one)
def get_project_from_context(ctx: typer.Context) -> Project:
    """Loads project based on current directory or explicit path."""
    try:
        # Typer passes the command-specific options.
        # We need a way to get a global --project-path or use CWD.
        # Let's assume `load_project` can take PWD.
        project_path_str = "." # Default to current directory
        
        # If a global option --project-dir is added to app, it can be accessed via ctx.params
        # if ctx.parent and ctx.parent.params.get("project_dir"):
        #    project_path_str = ctx.parent.params["project_dir"]
            
        return load_project(project_path_str)
    except errors.LoadProjectError as e:
        typer.secho(f"Error loading project: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e: # Catch any other unexpected error during load
        typer.secho(f"An unexpected error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


# --- Project Initialization and Loading Commands ---
@app.command()
def init(
    name: Annotated[str, typer.Option(help="Name for the new project.")] = "MyTranslationProject",
    path: Annotated[Path, typer.Option(help="Directory to initialize the project in. Defaults to current directory.")] = Path(".")
):
    """Initializes a new translation project."""
    try:
        project = init_project(name, str(path.resolve()))
        typer.secho(f"Project '{project.config.name}' initialized successfully at {project.root_path}", fg=typer.colors.GREEN)
    except errors.InitProjectError as e:
        typer.secho(f"Error initializing project: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command("set-source")
def set_source_dir(
    ctx: typer.Context, # For getting loaded project
    dir_name: Annotated[str, typer.Argument(help="Name of the source directory (relative to project root).")],
    lang: Annotated[Language, typer.Argument(help="Source language.", case_sensitive=False)] # Typer handles Enum conversion
):
    """Sets or changes the source directory and its language."""
    project = get_project_from_context(ctx)
    try:
        project.set_source_directory(dir_name, lang)
        typer.secho(f"Source directory set to '{dir_name}' with language {lang.value}", fg=typer.colors.GREEN)
    except errors.SetSourceDirError as e:
        typer.secho(f"Error setting source directory: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("set-target")
def add_language(
    ctx: typer.Context,
    dir_name: Annotated[Path, typer.Argument(help="Set particular directory.", case_sensitive=True)],
    lang: Annotated[Language, typer.Argument(help="Target language to add.", case_sensitive=False)],
):
    """Adds a new target language to the project."""
    project = get_project_from_context(ctx)
    try:
        new_path = project.add_target_language(lang, dir_name)
        typer.secho(f"Target language {lang.value} added. Directory created at {new_path}", fg=typer.colors.GREEN)
    except errors.AddLanguageError as e:
        typer.secho(f"Error adding language: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("remove-target")
def remove_language(
    ctx: typer.Context,
    lang: Annotated[Language, typer.Argument(help="Target language to remove.", case_sensitive=False)]
):
    """Removes a target language and its directory from the project."""
    project = get_project_from_context(ctx)
    try:
        project.remove_target_language(lang)
        typer.secho(f"Target language {lang.value} and its directory removed.", fg=typer.colors.GREEN)
    except errors.RemoveLanguageError as e:
        typer.secho(f"Error removing language: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("sync")
def sync_files(ctx: typer.Context):
    """Synchronizes untranslatable files from the source to all target directories."""
    project = get_project_from_context(ctx)
    try:
        project.sync_untranslatable_files()
        typer.secho("Untranslatable files synchronized successfully.", fg=typer.colors.GREEN)
    except errors.SyncFilesError as e:
        typer.secho(f"Error synchronizing files: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("add")
def mark_translatable(
    ctx: typer.Context,
    file_paths: Annotated[list[str], typer.Argument(help="Path to the file (relative to project root or absolute).")]
):
    """Marks a file in the source directory as translatable."""
    project = get_project_from_context(ctx)
    try:
        for file_path in file_paths:
            project.set_file_translatability(file_path, True)
            typer.secho(f"File '{file_path}' marked as translatable.", fg=typer.colors.GREEN)
    except errors.AddTranslatableFileError as e:
        typer.secho(f"Error marking file as translatable: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("remove")
def mark_untranslatable(
    ctx: typer.Context,
    file_paths: Annotated[list[str], typer.Argument(help="Path to the file (relative to project root or absolute).")]
):
    """Marks a file in the source directory as untranslatable."""
    project = get_project_from_context(ctx)
    try:
        for file_path in file_paths:
            project.set_file_translatability(file_path, False)
            typer.secho(f"File '{file_path}' marked as untranslatable.", fg=typer.colors.GREEN)
    except errors.AddTranslatableFileError as e:
        typer.secho(f"Error marking file as untranslatable: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("set-llm")
def set_source_dir(
    ctx: typer.Context, # For getting loaded project
    service: Annotated[str, typer.Argument(help="Name of the service providing a model")],
    model: Annotated[str, typer.Argument(help="Name of the model", case_sensitive=True)] # Typer handles Enum conversion
):
    """Sets or changes an LLM and the service providing the model."""
    project = get_project_from_context(ctx)
    try:
        project.set_llm_service_and_model(service, model)
        typer.secho(f"The service set to '{service}' with the model {model}", fg=typer.colors.GREEN)
    except errors.SetSourceDirError as e:
        typer.secho(f"Error setting service and model: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("list")
def list_translatable_files(ctx: typer.Context):
    """Lists all files marked as translatable in the source directory."""
    project = get_project_from_context(ctx)
    try:
        files = project.get_translatable_files()
        if not files:
            typer.secho("No translatable files found.", fg=typer.colors.YELLOW)
            return
        typer.secho("Translatable files:", fg=typer.colors.BLUE)
        for f_path in files:
            # Try to make path relative to project root for cleaner display
            try:
                display_path = f_path.relative_to(project.root_path)
            except ValueError:
                display_path = f_path # If not under root_path (should not happen)
            typer.echo(f"  {display_path}")
    except errors.GetTranslatableFilesError as e:
        typer.secho(f"Error listing translatable files: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("info")
def info_on_project(ctx: typer.Context):
    """
    Provides an info about the project
    """
    project = get_project_from_context(ctx)
    print("Project Information:");
    print("\tProject Name: {}".format(project.config.get_name()) )
    print("\tRoot Path: {}".format(project.root_path))

    src_dir = project.config.get_src_dir()
    if src_dir is None:
        print("\tSource directory: Is not set")
    else:
        src_dir_name = src_dir.get_path().name
        src_dir_lang = src_dir.get_lang()
        llm_service = project.get_llm_service()
        llm_model = project.get_llm_model()
        print("\tSource language: {}".format(src_dir_lang))
        print("\tSource directory: {}".format(src_dir_name))
        print("\tModel for translation: {} {}".format(llm_service, llm_model))

    target_langs = project._get_target_languages()
    if len( target_langs ) == 0:
        print("\tTarget langauges: There is no target languages")
    else:
        print("Target languages:")
        for lang in target_langs:
            tgt_dir = project.config.get_target_dir_path_by_lang(lang)
            tgt_dir_name = None if tgt_dir is None else tgt_dir.name
            print("\tLanguage: {:<10} | Directory: {}".format(lang, tgt_dir_name))


# --- Translation Commands ---
translate_app = typer.Typer(name="translate", help="Translate files", no_args_is_help=True)
app.add_typer(translate_app) # Sub-command of project

def _read_vocab_from_file(path: Path) -> list[dict]:
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)

async def _translate_file_command(project: Project, file_path_str: str, lang: Language, vocab: Path | None):
    try:
        vocabulary = None
        if vocab != None:
            vocabulary = vocab_list_from_vocab_db(_read_vocab_from_file(vocab), project.get_source_langugage(), lang)

        await project.translate_single_file(file_path_str, lang, vocabulary) # WARNING: remove None
        typer.secho(f"File '{file_path_str}' translated to {lang.value} successfully.", fg=typer.colors.GREEN)
    except errors.TranslateFileError as e:
        typer.secho(f"Error translating file '{file_path_str}': {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"An unexpected error occurred during translation: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@translate_app.command("file")
def translate_file_cli(
    ctx: typer.Context,
    file_path: Annotated[str, typer.Argument(help="Path to the translatable file.")],
    lang: Annotated[Language, typer.Argument(help="Target language for translation.", case_sensitive=False)],
    vocabulary: Annotated[Path | None, typer.Option(help="A path to the csv file with the vocabulary.", case_sensitive=False)] = None
):
    """Translates a single specified translatable file."""
    project = get_project_from_context(ctx)
    asyncio.run(_translate_file_command(project, file_path, lang, vocabulary))


async def _translate_all_command(project: Project, lang: Language, vocab: Path | None):
    try:
        vocabulary = None
        if vocab != None:
            vocabulary = vocab_list_from_vocab_db(_read_vocab_from_file(vocab), project.get_source_langugage(), lang)

        await project.translate_all_for_language(lang, vocabulary) # WARNING: remove None
        typer.secho(f"All translatable files processed for language {lang.value}.", fg=typer.colors.GREEN)
    except errors.TranslateFileError as e: # Should be caught by individual file errors mostly
        typer.secho(f"Error during 'translate all' for {lang.value}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"An unexpected error occurred during 'translate all': {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@translate_app.command("all")
def translate_all_cli(
    ctx: typer.Context,
    lang: Annotated[Language, typer.Argument(help="Target language for translation.", case_sensitive=False)],
    vocabulary: Annotated[Path | None, typer.Option(help="A path to the csv file with the vocabulary.", case_sensitive=False)] = None
):
    """Translates all translatable files to the specified language."""
    project = get_project_from_context(ctx)
    asyncio.run(_translate_all_command(project, lang, vocabulary))


# ============ cache app =============
cache_app = typer.Typer(name="cache", help="Translation cache utilities", no_args_is_help=True)
app.add_typer(cache_app)

@cache_app.command("sync")
def sync_cache_cli(ctx: typer.Context):
    """Synchronizes the translation cache for all target languages using on-disk files."""
    project = get_project_from_context(ctx)
    try:
        project.sync_translation_cache()
        typer.secho("Translation cache synced for all target languages.", fg=typer.colors.GREEN)
    except errors.TranslationCacheSyncError as e:
        typer.secho(f"Error syncing translation cache: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"An unexpected error occurred during cache sync: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

# --- Main execution for CLI ---
# This callback is for global options like --project-dir if you add them
# For now, it's not strictly needed as get_project_from_context handles loading
# @app.callback()
# def main_global_options(
#    project_dir: Annotated[Optional[Path], typer.Option(help="Path to the project directory (if not current).")] = None
# ):
#    """
#    Directory Translation Tool
#    """
#    # Store project_dir in ctx.obj if needed by subcommands,
#    # or handle it directly in get_project_from_context.
#    pass


if __name__ == "__main__": 
    app()
