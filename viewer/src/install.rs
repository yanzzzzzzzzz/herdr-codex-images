use crate::{ContextPaths, MOD, VERSION, atomic_write, state};
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

#[derive(Serialize, Deserialize)]
struct Installation {
    owner: String,
    version: String,
    files: BTreeMap<String, String>,
    program: Value,
}

fn managed(cx: &ContextPaths, relative: &str) -> Result<PathBuf> {
    let path = cx.home.join(relative);
    if !path.starts_with(&cx.home)
        || Path::new(relative)
            .components()
            .any(|c| matches!(c, std::path::Component::ParentDir))
    {
        bail!("Path escaped the application home");
    }
    let mut cursor = Some(path.as_path());
    while let Some(p) = cursor {
        if std::fs::symlink_metadata(p).is_ok_and(|m| m.file_type().is_symlink()) {
            bail!("Managed path is a symbolic link: {}", p.display());
        }
        if p == cx.home {
            break;
        }
        cursor = p.parent();
    }
    Ok(path)
}

fn record_path(cx: &ContextPaths) -> Result<PathBuf> {
    managed(cx, "data/herdr-image-viewer/installation.json")
}

fn read_record(cx: &ContextPaths) -> Result<Option<Installation>> {
    let path = record_path(cx)?;
    if !path.exists() {
        return Ok(None);
    }
    let record: Installation = serde_json::from_slice(&std::fs::read(path)?)?;
    if record.owner != MOD {
        bail!("Unmanaged installation record");
    }
    let owned = regex::Regex::new(
        r"^(mods/herdr-image-viewer/(main\.js|mod\.json)|data/herdr-image-viewer/bin/[A-Za-z0-9.-]+/herdr-image-viewer(\.exe)?)$",
    )?;
    if record.files.keys().any(|path| !owned.is_match(path)) {
        bail!("Installation record names files outside this viewer's owned paths");
    }
    Ok(Some(record))
}

fn programs(cx: &ContextPaths) -> Result<Value> {
    let path = managed(cx, "programs.json")?;
    let value = if path.exists() {
        serde_json::from_slice(&std::fs::read(path)?)?
    } else {
        json!({})
    };
    if !value.is_object() || value.get("programs").is_some_and(|v| !v.is_object()) {
        bail!("Unexpected programs.json structure; no files changed");
    }
    Ok(value)
}

pub fn install(cx: &ContextPaths) -> Result<()> {
    let record = read_record(cx)?;
    let mut programs = programs(cx)?;
    let existing_entry = programs.pointer(&format!("/programs/{MOD}"));
    if existing_entry.is_some()
        && record
            .as_ref()
            .is_none_or(|r| Some(&r.program) != existing_entry)
    {
        bail!("An unrelated or edited program entry exists; refusing to replace it");
    }
    if let Some(record) = &record {
        for (relative, expected) in &record.files {
            let path = managed(cx, relative)?;
            if !path.is_file() || state::digest(&std::fs::read(path)?) != *expected {
                bail!(
                    "Managed file was edited or removed: {relative}; personal changes are retained"
                );
            }
        }
    } else {
        let folder = managed(cx, &format!("mods/{MOD}"))?;
        if folder.is_dir() && std::fs::read_dir(folder)?.next().is_some() {
            bail!("An unmanaged image-viewer mod exists");
        }
    }
    let name = if cfg!(windows) {
        "herdr-image-viewer.exe"
    } else {
        "herdr-image-viewer"
    };
    let relative_bin = format!("data/{MOD}/bin/{VERSION}/{name}");
    let binary = managed(cx, &relative_bin)?;
    let executable = std::fs::read(std::env::current_exe()?)?;
    if binary.exists() && state::digest(&std::fs::read(&binary)?) != state::digest(&executable) {
        bail!("Same-version executable differs; use a new version instead of replacing it");
    }
    let mod_js = include_str!("../desktop/main.js")
        .replace("__VIEWER_DATA__", &serde_json::to_string(&cx.data())?)
        .replace("__VIEWER_BIN__", &serde_json::to_string(&binary)?)
        .replace("__VIEWER_HOME__", &serde_json::to_string(&cx.home)?);
    let program = json!({"name":"Codex + Images", "run":[binary,"--app-home",cx.home,"codex"], "color":"#63b3ed", "tile":"#17191c"});
    if programs.get("programs").is_none() {
        programs["programs"] = json!({});
    }
    programs["programs"][MOD] = program.clone();
    let mut writes = vec![
        (format!("mods/{MOD}/main.js"), mod_js.into_bytes()),
        (
            format!("mods/{MOD}/mod.json"),
            include_bytes!("../desktop/mod.json").to_vec(),
        ),
    ];
    if !binary.exists() {
        writes.push((relative_bin.clone(), executable));
    }
    let mut files = BTreeMap::new();
    for (path, data) in &writes {
        files.insert(path.clone(), state::digest(data));
    }
    if !files.contains_key(&relative_bin) {
        files.insert(
            relative_bin.clone(),
            state::digest(&std::fs::read(&binary)?),
        );
    }
    let new_record = Installation {
        owner: MOD.into(),
        version: VERSION.into(),
        files,
        program,
    };
    let programs_path = managed(cx, "programs.json")?;
    if programs_path.exists() {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos();
        atomic_write(
            &managed(cx, &format!("data/{MOD}/backups/programs-{stamp}.json"))?,
            &std::fs::read(&programs_path)?,
        )?;
    }
    writes.push((
        "programs.json".into(),
        serde_json::to_vec_pretty(&programs)?,
    ));
    writes.push((
        format!("data/{MOD}/installation.json"),
        serde_json::to_vec_pretty(&new_record)?,
    ));
    let mut changed: Vec<(PathBuf, Option<Vec<u8>>)> = Vec::new();
    let transaction: Result<()> = (|| {
        for (relative, bytes) in writes {
            let path = managed(cx, &relative)?;
            let before = if path.exists() {
                Some(std::fs::read(&path)?)
            } else {
                None
            };
            atomic_write(&path, &bytes)?;
            changed.push((path, before));
        }
        Ok(())
    })();
    if let Err(error) = transaction {
        for (path, before) in changed.into_iter().rev() {
            match before {
                Some(bytes) => {
                    atomic_write(&path, &bytes).context("Installation rollback failed")?;
                }
                None => {
                    std::fs::remove_file(path).context("Installation rollback failed")?;
                }
            }
        }
        return Err(error);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&binary, std::fs::Permissions::from_mode(0o755))?;
        std::fs::set_permissions(cx.data(), std::fs::Permissions::from_mode(0o700))?;
    }
    std::fs::create_dir_all(cx.data().join("state"))?;
    println!(
        "Installed Codex + Images in {}. Original Herdr, Codex, profiles and sessions were not replaced.",
        cx.home.display()
    );
    Ok(())
}

