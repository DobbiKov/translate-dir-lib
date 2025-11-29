# Translate dir CLI
This is CLI tool that aims to automatize the process of translation of large
documents written using Markup languages such as:
- LaTeX
- Markdown
- Jupyter
- Myst
- Typst

This CLI tool is an implementation of [this library](https://github.com/DobbiKov/translate-dir-lib).

Learn more about the project: [main repository](https://github.com/DobbiKov/sci-trans-git).

Extended abstract about the project: [link](https://dobbikov.github.io/sci-trans-git/jdse-paper.pdf)


⚠️ This tool is in early development. Expect bugs and incomplete features.

## Table of Contents
- [Why translate-dir?](#why-translate-dir)
- [Features](#features)
- [Citation](#citation)
- [Getting started](#getting-started)
    - [Installation](#installation)
    - [First steps](#first-steps)
        - [Project Setup](#project-setup)
        - [Sync & Translate](#sync--translate)
        - [Correction](#correction)
- [Getting started for developers](#getting-started-for-developers)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Why translate-dir?

Manually translating large projects with scientific notation, Markdown, or
LaTeX is slow and error-prone. This library automates this process while
preserving file structure and formatting, so you can focus on refining the
content rather than wrestling with markup.

## Features
- [x] **Project creation** – Set up a new translation workspace in seconds
- [x] **Source & target language management** – Easily define languages for translation
- [x] **File syncing** – Synchronize translatable and non-translatable files across languages
- [x] **Translation cache** – Keep track of all translated content and corrections
- [x] **AI-based translations** – Leverage Google Gemini for high-quality translations
- [x] **Vocabulary support** – Fine-tune translations with custom glossaries
- [x] **Cache-aware corrections** – Preserve manual fixes by syncing the cache from files on disk

## Citation

If you use this software in your research or for writing, please cite it as follows:
```bib
@software{korotenko-sci-trans-git,
    author = {Yehor Korotenko},
    title = {sci-trans-git},
    year = {2025},
    publisher = {GitHub},
    version = {0.2.0-alpha},
    url = {https://github.com/DobbiKov/sci-trans-git},
    doi = {10.5281/zenodo.15775111}
}
```

## Getting started
For developers: follow [here](#getting-started-for-developers)

### Installation
Requirements:
- python 3.11 +
- [uv](https://docs.astral.sh/uv/#__tabbed_1_1) (dependency manager)
1. Ensure you have [uv](https://docs.astral.sh/uv/#__tabbed_1_1) tool installed. 
2. Clone the repository: 
    ```sh
    git clone https://github.com/DobbiKov/translate-dir-cli
    cd translate-dir-cli
    ```
3. Install dependencies: 
    ```sh
    uv sync
    ```

4. Install CLI globally: 
    ```sh
    uv tool install .
    ```
5. Run the cli:
    ```
    translate-dir --help
    ```

### First steps
This section is a guide to start using this tool as quickly as possible, the profound
explanation can be found [here](https://github.com/DobbiKov/translate-dir-lib/blob/master/docs/tool-profound-explanation.md). It is
very recommended to read the profound explanation in order to understand how 
the tool operates with files and how the overall structure of the project look
like.

#### Project Setup
1. Create a root directory for your translation project and place your writing project inside it.

2. Initialize the translation project:
    ```
    translate-dir init --name <my_project>
    ```
3. Set the source directory and its language:
    ```
    translate-dir set-source <dir_name> <language>
    ```

    Example:
    ```
    translate-dir set-source analysis_notes french
    ```

4. Add target language(s):
    ```
    translate-dir set-target <dir_name> <language>
    ```

    Example:
    ```
    translate-dir set-target tgt/en english 
    ```

#### Sync & Translate
5. Mark files for translation:
    ```
    translate-dir add <path_to_file>
    ```

    Example:
    ```
    translate-dir add analysis_notes/main.tex
    ```

    To see all the translatable files use: `translate-dir list`

6. Sync files between source and target directory:
    ```
    translate-dir sync
    ```

For the translation the `LLM_API_KEY` of the service you use is required. 

Follow the next instruction to obtain the key for `gemini` models from `google`:
1. Visit [this link](https://aistudio.google.com/app/apikey)
2. 
    - If it is your first time getting an API KEY for Gemini:
        1. If it is your first time getting an API KEY for Gemini, then you'll see a Popup window. Click on `Get API Key`, then accept the Terms of Service.
        2. Click on `Create API Key`
        3. Copy the generated API key in the popup window
    - If you already had your API KEY
        1. Click on `Create API Key`
        2. Create a new project or choose an existing one
        3. Click on `Create API KEY in existing project`
        4. Copy the generated API key in the popup window

This key must be set as an environment variable:
- On linux/MacOS:
    ```sh
    export LLM_API_KEY=<your_key>
    ```
- On Windows (cmd):
    ```sh
    set LLM_API_KEY=<your_key>    
    ```
- On Windows (PowerShell):
    ```sh
    $env:LLM_API_KEY="<your_key>"
    ```


7. Translate one file:
    ```
    translate-dir translate file <file_path> <target_language>
    ```

    Example:
    ```
    translate-dir translate file analysis_notes/main.tex english
    ```

8. Translate all files
    ```
    translate-dir translate all <target_language>
    ```

    Example:
    ```
    translate-dir translate all english 
    ```

##### Vocabulary
You can use the `--vocabulary` flag with any translation command to provide a custom translation vocabulary. This flag expects the path to a CSV file containing your vocabulary.

The CSV file should be structured as a table where:

* Each column represents a language.
* Each row lists a term in one language and its translations in the other languages.

For example `vocab.csv`:
```csv
English,    French,     German   
apple,      pomme,      Apfel    
computer,   ordinateur, Computer 
```

```sh
translate-dir translate all english --vocabulary vocab.csv
```

This vocabulary helps the translation tool choose more accurate terms and maintain consistency across your project.


#### Cache sync

9. Rebuild the translation cache from the files on disk:
    ```
    translate-dir cache sync
    ```

    Run this after manually editing translated files to ensure the cache matches
    the current contents.

## Getting started for developers
1. Ensure you have [uv](https://docs.astral.sh/uv/#__tabbed_1_1) tool installed. 
2. Clone the library firstly, the lib's installation guide can be found [here](https://github.com/DobbiKov/translate-dir-lib?tab=readme-ov-file#installation)
3. Get the path to the lib's directory on your local machine (for instance: `realpath <your_dir>` on macOs)
4. Clone this repo: 
    ```sh
    git clone https://github.com/DobbiKov/translate-dir-cli
    ```
5. Enter to the directory: 
    ```sh
    cd translate-dir-cli
    ```
6. Remove current library dependency: 
    ```sh
    uv remove translate-dir-lib
    ```
7. Add the local one: `uv add --editable <path_to_local_lib_dir>`
8. Install the dependencies: 
    ```sh
    uv sync
    ```
9. Install the CLI globally in editable mode: 
    ```sh
    uv pip install -e .
    ```

## Documentation
The documentation for the library can be found [here](./docs/main.md)

## Contributing
The suggestions and pull requests are welcome. Visit the issues pages as well
as the project's [main page](https://github.com/DobbiKov/sci-trans-git) and the
[shared document](https://codimd.math.cnrs.fr/sUW9PQ1tTLWcR98UjLHLpw) in order
to know the current direction and plans of the project.
