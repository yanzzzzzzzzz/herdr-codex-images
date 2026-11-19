use crate::{ContextPaths, atomic_write, valid_source};
use anyhow::{Context, Result, bail};
use image::ImageFormat;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::Cursor;
use std::path::{Path, PathBuf};

const MAX_FILE: u64 = 32 * 1024 * 1024;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Preview {
    pub original: PathBuf,
    pub preview: PathBuf,
    pub name: String,
    pub width: u32,
    pub height: u32,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Snapshot {
    pub source: String,
    pub thread: Option<String>,
    pub message: String,
    pub images: Vec<Preview>,
}

pub fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn reject_network(path: &Path) -> Result<()> {
    let text = path.to_string_lossy();
    if text.starts_with("\\\\") || text.starts_with("//") || text.contains("://") {
        bail!("Network paths and URLs are not loaded");
    }
    Ok(())
}

pub fn decode(path: &Path) -> Result<(PathBuf, image::DynamicImage, String)> {
    reject_network(path)?;
    let extension = path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if !["png", "jpg", "jpeg", "gif", "webp", "bmp"].contains(&extension.as_str()) {
        bail!("Supported local images: PNG, JPEG, GIF, WebP, BMP");
    }
    let canonical = path.canonicalize().context("Image does not exist")?;
    // std::canonicalize adds the Windows verbatim prefix; the user-supplied path
    // was checked before resolution, so this is not a user-supplied UNC request.
    let file = std::fs::File::open(&canonical)?;
    let metadata = file.metadata()?;
    if !metadata.is_file() || metadata.len() == 0 || metadata.len() > MAX_FILE {
        bail!("Image must be a regular file of at most 32 MiB");
    }
    use std::io::Read;
    let mut bytes = Vec::new();
    file.take(MAX_FILE + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_FILE {
        bail!("Image grew beyond the size limit");
    }
    let mut reader = image::ImageReader::new(Cursor::new(&bytes)).with_guessed_format()?;
    if !matches!(
        reader.format(),
        Some(
            ImageFormat::Png
                | ImageFormat::Jpeg
                | ImageFormat::Gif
                | ImageFormat::WebP
                | ImageFormat::Bmp
        )
    ) {
        bail!("Unsupported image contents");
    }
    let mut limits = image::Limits::default();
    limits.max_alloc = Some(64 * 1024 * 1024);
    limits.max_image_width = Some(16384);
    limits.max_image_height = Some(16384);
    reader.limits(limits);
    let decoded = reader
        .decode()
        .context("Image exceeds the decoder budget or is invalid")?;
    if u64::from(decoded.width()) * u64::from(decoded.height()) * 4 > 64 * 1024 * 1024 {
        bail!("Decoded image exceeds 64 MiB");
    }
    #[cfg(windows)]
    let canonical = canonical
        .to_str()
        .and_then(|s| s.strip_prefix(r"\\?\"))
        .map(PathBuf::from)
        .unwrap_or(canonical);
    Ok((canonical, decoded, digest(&bytes)))
}

fn save(cx: &ContextPaths, source: &str, snapshot: &Snapshot) -> Result<()> {
    valid_source(source)?;
    let path = cx.data().join("state").join(format!("{source}.json"));
    let bytes = serde_json::to_vec(snapshot)?;
    if std::fs::read(&path).ok().as_deref() != Some(bytes.as_slice()) {
        atomic_write(&path, &bytes)?;
    }
    Ok(())
}

pub fn clear(cx: &ContextPaths, source: &str, thread: Option<&str>, message: &str) -> Result<()> {
    save(
        cx,
        source,
        &Snapshot {
            source: source.into(),
            thread: thread.map(Into::into),
            message: message.into(),
            images: vec![],
        },
    )
}

pub fn publish(
    cx: &ContextPaths,
    source: &str,
    thread: Option<&str>,
    paths: &[PathBuf],
    message: &str,
) -> Result<()> {
    valid_source(source)?;
    let mut previews = Vec::new();
    for path in paths.iter().take(8) {
        let (original, decoded, hash) = decode(path)?;
        if previews.iter().any(|p: &Preview| p.original == original) {
            continue;
        }
        let preview = cx.data().join("images").join(format!("{hash}.png"));
        if !preview.is_file() {
            let mut encoded = Cursor::new(Vec::new());
            decoded.write_to(&mut encoded, ImageFormat::Png)?;
            if encoded.get_ref().len() > 16 * 1024 * 1024 {
                bail!("Normalized PNG exceeds the Herdr mod asset limit of 16 MiB");
            }
            atomic_write(&preview, &encoded.into_inner())?;
        }
        previews.push(Preview {
            name: original
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .into(),
            original,
            preview,
            width: decoded.width(),
            height: decoded.height(),
        });
    }
    save(
        cx,
        source,
        &Snapshot {
            source: source.into(),
            thread: thread.map(Into::into),
            message: message.into(),
            images: previews,
        },
    )
}

pub fn open_original(cx: &ContextPaths, source: &str, index: usize) -> Result<()> {
    valid_source(source)?;
    let snapshot: Snapshot = serde_json::from_slice(&std::fs::read(
        cx.data().join("state").join(format!("{source}.json")),
    )?)?;
    let first = snapshot.images.get(index).context("No image is selected")?;
    // Revalidate before handing a path to the user's configured image viewer.
    let _ = decode(&first.original)?;
    let mut command = if cfg!(windows) {
        let mut c = std::process::Command::new(
            PathBuf::from(std::env::var_os("SystemRoot").context("Missing SystemRoot")?)
                .join("System32/rundll32.exe"),
        );
        c.arg("url.dll,FileProtocolHandler");
        c
    } else if cfg!(target_os = "macos") {
        std::process::Command::new("/usr/bin/open")
    } else {
        std::process::Command::new("xdg-open")
    };
    if !command.arg(&first.original).status()?.success() {
        bail!("The operating system image viewer failed");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn hostile_inputs_are_rejected_before_opening() {
        for p in [
            "https://example.com/x.png",
            "//server/x.png",
            "\\\\server\\x.png",
            "program.exe",
        ] {
            assert!(decode(Path::new(p)).is_err());
        }
    }
    #[test]
    fn real_pixels_are_retained_and_other_terminals_are_isolated() {
        let temp = tempfile::tempdir().unwrap();
        let cx = ContextPaths {
            home: temp.path().join("home"),
            app: None,
        };
        let input = temp.path().join("photo #1.png");
        image::RgbaImage::from_pixel(800, 400, image::Rgba([9, 23, 200, 255]))
            .save(&input)
            .unwrap();
        publish(&cx, "t1", Some("thread-a"), &[input], "Reply").unwrap();
        clear(&cx, "t2", Some("thread-b"), "Empty").unwrap();
        let snapshot: Snapshot =
            serde_json::from_slice(&std::fs::read(cx.data().join("state/t1.json")).unwrap())
                .unwrap();
        let decoded = image::open(&snapshot.images[0].preview).unwrap();
        assert_eq!((decoded.width(), decoded.height()), (800, 400));
        assert_eq!(decoded.to_rgba8().get_pixel(0, 0).0, [9, 23, 200, 255]);
        assert_eq!(snapshot.thread.as_deref(), Some("thread-a"));
        assert!(publish(&cx, "../outside", None, &[], "bad").is_err());
    }
}