pub fn doctor(cx: &ContextPaths) -> Result<()> {
    let record = read_record(cx)?.context("Viewer is not installed")?;
    for (relative, expected) in record.files {
        if state::digest(&std::fs::read(managed(cx, &relative)?)?) != expected {
            bail!("File changed: {relative}");
        }
    }
    if programs(cx)?.pointer(&format!("/programs/{MOD}")) != Some(&record.program) {
        bail!("Viewer program entry changed");
    }
    println!("OK: installed viewer files and menu entry match; no app or model was started.");
    Ok(())
}

pub fn uninstall(cx: &ContextPaths) -> Result<()> {
    let Some(record) = read_record(cx)? else {
        println!("No managed installation.");
        return Ok(());
    };
    let mut programs = programs(cx)?;
    if programs.pointer(&format!("/programs/{MOD}")) == Some(&record.program) {
        programs["programs"]
            .as_object_mut()
            .context("Invalid programs object")?
            .remove(MOD);
        atomic_write(
            &managed(cx, "programs.json")?,
            &serde_json::to_vec_pretty(&programs)?,
        )?;
    } else {
        println!("Retained edited program entry.");
    }
    for (relative, expected) in record.files {
        if !relative.starts_with("mods/") {
            continue;
        } // Running helpers and cached data stay intact.
        let path = managed(cx, &relative)?;
        if path.is_file() && state::digest(&std::fs::read(&path)?) == expected {
            std::fs::remove_file(path)?;
        } else if path.exists() {
            println!("Retained personal changes: {relative}");
        }
    }
    std::fs::remove_file(record_path(cx)?)?;
    println!(
        "Removed unchanged viewer integration. Cached images, backups, helper versions and running sessions are retained."
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn install_reinstall_uninstall_preserve_personal_files() {
        let temp = tempfile::tempdir().unwrap();
        let cx = ContextPaths {
            home: temp.path().join("home with spaces"),
            app: None,
        };
        std::fs::create_dir_all(&cx.home).unwrap();
        let settings = b"{\"zoom\":1.25}";
        std::fs::write(cx.home.join("settings.json"), settings).unwrap();
        std::fs::write(
            cx.home.join("programs.json"),
            b"{\"programs\":{\"my-tool\":{\"run\":[\"personal\"]}},\"extra\":true}",
        )
        .unwrap();
        install(&cx).unwrap();
        doctor(&cx).unwrap();
        install(&cx).unwrap();
        let mod_file = cx.home.join("mods/herdr-image-viewer/main.js");
        std::fs::write(&mod_file, "// personal edit").unwrap();
        assert!(install(&cx).is_err());
        uninstall(&cx).unwrap();
        assert_eq!(
            std::fs::read(cx.home.join("settings.json")).unwrap(),
            settings
        );
        assert_eq!(
            std::fs::read_to_string(mod_file).unwrap(),
            "// personal edit"
        );
        let programs = programs(&cx).unwrap();
        assert_eq!(programs["programs"]["my-tool"]["run"][0], "personal");
        assert_eq!(programs["extra"], true);
    }
    #[test]
    fn foreign_mod_and_program_are_never_overwritten() {
        let temp = tempfile::tempdir().unwrap();
        let cx = ContextPaths {
            home: temp.path().into(),
            app: None,
        };
        std::fs::create_dir_all(cx.home.join("mods/herdr-image-viewer")).unwrap();
        std::fs::write(cx.home.join("mods/herdr-image-viewer/custom.txt"), "mine").unwrap();
        assert!(install(&cx).is_err());
        assert!(!cx.home.join("programs.json").exists());
    }
}
