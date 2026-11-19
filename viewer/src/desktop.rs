use crate::{ContextPaths, MOD};
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::path::PathBuf;
use std::process::Command;

fn binary(cx: &ContextPaths) -> PathBuf {
    if let Some(path) = &cx.app {
        return path.clone();
    }
    if let Some(path) = std::env::var_os("HERDR_APP_BIN") {
        return path.into();
    }
    if cfg!(windows)
        && let Some(local) = std::env::var_os("LOCALAPPDATA")
    {
        let path = PathBuf::from(local).join("Programs/herdr-app/herdr-app.exe");
        if path.is_file() {
            return path;
        }
    }
    if cfg!(target_os = "macos") {
        let path = PathBuf::from("/Applications/Herdr.app/Contents/MacOS/Herdr");
        if path.is_file() {
            return path;
        }
    }
    PathBuf::from("herdr-app")
}

pub fn call(cx: &ContextPaths, args: &[&str]) -> Result<Value> {
    let output = Command::new(binary(cx))
        .args(args)
        .env("HERDR_APP_HOME", &cx.home)
        .output()
        .context("Cannot contact Herdr desktop; open the app first")?;
    if !output.status.success() {
        bail!("Herdr: {}", String::from_utf8_lossy(&output.stderr));
    }
    let value: Value = serde_json::from_slice(&output.stdout).context("Invalid Herdr response")?;
    if let Some(error) = value.get("error") {
        bail!("Herdr: {error}");
    }
    Ok(value)
}

fn matching<'a>(value: &'a Value, test: &impl Fn(&Value) -> bool) -> Option<&'a Value> {
    if test(value) {
        return Some(value);
    }
    match value {
        Value::Object(object) => object.values().find_map(|v| matching(v, test)),
        Value::Array(array) => array.iter().find_map(|v| matching(v, test)),
        _ => None,
    }
}

pub fn open(cx: &ContextPaths, source: &str) -> Result<()> {
    crate::valid_source(source)?;
    let marker = cx.data().join("panels").join(format!("{source}.json"));
    if let Ok(bytes) = std::fs::read(&marker)
        && let Ok(previous) = serde_json::from_slice::<Value>(&bytes)
        && let Some(pane) = previous.get("pane").and_then(Value::as_str)
        && call(cx, &["do", "pane.focus", &json!({"pane":pane}).to_string()]).is_ok()
    {
        if source != "manual" {
            call(
                cx,
                &["do", "pane.focus", &json!({"terminal":source}).to_string()],
            )?;
        }
        return Ok(());
    }
    let layout = call(cx, &["ls"])?;
    if matching(&layout, &|v| {
        v.get("mod").and_then(Value::as_str) == Some(MOD)
            && v.pointer("/props/source").and_then(Value::as_str) == Some(source)
    })
    .is_some()
    {
        return Ok(());
    }
    let props = json!({"source":source});
    if source == "manual" {
        let args = json!({"name":"Images", "mod":MOD, "props":props});
        let result = call(cx, &["do", "tab.new", &args.to_string()])?;
        if let Some(pane) = result.get("pane").and_then(Value::as_str) {
            crate::atomic_write(&marker, &serde_json::to_vec(&json!({"pane":pane}))?)?;
        }
    } else {
        let pane = matching(&layout, &|v| v.get("terminal").and_then(Value::as_str) == Some(source))
            .and_then(|v| v.get("id").or_else(|| v.get("pane"))).and_then(Value::as_str)
            .context("Source terminal is not a visible Herdr pane; refusing to open beside a different terminal")?;
        let args = json!({"direction":"right", "pane":pane, "mod":MOD, "props":props});
        let result = call(cx, &["do", "pane.split", &args.to_string()])?;
        if let Some(pane) = result.get("pane").and_then(Value::as_str) {
            crate::atomic_write(&marker, &serde_json::to_vec(&json!({"pane":pane}))?)?;
        }
        call(
            cx,
            &["do", "pane.focus", &json!({"terminal":source}).to_string()],
        )?;
    }
    Ok(())
}
