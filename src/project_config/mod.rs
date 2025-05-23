use crate::errors::project_config_errors::{LoadConfigError, WriteConfigError};
use crate::errors::project_errors::{AddTranslatableFileError, InitProjectError};
use crate::Language;
use queues::*;
use serde;
use std::{
    io::{Read, Write},
    path::{Path, PathBuf},
};
use thiserror::Error;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
/// A struct representing a particular project's config, this config contains the root directory
/// structure and the
pub struct ProjectConfig {
    /// name for the current project
    name: String,
    /// the directory assigned to each target language
    lang_dirs: Vec<LangDir>,
    /// the master directory that the files are copied and translated from
    src_dir: Option<LangDir>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
/// A master directory for a language that copies the master one
pub struct LangDir {
    dir: Directory,
    language: Language,
}
impl LangDir {
    pub(crate) fn new(dir: Directory, lang: Language) -> Self {
        Self {
            dir,
            language: lang,
        }
    }
    pub(crate) fn get_lang(&self) -> Language {
        self.language.clone()
    }
    pub(crate) fn get_dir_as_ref(&self) -> &Directory {
        &self.dir
    }
    pub(crate) fn set_dir(&mut self, dir: Directory) {
        self.dir = dir;
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
/// A config representation of a directory
pub struct Directory {
    /// name of the directory
    name: String,
    /// path to the directory
    path: PathBuf,
    /// directory that this one contains
    dirs: Vec<Directory>,
    /// files that this directory contains
    files: Vec<File>,
}

impl Directory {
    fn new(path: PathBuf) -> Self {
        let name = match path.file_name() {
            None => String::new(),
            Some(r) => r.to_owned().into_string().unwrap_or(String::new()),
        };

        Directory {
            name,
            path,
            dirs: vec![],
            files: vec![],
        }
    }
    pub(crate) fn get_dir_name(&self) -> String {
        self.name.clone()
    }
    pub(crate) fn get_path(&self) -> PathBuf {
        self.path.clone()
    }
    pub(crate) fn get_files_as_ref(&self) -> &Vec<File> {
        &self.files
    }
    pub(crate) fn get_dirs_as_ref(&self) -> &Vec<Directory> {
        &self.dirs
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
/// A config for a file
pub struct File {
    /// name of the file
    name: String,
    /// path to file
    path: PathBuf,
    /// if the file is translatable (false is not, true if it is)
    translatable: bool,
}

impl File {
    pub(crate) fn get_name(&self) -> String {
        self.name.clone()
    }
    pub(crate) fn get_path(&self) -> PathBuf {
        self.path.clone()
    }
    pub(crate) fn is_translatable(&self) -> bool {
        self.translatable
    }
}

impl ProjectConfig {
    fn new(proj_name: &str) -> Self {
        ProjectConfig {
            name: proj_name.to_string(),
            lang_dirs: Vec::new(),
            src_dir: None,
        }
    }
    pub(crate) fn get_name(&self) -> String {
        self.name.clone()
    }
    pub(crate) fn get_src_dir_as_ref(&self) -> &Option<LangDir> {
        &self.src_dir
    }
    pub(crate) fn get_lang_dirs_as_ref(&self) -> &Vec<LangDir> {
        &self.lang_dirs
    }
    pub(crate) fn set_src_dir(&mut self, dir_path: PathBuf, lang: Language) -> std::io::Result<()> {
        let dir = build_tree(dir_path)?;
        let lang_dir = LangDir::new(dir, lang);

        self.src_dir = Some(lang_dir);
        Ok(())
    }
    pub(crate) fn add_lang(&mut self, dir_path: PathBuf, lang: Language) -> std::io::Result<()> {
        let dir = build_tree(dir_path)?;
        let lang_dir = LangDir::new(dir, lang);
        self.lang_dirs.push(lang_dir);
        Ok(())
    }
    pub(crate) fn analyze_lang_dirs(&mut self) -> std::io::Result<()> {
        for dir in &mut self.lang_dirs {
            let path = dir.get_dir_as_ref().get_path();
            let tree = build_tree(path)?;
            dir.set_dir(tree);
        }
        Ok(())
    }

    pub fn make_translatable_file(
        &mut self,
        path: PathBuf,
    ) -> Result<(), AddTranslatableFileError> {
        let mut func = |f: &mut File| {
            f.translatable = true;
        };
        let src_dir = &mut match &mut self.src_dir {
            Some(r) => r,
            None => {
                return Err(AddTranslatableFileError::NoSourceLang);
            }
        }
        .dir;
        let res = find_file_and_apply(src_dir, &path, &mut func);
        match res {
            true => Ok(()),
            false => Err(AddTranslatableFileError::NoFile),
        }
    }

    pub fn make_untranslatable_file(
        &mut self,
        path: PathBuf,
    ) -> Result<(), AddTranslatableFileError> {
        let mut func = |f: &mut File| {
            f.translatable = false;
        };
        let src_dir = &mut match &mut self.src_dir {
            Some(r) => r,
            None => {
                return Err(AddTranslatableFileError::NoSourceLang);
            }
        }
        .dir;
        let res = find_file_and_apply(src_dir, &path, &mut func);
        match res {
            true => Ok(()),
            false => Err(AddTranslatableFileError::NoFile),
        }
    }
}

/// Searches recursively for file in the given directory and if it finds the file it applies the
/// given function and returns true, otherwise returns false
fn find_file_and_apply<F>(dir: &mut Directory, path: &Path, func: &mut F) -> bool
where
    F: FnMut(&mut File),
{
    for file in &mut dir.files {
        if file.get_path() == *path {
            (func)(file);
            return true;
        }
    }
    for sub_dir in &mut dir.dirs {
        if find_file_and_apply(sub_dir, path, func) {
            return true;
        }
    }
    false
}

/// Build a `Directory` tree rooted at `root`.
pub fn build_tree<P: AsRef<Path>>(root: P) -> std::io::Result<Directory> {
    fn recurse(path: &Path) -> std::io::Result<Directory> {
        let name = path
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| String::from("/"));

        let mut dir = Directory::new(path.to_path_buf());

        for entry in std::fs::read_dir(path)? {
            let entry = entry?;
            let meta = entry.metadata()?;

            if meta.is_symlink() {
                continue;
            }

            if meta.is_dir() {
                dir.dirs.push(recurse(&entry.path())?);
            } else if meta.is_file() {
                let file_name = entry.file_name().to_string_lossy().into_owned();
                dir.files.push(File {
                    name: file_name.clone(),
                    path: entry.path(),
                    translatable: false,
                });
            }
        }

        Ok(dir)
    }

    recurse(root.as_ref())
}

/// Init project config with it's file
pub fn init(proj_name: &str, path: PathBuf) -> Result<(), InitProjectError> {
    if !path.exists() {
        return Err(InitProjectError::InvalidPath);
    }
    let config_filename = "trans_conf.json";
    let config_file_fullpath = path.join(config_filename);
    if config_file_fullpath.exists() {
        return Err(InitProjectError::ProjectAlreadyInitialized);
    }

    let conf = ProjectConfig::new(proj_name);
    let _ = write_conf(config_file_fullpath, &conf).map_err(InitProjectError::ConfigWritingError);
    Ok(())
}

pub(crate) fn write_conf(path: PathBuf, conf: &ProjectConfig) -> Result<(), WriteConfigError> {
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .read(true)
        .open(path)
        .map_err(WriteConfigError::IoError)?;

    let serialized = serde_json::to_string(conf)
        .map_err(|e| WriteConfigError::SerialisationError(e.to_string()))?;
    file.write_fmt(format_args!("{}", serialized))
        .map_err(WriteConfigError::IoError)?;
    Ok(())
}

pub fn load_config_from_file(path: PathBuf) -> Result<ProjectConfig, LoadConfigError> {
    let mut conf_file = std::fs::OpenOptions::new()
        .read(true)
        .open(&path)
        .map_err(LoadConfigError::OpenConfigFileError)?;
    let mut contents = String::new();
    let _ = conf_file
        .read_to_string(&mut contents)
        .map_err(LoadConfigError::OpenConfigFileError)?;
    let conf: ProjectConfig = serde_json::from_str(contents.as_str())
        .map_err(|_| LoadConfigError::IncorrectConfigFileFormat)?;

    Ok(conf)
}

// commands
//pub fn add_lang_dir(dir_name: &str, lang: Language) -> Result<(), Box<dyn std::error::Error>> {
//    todo!()
//}
