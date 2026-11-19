use crate::ContextPaths;
use anyhow::{Context, Result, bail};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::Command;

const REPOSITORY: &str = "yanzzzzzzzzz/herdr-codex-images";
const REPOSITORY_ID: &str = "1462573185";
const WORKFLOW: &str = "yanzzzzzzzzz/herdr-codex-images/.github/workflows/viewer-release.yml";

fn gh(args: &[&str]) -> Result<Vec<u8>> {
    let output = Command::new("gh")
        .args(args)
        .output()
        .context("Verified updates require GitHub CLI (gh); no downloaded program was executed")?;
    if !output.status.success() {
        bail!(
            "GitHub verification/download failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    Ok(output.stdout)
}

pub fn asset() -> Result<&'static str> {
    match (std::env::consts::OS, std::env::consts::ARCH) {
        ("windows", "x86_64") => Ok("herdr-image-viewer-windows-x64.exe"),
        ("macos", "aarch64") => Ok("herdr-image-viewer-macos-arm64"),
        ("linux", "x86_64") => Ok("herdr-image-viewer-linux-x64"),
        _ => bail!("No prebuilt viewer for this architecture; build from the reviewed source"),
    }
}

fn validate_release(release: &Value, version: &str) -> Result<()> {
    if !regex::Regex::new(r"^viewer-v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$")?
        .is_match(version)
    {
        bail!("Use an explicit viewer-vX.Y.Z release tag");
    }
    if release["immutable"] != true || release["draft"] != false || release["tag_name"] != version {
        bail!("Only published immutable viewer releases can be installed by update");
    }
    Ok(())
}

fn verify(binary: &Path, bundle: &Path, version: &str, commit: &str) -> Result<()> {
    let binary = binary.to_str().context("Invalid binary path")?;
    let bundle = bundle.to_str().context("Invalid bundle path")?;
    let output = gh(&[
        "attestation",
        "verify",
        binary,
        "--bundle",
        bundle,
        "--repo",
        REPOSITORY,
        "--signer-workflow",
        WORKFLOW,
        "--source-ref",
        &format!("refs/tags/{version}"),
        "--source-digest",
        commit,
        "--deny-self-hosted-runners",
        "--format",
        "json",
    ])?;
    let verified: Value = serde_json::from_slice(&output)?;
    let certificates = verified
        .as_array()
        .context("Invalid attestation verification result")?;
    if certificates.is_empty()
        || certificates.iter().any(|v| {
            v.pointer("/verificationResult/signature/certificate/sourceRepositoryIdentifier")
                .and_then(Value::as_str)
                != Some(REPOSITORY_ID)
        })
    {
        bail!("Attestation does not identify the expected repository ID");
    }
    Ok(())
}

pub fn run(cx: &ContextPaths, version: &str) -> Result<()> {
    if !regex::Regex::new(r"^viewer-v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$")?
        .is_match(version)
    {
        bail!("Invalid viewer release tag");
    }
    let release: Value = serde_json::from_slice(&gh(&[
        "api",
        &format!("repos/{REPOSITORY}/releases/tags/{version}"),
    ])?)?;
    validate_release(&release, version)?;
    let commit = String::from_utf8(gh(&[
        "api",
        &format!("repos/{REPOSITORY}/commits/{version}"),
        "--jq",
        ".sha",
    ])?)?
    .trim()
    .to_owned();
    if !regex::Regex::new(r"^[a-f0-9]{40}$")?.is_match(&commit) {
        bail!("Invalid source commit");
    }
    let temporary = tempfile::tempdir()?;
    let directory = temporary
        .path()
        .to_str()
        .context("Invalid temporary directory")?;
    let name = asset()?;
    for pattern in [name, "viewer-provenance.jsonl"] {
        gh(&[
            "release",
            "download",
            version,
            "--repo",
            REPOSITORY,
            "--pattern",
            pattern,
            "--dir",
            directory,
        ])?;
    }
    let binary: PathBuf = temporary.path().join(name);
    verify(
        &binary,
        &temporary.path().join("viewer-provenance.jsonl"),
        version,
        &commit,
    )?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&binary, std::fs::Permissions::from_mode(0o755))?;
    }
    // This is the first execution of the new binary, after all provenance policy checks.
    if !Command::new(&binary)
        .arg("--app-home")
        .arg(&cx.home)
        .arg("install-desktop")
        .status()?
        .success()
    {
        bail!("Verified viewer installation failed; existing processes were not stopped");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn mutable_draft_wrong_version_and_legacy_releases_are_rejected() {
        let version = "viewer-v0.2.0-preview.1";
        let good = serde_json::json!({"immutable":true,"draft":false,"tag_name":version});
        validate_release(&good, version).unwrap();
        for bad in [
            serde_json::json!({"immutable":false,"draft":false,"tag_name":version}),
            serde_json::json!({"immutable":true,"draft":true,"tag_name":version}),
            serde_json::json!({"immutable":true,"draft":false,"tag_name":"v0.1.0-preview.3"}),
        ] {
            assert!(validate_release(&bad, version).is_err());
        }
        assert!(validate_release(&good, "../../main").is_err());
    }
}
