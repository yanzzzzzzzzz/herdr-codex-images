use crate::{ContextPaths, desktop, state};
use anyhow::{Context, Result, bail};
use pulldown_cmark::{Event, Parser, Tag};
use regex::Regex;
use serde_json::Value;
use std::io::{BufRead, BufReader, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};
use std::time::Duration;

const HISTORY_BYTES: u64 = 8 * 1024 * 1024;

fn thread_pattern() -> Regex {
    Regex::new(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
        .expect("constant expression")
}

fn footer_thread(screen: &str) -> Option<String> {
    let pattern = thread_pattern();
    let mut found: Vec<_> = screen
        .lines()
        .rev()
        .take(4)
        .filter_map(|line| {
            pattern
                .find(line.trim())
                .filter(|m| m.as_str() == line.trim())
                .map(|m| m.as_str().to_ascii_lowercase())
        })
        .collect();
    found.sort();
    found.dedup();
    if found.len() == 1 { found.pop() } else { None }
}

fn codex_home() -> Result<PathBuf> {
    if let Some(home) = std::env::var_os("CODEX_HOME") {
        return Ok(home.into());
    }
    let home = std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
        .context("Missing home directory")?;
    Ok(PathBuf::from(home).join(".codex"))
}

fn exact_rollout(home: &Path, thread: &str) -> Result<PathBuf> {
    if thread_pattern()
        .find(thread)
        .is_none_or(|m| m.as_str() != thread)
    {
        bail!("Invalid exact session ID");
    }
    let suffix = format!("{thread}.jsonl");
    let mut found = Vec::new();
    // Only filenames are inspected. No unrelated session contents are opened.
    for entry in walkdir::WalkDir::new(home.join("sessions"))
        .follow_links(false)
        .max_depth(6)
    {
        let entry = entry?;
        if entry.file_type().is_file()
            && entry
                .file_name()
                .to_string_lossy()
                .to_ascii_lowercase()
                .ends_with(&suffix)
        {
            found.push(entry.into_path());
        }
    }
    if found.len() != 1 {
        bail!("Exact Codex rollout is missing or ambiguous; no other session was selected");
    }
    Ok(found.remove(0))
}

fn paths_from_reply(markdown: &str, cwd: &Path) -> Result<Vec<PathBuf>> {
    let root = cwd.canonicalize()?;
    let mut paths = Vec::new();
    for event in Parser::new(markdown) {
        let destination = match event {
            Event::Start(Tag::Link { dest_url, .. } | Tag::Image { dest_url, .. }) => {
                dest_url.into_string()
            }
            Event::Code(path) => path.into_string(),
            _ => continue,
        };
        if destination.len() > 8192
            || destination.chars().any(char::is_control)
            || destination.starts_with('~')
        {
            continue;
        }
        let raw = PathBuf::from(&destination);
        let candidate = if raw.is_absolute() {
            if state::reject_network(&raw).is_err() {
                continue;
            }
            raw
        } else if let Ok(url) = url::Url::parse(&destination) {
            if url.scheme() != "file"
                || url.host().is_some()
                || url.query().is_some()
                || url.fragment().is_some()
            {
                continue;
            }
            let Ok(path) = url.to_file_path() else {
                continue;
            };
            if state::reject_network(&path).is_err() {
                continue;
            }
            path
        } else {
            if state::reject_network(&raw).is_err() {
                continue;
            }
            cwd.join(raw)
        };
        let Ok(canonical) = candidate.canonicalize() else {
            continue;
        };
        // Automatic previews stay inside the exact session's workspace. Explicit
        // `show` is available when the user wants an image elsewhere.
        if !canonical.starts_with(&root) || !canonical.is_file() {
            continue;
        }
        let extension = canonical
            .extension()
            .and_then(|v| v.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        if !["png", "jpg", "jpeg", "gif", "bmp", "webp"].contains(&extension.as_str()) {
            continue;
        }
        if !paths.contains(&candidate) {
            paths.push(candidate);
        }
        if paths.len() == 8 {
            break;
        }
    }
    Ok(paths)
}

pub fn scan(cx: &ContextPaths, source: &str, session: &Path, thread: &str) -> Result<()> {
    state::reject_network(session)?;
    let file = std::fs::File::open(session)?;
    let mut header = String::new();
    BufReader::new(file.take(1024 * 1024)).read_line(&mut header)?;
    let metadata: Value = serde_json::from_str(&header).context("Invalid rollout header")?;
    if metadata["type"] != "session_meta" || metadata["payload"]["id"].as_str() != Some(thread) {
        bail!("Rollout identity does not match the selected Codex session");
    }
    let cwd = metadata["payload"]["cwd"]
        .as_str()
        .context("Session has no working directory")?;
    state::reject_network(Path::new(cwd))?;
    let mut file = std::fs::File::open(session)?;
    let offset = file.metadata()?.len().saturating_sub(HISTORY_BYTES);
    file.seek(SeekFrom::Start(offset))?;
    let mut bytes = Vec::new();
    file.take(HISTORY_BYTES).read_to_end(&mut bytes)?;
    let start = if offset > 0 {
        bytes
            .iter()
            .position(|b| *b == b'\n')
            .map_or(bytes.len(), |i| i + 1)
    } else {
        0
    };
    let mut latest = None;
    for line in bytes[start..].split_inclusive(|b| *b == b'\n') {
        if !line.ends_with(b"\n") {
            continue;
        } // Never render an in-progress journal record.
        let Ok(record) = serde_json::from_slice::<Value>(line) else {
            continue;
        };
        let payload = &record["payload"];
        if record["type"] == "response_item"
            && payload["type"] == "message"
            && payload["role"] == "assistant"
            && payload["phase"] == "final_answer"
        {
            let text = payload["content"]
                .as_array()
                .into_iter()
                .flatten()
                .filter(|item| item["type"] == "output_text")
                .filter_map(|item| item["text"].as_str())
                .collect::<Vec<_>>()
                .join("\n");
            latest = Some(text);
        } else if record["type"] == "event_msg"
            && payload["type"] == "task_complete"
            && let Some(text) = payload["last_agent_message"].as_str()
        {
            latest = Some(text.to_owned());
        }
    }
    let paths = paths_from_reply(latest.as_deref().unwrap_or(""), Path::new(cwd))?;
    if paths.is_empty() {
        state::clear(
            cx,
            source,
            Some(thread),
            "No supported local images in the latest completed reply",
        )
    } else {
        state::publish(
            cx,
            source,
            Some(thread),
            &paths,
            "Latest completed Codex reply · local workspace images",
        )
    }
}

fn hc() -> PathBuf {
    if cfg!(windows)
        && let Some(local) = std::env::var_os("LOCALAPPDATA")
    {
        let path = PathBuf::from(local).join("Programs/herdr-core/hc.exe");
        if path.is_file() {
            return path;
        }
    }
    PathBuf::from("hc")
}

fn installed_codex() -> PathBuf {
    // Prefer the ordinary npm installation over a legacy preview's PATH block.
    if cfg!(windows)
        && let Some(programs) = std::env::var_os("ProgramFiles")
    {
        let path = PathBuf::from(programs).join("nodejs/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe");
        if path.is_file() {
            return path;
        }
    }
    PathBuf::from("codex")
}

fn standalone_codex(mut command: Command) -> Command {
    // A CLI installed through npm has no Windows app package identity. Herdr
    // can inherit this desktop-only request when started by the Codex app.
    // Let the standalone CLI use its own sandbox runtime; keep its policy.
    command.env_remove("CODEX_WINDOWS_REGISTERED_CORE");
    command
}

pub fn launch(cx: &ContextPaths, codex: Option<PathBuf>, mut args: Vec<String>) -> Result<()> {
    if args
        .iter()
        .any(|a| a == "--remote" || a.starts_with("--remote="))
    {
        bail!("Remote app-server workspaces are not supported by this local viewer");
    }
    if !args.iter().any(|a| a == "--no-daemon") {
        args.insert(0, "--no-daemon".into());
    }
    let source = std::env::var("HC_TERMINAL_ID")
        .context("Launch Codex + Images from a local Herdr desktop terminal")?;
    crate::valid_source(&source)?;
    let home = codex_home()?;
    state::clear(
        cx,
        &source,
        None,
        "Waiting for this Codex session's first image reply…",
    )?;
    desktop::open(cx, &source)?;
    let stop = Arc::new(AtomicBool::new(false));
    let stopped = Arc::clone(&stop);
    let context = cx.clone();
    let worker = std::thread::spawn(move || {
        let mut current = None;
        let mut fingerprint = None;
        while !stopped.load(Ordering::Relaxed) {
            let result: Result<()> = (|| {
                let output = Command::new(hc())
                    .args(["read", &source, "--lines", "0"])
                    .output()?;
                if !output.status.success() {
                    bail!("Cannot read the source terminal");
                }
                let Some(thread) = footer_thread(&String::from_utf8_lossy(&output.stdout)) else {
                    return Ok(());
                };
                if current.as_deref() != Some(thread.as_str()) {
                    state::clear(
                        &context,
                        &source,
                        Some(&thread),
                        "Waiting for this exact Codex session…",
                    )?;
                    current = Some(thread.clone());
                    fingerprint = None;
                }
                let file = exact_rollout(&home, &thread)?;
                let meta = std::fs::metadata(&file)?;
                let next = (file.clone(), meta.len(), meta.modified()?);
                if fingerprint.as_ref() != Some(&next) {
                    scan(&context, &source, &file, &thread)?;
                    fingerprint = Some(next);
                }
                Ok(())
            })();
            if let Err(error) = result {
                let _ = state::clear(&context, &source, current.as_deref(), &error.to_string());
            }
            std::thread::sleep(Duration::from_millis(650));
        }
    });
    let status = standalone_codex(Command::new(codex.unwrap_or_else(installed_codex)))
        .args(["-c", "tui.status_line=[\"thread-id\"]"])
        .args(args)
        .env("HERDR_APP_HOME", &cx.home)
        .env("HERDR_IMAGE_VIEWER_BIN", std::env::current_exe()?)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status();
    stop.store(true, Ordering::Relaxed);
    let _ = worker.join();
    if !status
        .context("Cannot start the installed Codex executable")?
        .success()
    {
        bail!("Codex exited unsuccessfully");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    const ID: &str = "01a1f16a-b961-7a30-8e37-ff45f5d601d4";
    #[test]
    fn standalone_launch_excludes_the_desktop_package_request() {
        let mut inherited = Command::new("codex");
        inherited.env("CODEX_WINDOWS_REGISTERED_CORE", "1");
        inherited.env("VIEWER_TEST_PRESERVED", "keep");
        let command = standalone_codex(inherited);
        let environment: std::collections::BTreeMap<_, _> = command.get_envs().collect();
        assert_eq!(
            environment.get(std::ffi::OsStr::new("CODEX_WINDOWS_REGISTERED_CORE")),
            Some(&None)
        );
        assert_eq!(
            environment.get(std::ffi::OsStr::new("VIEWER_TEST_PRESERVED")),
            Some(&Some(std::ffi::OsStr::new("keep")))
        );
        assert!(command.get_args().next().is_none());
    }

    #[cfg(windows)]
    #[test]
    fn standalone_child_really_does_not_receive_the_desktop_flag() {
        let mut inherited = Command::new("cmd.exe");
        inherited.env("CODEX_WINDOWS_REGISTERED_CORE", "1");
        inherited.env("VIEWER_TEST_PRESERVED", "keep");
        let output = standalone_codex(inherited)
            .args([
                "/D",
                "/C",
                "if defined CODEX_WINDOWS_REGISTERED_CORE (exit /b 9) else (echo %VIEWER_TEST_PRESERVED%)",
            ])
            .output()
            .unwrap();
        assert!(output.status.success());
        assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "keep");
    }

    #[test]
    fn only_the_footer_can_bind_a_session() {
        assert_eq!(footer_thread(&format!("prompt {ID}\n1\n2\n3\n4\n5")), None);
        assert_eq!(
            footer_thread(&format!("reply\n{ID}\nhelp")),
            Some(ID.into())
        );
        assert_eq!(
            footer_thread(&format!("{ID}\n01a1f16a-b961-7a30-8e37-ff45f5d601d5")),
            None
        );
    }
    #[test]
    fn prompts_code_examples_and_other_sessions_never_become_images() {
        let temp = tempfile::tempdir().unwrap();
        let cx = ContextPaths {
            home: temp.path().join("app"),
            app: None,
        };
        let image = temp.path().join("example.png");
        image::RgbaImage::new(10, 10).save(&image).unwrap();
        let file = temp.path().join("rollout.jsonl");
        let records = [
            serde_json::json!({"type":"session_meta","payload":{"id":ID,"cwd":temp.path()}}),
            serde_json::json!({"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"![secret](example.png)"}]}}),
            serde_json::json!({"type":"response_item","payload":{"type":"message","role":"assistant","phase":"final_answer","content":[{"type":"output_text","text":"```md\n![example](example.png)\n```"}]}}),
        ];
        std::fs::write(
            &file,
            records.iter().map(|r| format!("{r}\n")).collect::<String>(),
        )
        .unwrap();
        scan(&cx, "t1", &file, ID).unwrap();
        let value: Value =
            serde_json::from_slice(&std::fs::read(cx.data().join("state/t1.json")).unwrap())
                .unwrap();
        assert_eq!(value["images"].as_array().unwrap().len(), 0);
        assert!(scan(&cx, "t2", &file, "different-thread").is_err());
        assert!(
            paths_from_reply("[x](https://example.com/image.png)", temp.path())
                .unwrap()
                .is_empty()
        );
        assert!(
            paths_from_reply("[x](../example.png)", &temp.path().join("app"))
                .unwrap()
                .is_empty()
        );
    }
}
