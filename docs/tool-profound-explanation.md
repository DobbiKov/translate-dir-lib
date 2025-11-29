# The profound explanation of the tool

This page contains an overview and explanation of the architecture, algorithms
and ideology of the library, and explains its features.

## Table of Contents

- [The profound explanation of the tool](#the-profound-explanation-of-the-tool)
  - [Table of Contents](#table-of-contents)
  - [Main Unit: Project](#main-unit-project)
  - [Project initialization and required settings](#project-initialization-and-required-settings)
    - [Important notes](#important-notes)
  - [Two types of files](#two-types-of-files)
  - [Syncing vs Translating](#syncing-vs-translating)
    - [Syncing](#syncing)
    - [Translating](#translating)
    - [Difference](#difference)
  - [Translation algorithm](#translation-algorithm)
  - [Correcting](#correcting)
  - [Translation Cache](#the-translation-cache)
    - [Structure](#structure)
    - [Checksum-to-text cache](#checksum-to-text-cache)
    - [Correspondence cache](#correspondence-cache)

## Main Unit: Project

The main unit of the library is called a **translation project**. A translation
project contains all the information about your file structure, languages and
translation cache.

Translation projects behaves similarly to, e.g., `git` projects. There is always
a root directory that you must be in, where you'll initialize the translation
project. The root directory contains the project configuration in a dedicated
_dot_ directory, a translation cache, and the files that are "tracked": in
our case the files that are synced and translated across the languages.

> Note: don't confuse your writing project, for example: LaTeX project and
> translation project. Your "writing project's" root directory must be placed in
> the root directory of the translation project.

For example: let's assume that we have a French LaTeX project in a directory
having the following structure:
```
analysis_notes_fr/
├── main.tex
├── lec1.tex
├── authors.tex
├── figues/
│   └── ...
└── bib/
    └── bib.tex
```

Creating a translation project requires a dedicated directory holding
`analysis_notes_fr` as subdirectory. For example:

```
analysis_notes/
└── analysis_notes_fr/
    ├── main.tex
    ├── lec1.tex
    ├── authors.tex
    ├── figues/
    │   └── ...
    └── bib/
        └── bib.tex
```

Once initialized, the translation project has the following structure:
```
analysis_notes/
├── analysis_notes_fr/
│   ├── main.tex
│   ├── lec1.tex
│   ├── authors.tex
│   ├── figues/
│   │   └── ...
│   └── bib/
│       └── bib.tex
├── .translate_dir/
    ├── config.json
    └── translate_cache/
        └── ...
```

And after translation into Ukrainian it becomes:

```
analysis_notes/
├── analysis_notes_fr/
│   ├── main.tex
│   ├── lec1.tex
│   ├── authors.tex
│   ├── figues/
│   │   └── ...
│   └── bib/
│       └── bib.tex
├── analysis_notes_ua/
│   ├── main.tex
│   ├── lec1.tex
│   ├── authors.tex
│   ├── figues/
│   │   └── ...
│   └── bib/
│       └── bib.tex
├── .translate_dir/
    ├── config.json
    └── translate_cache/
        └── ...
```

## Project initialization and required settings

When you initialize a project, a `.translate_dir` directory is created that
stores a `config.json` configuration file. This file will store:

- the project's name
- the source and target languages
- the directories that correspond to the source and target languages
- the files that must be translated
- additional settings

You must then set a **source directory** together with its language. Only files
within that source directory can be translated. You must then set at least one
**target directory** together with its language. The target directory will be
created if needed and will eventually hold the translation of the source
directory.

### Important notes

- The source directory can be reset, i.e you can set another directory as a
  source one using the same `set-source command`.
- The target languages can be removed using `remove-target` command (in CLI), or
  `remove_target_language` method in the library.

## Translatable and untranslatable files.

You can mark any file in the source directory as _translatable_; a translatable
file is ignored by the `sync` command, and translated by the translation
commands.

All other files in the source directory are considered as _untranslatable_. An
untranslatable file is copied over as is by the `sync` command and ignored by
the translation commands. Typical untranslatable files are assets such as media
or bibliography files.

With this, once translated and synced, the target directory should be ready for
use (e.g. for building with latex).

## Translation algorithm

The algorithm reads a file, divides it into _chunks_ (sometimes called _cells_
here) and pass them to a Large Language Model (by default the _gemini_ models
from google) together with a big prompt that asks the model to translate a chunk
and explains how to preserve the structure, syntax and layout. Then the
translation is extracted, added as a translation pair with the source of the
chunk in the translation cache (see below) and written to the output file.

After the translation, some metadata is set for each chunk in the output file.
Such metadata may be:

- the source checksum that serves to identify the source text that has been
  translated
- a _needs_review_ tag that alerts the user that a particular chunk has been
  translated by machine and needs review by a human.

The translation command may also take a vocabulary list as optional parameter.
That list contains pairs of a word or phrase on a source language and its
translation on the target one. That vocabulary is passed to the LLM in order to
improve its translation quality.

The current version of the library supports the next services:

- OpenAI
- Anthropic
- Google
- Aristote
- xAI

Each service can be set as well as a model supported by each service using an
appropriate interface. The google's `gemini-2.0-flash` is a model set by
default.

When translating, an environment variable `LLM_API_KEY` must be set accordingly
to the service you use.

## The Translation Cache

The translation cache stores translation pairs for later fast retrieval and
reuse.

### Structure

The cache is stored in the `translate_cache` directory located at the project
root. This folder has the following structure:

```
translate_cache/
├── correspondence_cache.csv
├── <lang_1>/
│   └── ...
└── <lang_2>/
    └── ...
```

and consists of two parts:

- a checksum-to-text cache
- a correspondence cache

### Checksum-to-text cache

This part of the cache is stored in the `<lang_*>` folders; each file in these
folders holds a chunk of text and is named after the checksum of that chunk.
This system allows the storage of the chunk contents, source retrieval and
updates comparison.

Example of such structure:

```
translate_cache/
├── English/
│   ├── <checksum1_en>
│   └── <checksum2_en>
├── French/
│   ├── <checksum1_fr>
│   └── <checksum2_fr>
└── correspondence_cache.csv
```

### Correspondence cache

The correspondence cache is stored in the `correspondence_cache.csv` file. Each
row of that file stores the checksums of chunks of text in two languages or
more, and states that they are the current reference translations of each other.

For example, the following rows:
```
English,French
<checksum1_en>, <checksum1_fr>
<checksum2_en>, <checksum2_fr>
```
states that the chunks stored in the files `English/<checksum_1_en>` and
`French/<checksum1_fr>` respectively are the current reference translations of 
each other.

## Correcting

After the automated translation, authors will typically review the translated
chunks and do some postedits. These postedits are precious. Calling the
`correction` command updates accordingly the translation cache to ensure that
future translations exploit them.
