use crate::{
    errors::project_errors::{
        AddLanguageError, AddTranslatableFileError, CopyFileDirError, InitProjectError,
        LoadProjectError, SetSourceDirError, SyncFilesError,
    },
    helper,
    project_config::{write_conf, Directory},
    Language,
};
use std::path::{Path, PathBuf};

use crate::project_config::ProjectConfig;

#[derive(Debug)]
/// Struct representing the full project for translation
pub struct Project {
    /// Absolute path to the root directory of the project
    path_to_root: PathBuf,
    /// Config of the project
    config: ProjectConfig,
}

/// Initialize project for translation
pub fn init(name: &str, path: PathBuf) -> Result<(), InitProjectError> {
    if !path.is_dir() {
        return Err(InitProjectError::InvalidPath);
    }
    let path = std::fs::canonicalize(path).map_err(|_| InitProjectError::InvalidPath)?;

    let conf = crate::project_config::init(name, path)?;

    Ok(())
}

/// Load project from the given path (even if the path is a child of the project directory)
pub fn load(path: PathBuf) -> Result<Project, LoadProjectError> {
    let conf_file_path = match helper::find_file_upwards(path, "trans_conf.json") {
        None => return Err(LoadProjectError::NoConfig),
        Some(r) => r,
    };
    let root = {
        // Yeah, I wrote the same thing in two different ways
        if let Some(p) = conf_file_path.clone().parent() {
            p.to_path_buf()
        } else {
            return Err(LoadProjectError::NoConfig);
        }
    };

    let conf = crate::project_config::load_config_from_file(conf_file_path)
        .map_err(LoadProjectError::LoadConfigError)?;

    Ok(Project {
        path_to_root: root,
        config: conf,
    })
}

impl Project {
    /// returns the path to the root folder of the project
    pub fn get_root_path(&self) -> std::path::PathBuf {
        self.path_to_root.clone()
    }
    /// return the config
    pub fn get_config(&self) -> ProjectConfig {
        self.config.clone()
    }
    pub fn get_config_as_ref(&self) -> &ProjectConfig {
        &self.config
    }
    /// returns the path to the config file
    fn get_config_file_path(&self) -> PathBuf {
        self.get_root_path().join("trans_conf.json")
    }

    /// returns source language in an option or None if the source directory with a language isn't set
    fn get_src_lang(&self) -> Option<Language> {
        let conf = self.get_config();
        let src_dir = match conf.get_src_dir_as_ref() {
            Some(r) => r,
            None => {
                return None;
            }
        };
        let src_lang = &src_dir.get_lang();
        Some(src_lang.clone())
    }
    /// Set source directory that the contents will be translated of
    pub fn set_source_dir(
        &mut self,
        dir_name: &str,
        lang: Language,
    ) -> Result<(), SetSourceDirError> {
        let full_dir_path = self.get_root_path().join(dir_name);
        if !full_dir_path.exists() {
            return Err(SetSourceDirError::DirectoryDoesNotExist);
        }
        if !full_dir_path.is_dir() {
            return Err(SetSourceDirError::NotDirectory);
        }

        //set as src dir
        let _ = self
            .config
            .set_src_dir(full_dir_path, lang)
            .map_err(SetSourceDirError::AnalyzeDirError);

        let _ = write_conf(self.get_config_file_path(), &self.get_config());
        Ok(())
    }

    /// adds a language that the source directory will be translated into
    pub fn add_lang(&mut self, lang: Language) -> Result<(), AddLanguageError> {
        // verifying we can create a directory for the lang
        let mut dir_name = self.get_config().get_name().clone();
        dir_name.push_str(lang.get_dir_suffix());

        let new_path = self.get_root_path().join(dir_name);

        if new_path.exists() {
            return Err(AddLanguageError::LangDirExists);
        }

        // verifying there's a source language
        let conf = self.get_config();
        let src_lang = self.get_src_lang().ok_or(AddLanguageError::NoSourceLang)?;

        // verifying this lang isn't in the project
        if src_lang == lang {
            return Err(AddLanguageError::LangAlreadyInTheProj);
        }
        for lang_dir in conf.get_lang_dirs_as_ref() {
            let t_lang = lang_dir.get_lang();
            if t_lang == lang {
                return Err(AddLanguageError::LangAlreadyInTheProj);
            }
        }

        std::fs::create_dir(&new_path).map_err(AddLanguageError::IoError)?;

        self.config
            .add_lang(new_path, lang)
            .map_err(AddLanguageError::IoError)?;

        let _ = write_conf(self.get_config_file_path(), &self.get_config());

        Ok(())
    }

