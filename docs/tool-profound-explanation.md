# The profound explanation of the tool
This page contains the profound overview and explanation of the architecture, algorithms and ideology of the library and explain all its features.

## Table of Contents
- [Main Unit: Project](#main-unit-project)
- [Project initialization and required settings](#project-initialization-and-required-settings)
- [Two types of files](#two-types-of-files)
- [Syncing vs Translating](#syncing-vs-translating)
    - [Syncing](#syncing)
    - [Translating](#translating)
    - [Difference](#difference) 
- [Translation algorithm](#translation-algorithm)
- [Correcting](#correcting)
- [Translation Database](#translation-database)
    - [Structure](#strucute)
    - [Text to checksum DB](#text-to-checksum-db)
    - [Correspondence DB](#correspondence-db)

## Main Unit: Project
The main unit of the library is called **project**. The project contains all
the information about your file structure, languages and translation database.

The project behaves similarly to the git. There's always a root directory that
you must be in, where you'll initialize the translation project. The directory
contains project's config in the _dot_ directory dedicated to this tool,
translation database and the files that are "tracked", in our case the files
that are synced and translated across the languages.

> Note: don't confuse your writing project, for example: LaTeX project and
> translation project. Your "writing project's" root directory must be placed
> in the root directory of the translation project.

For example:
Let's assume that we have a LaTeX project in the directory called `analysis_notes` that has the next structure
```
analysis_notes/
├── main.tex
├── lec1.tex
├── authors.tex
├── figues/
│   └── ...
└── bib/
    └── bib.tex
```

Then, if we want to create a translation project using this CLI, then we need
to move to the directory of our choice or create one, here:
`analysis_translation_proj` and put the `analysis_notes` directory there:

```
analysis_translation_proj/
└── analysis_notes/
    ├── main.tex
    ├── lec1.tex
    ├── authors.tex
    ├── figues/
    │   └── ...
    └── bib/
        └── bib.tex
```

Then, when we will initialize our translation project it will have the next structure:

```
analysis_translation_proj/
├── analysis_notes/
│   ├── main.tex
│   ├── lec1.tex
│   ├── authors.tex
│   ├── figues/
│   │   └── ...
│   └── bib/
│       └── bib.tex
├── trans_git_db/
    ├── trans_conf.json
    └── trans_git_db/
        └── ...
```

And after translation into Ukrainian:
```
analysis_translation_proj/
├── analysis_notes/
│   ├── main.tex
│   ├── lec1.tex
│   ├── authors.tex
│   ├── figues/
│   │   └── ...
│   └── bib/
│       └── bib.tex
├── proj_name_ua/
│   ├── main.tex
│   ├── lec1.tex
│   ├── authors.tex
│   ├── figues/
│   │   └── ...
│   └── bib/
│       └── bib.tex
├── trans_git_db/
    ├── trans_conf.json
    └── trans_git_db/
        └── ...
```

## Project initialization and required settings
When you initialize a project the `.trans_git` directory is created that stores `trans_conf.json` config. This config stores:
- project's name
- source and target languages
- directories that correspond to the source and target languages
- files that must be translated
- and additional settings 

However, when you initialize a project, you define your intentions but it is
not sufficient yet to translate any files.

Firstly, you must set the **source directory** and a language that corresponds to
that source directory. Only the files from the set source directory will be
able to be translated, you can't specify any files from other directories that
are not children of the source directory to be translatable even if those files
are located in the root directory of the project.

Secondly, you must set the target languages different from the source language.
The setting of a target language will create a directory in the root of the
project that will have as a name: the name of the project and an appropriate language suffix.
Example: The addition of the French language in the project named
`analysis_course` will produce the directory with a name `analysis_course_fr`.

This directory will have the copy of the source directory with translated files.

### Important notes
- The source directory can be reset, i.e you can set another directory as a source one.
- The target languages can be removed.

## Two types of files
All the files in the source directory are considered as *untranslatable* by
default. It means that those files won't be translated and will be copied when
`sync` command is used.

You can mark any file in the source directory as *translatable*, then such file
won't be copied by `sync` command and will be able to be translated using the
appropriate command.

## Syncing vs Translating
### Syncing
When `sync` command is used, all the *untranslatable* files from the source
directory are copied to the target language directories. An example of such
files are images, figures or bibliography.

The goal of this functionality is to reproduce your "writing" project's
structure in order to simplify the compilation process. That is to say, when
you translate your project and use `sync` command, you can compile it without
any additional actions required.

> Note: the `sync` command doesn't copy the files that are marked as *translatable*.

### Translating
Translating reads the files in the source directory that are marked as
*translatable*, translates them and writes to the appropriate target language
directories. During the translation process, the files that are _not_ marked as
_translatable_ won't be copied to the target directories.

### Difference
The syncing _copies_ only the _untranslatable_ files and doesn't touch
_translatable_ ones. Translating translates the files and put them into
appropriate directories.

## Translation algorithm
The core idea of the algorithm of the algorithm is read a file, divide it into
_chunks_ (sometimes called _cells_ here) and pass to an LLM (currently _gemini_
models from google) with a big prompt that asks a model translate a chunk and
explains how to preserve the structure, syntax and layout. Then the translation
is extracted, added as a pair with the source of the chunk in the database and
written to the output file.

After the translation, some metadata is set for each chunk in the output file.
Such metadata may be:
- source checksum that serves to identify the source text that has been translated
- _needs\_review_ tag that alerts the user that a particular chunk has been
  translated by machine but wasn't verified by human.

The translation command may also take an optional parameter that is a
vocabulary list. That list contains pairs of a word or phrase on a source
language and it's translation on the target one. That vocabulary that is passed
to the LLM in order to improve it's translation quality.

Current version of the library uses `gemini-2.0-flash` Google's model that
requires `GOOGLE_API_KEY` to be set as an environment variable. The information
about how to obtain such key can be found [here](https://aistudio.google.com/app/apikey).

## Correcting
After the translation a user may want to correct or edit the translated files.
These changes are logically should be saved in order to not lose those changes.
Thus, when the correction command is called, it reads each translated chunk in
the translated files retrieve the source text using the source checksum and if
it figures out that the translation has been changed by user it updates it in
the database.

## Translation Database
Translation database is aimed to store translation pairs in order to avoid
retranslation of the chunks that have already been translated previously and
track changes and edits in the source project and the translated versions of
it.

### Structure
The database is presented in the `trans_git_db` directory that is stored in the
root directory of the project. This folder has the next structure:

```
trans_git_db/
├── correspondence_db.csv
├── <lang_1>/
│   └── ...
└── <lang_2>/
    └── ...
```

and consists of the next parts:
- Text to checksum DB
- correspondence DB

### Text to checksum DB
This part of the database is represented by the `<lang_*>` folders that store
files that has any text (usually the text of the chunks from the files) and the
checksum of the contents of the file as a name of the file. This system allows
the storage of the chunk contents, source retrieval and updates comparison.

Example of such structure:
```
trans_git_db/
├── English/
│   ├── <checksum1_en>
│   └── <checksum2_en>
├── French/
│   ├── <checksum1_fr>
│   └── <checksum2_fr>
└── correspondence_db.csv
```

### Correspondence DB
The correspondence database is represented by the `correspondence_db.csv` file
that stores in each row the checksum of at least two languages that the source
contents correspond to the translated contents.

Example:
```
English,French
<checksum1_en>, <checksum1_fr>
<checksum2_en>, <checksum2_fr>
```

That means that the contents of the file stored in `English/<checksum_1_en>`
correspond to the contents of the file `French/<checksum1_fr>`, that is to say
that the contents of the file `French/<checksum1_fr>` is a translation into
French of the text stored in the `English/<checksum1_en>` file.