    // TODO: add result
    pub fn sync_files(&mut self) -> Result<(), SyncFilesError> {
        let src_lang = self.get_src_lang().ok_or(SyncFilesError::NoSourceLang)?;
        let conf = self.get_config_as_ref();
        let lang_dirs = conf.get_lang_dirs_as_ref();
        if lang_dirs.is_empty() {
            return Err(SyncFilesError::NoTransLangs);
        }

        let lang_dirs_names: Vec<String> = lang_dirs
            .iter()
            .map(|e| e.get_dir_as_ref().get_dir_name())
            .collect();

        let src_dir = conf.get_src_dir_as_ref();
        let src_dir_name = if let Some(l_dir) = src_dir {
            l_dir.get_dir_as_ref().get_dir_name()
        } else {
            panic!("impossible case")
        };

        let lang_src_dir = src_dir.clone().unwrap();
        let src_dir = lang_src_dir.get_dir_as_ref();

        // copy files
        for d_name in lang_dirs_names {
            copy_untranslatable_files(&self.get_root_path(), &src_dir_name, &d_name, src_dir)
                .map_err(SyncFilesError::CopyError)?;
        }
        self.config
            .analyze_lang_dirs()
            .map_err(SyncFilesError::BuildingConfigError)?;
        write_conf(self.get_config_file_path(), &self.config)
            .map_err(SyncFilesError::ConfigWritingError)?;
        Ok(())
    }

    /// Makes the file by given path translatable (for the source directory)
    pub fn make_translatable_file(
        &mut self,
        path: PathBuf,
    ) -> Result<(), AddTranslatableFileError> {
        let path = std::fs::canonicalize(path).map_err(|_| AddTranslatableFileError::NoFile)?;
        self.config.make_translatable_file(path)?;
        write_conf(self.get_config_file_path(), &self.config)
            .map_err(AddTranslatableFileError::ConfigWritingError)?;
        Ok(())
    }

    /// Makes the file by given path untranslatable (for the source directory)
    pub fn make_untranslatable_file(
        &mut self,
        path: PathBuf,
    ) -> Result<(), AddTranslatableFileError> {
        let path = std::fs::canonicalize(path).map_err(|_| AddTranslatableFileError::NoFile)?;
        self.config.make_untranslatable_file(path)?;
        write_conf(self.get_config_file_path(), &self.config)
            .map_err(AddTranslatableFileError::ConfigWritingError)?;
        Ok(())
    }
}

pub fn copy_untranslatable_files(
    root_path: &Path,
    from_name: &str,
    to_name: &str,
    from_structure: &Directory,
) -> Result<(), CopyFileDirError> {
    let from_dir = root_path.clone().join(from_name);
    let to_dir = root_path.clone().join(to_name);
    copy_untranslatable_files_rec(&from_dir, &to_dir, from_structure)
}

fn copy_untranslatable_files_rec(
    from_dir: &Path,
    to_dir: &Path,
    dir: &Directory,
) -> Result<(), CopyFileDirError> {
    for file in dir.get_files_as_ref() {
        if file.is_translatable() {
            continue;
        }
        let full_path = file.get_path();
        let relative_path = full_path
            .strip_prefix(from_dir)
            .map_err(CopyFileDirError::StripPathError)?
            .to_path_buf();

        let new_path = to_dir.join(relative_path);
        let _ = std::fs::copy(full_path, new_path);
    }
    for sub_dir in dir.get_dirs_as_ref() {
        let full_path = sub_dir.get_path();
        let relative_path = full_path
            .strip_prefix(from_dir)
            .map_err(CopyFileDirError::StripPathError)?
            .to_path_buf();

        let new_path = to_dir.join(relative_path);
        if !&new_path.exists() {
            std::fs::create_dir(new_path).map_err(CopyFileDirError::IoError)?;
        }
        copy_untranslatable_files_rec(from_dir, to_dir, sub_dir)?;
    }
    Ok(())
}
