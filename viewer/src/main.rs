mod desktop;
mod follow;
mod install;
mod state;
mod update;

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use std::path::{Path, PathBuf};

const MOD: &str = "herdr-image-viewer";
const VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Parser)]
#[command(version, about)]
struct Cli {
    /// Herdr desktop configuration directory; defaults to HERDR_APP_HOME or ~/.config/herdr-app.
    #[arg(long, global = true)]
    app_home: Option<PathBuf>,
    /// Desktop executable (never the Herdr TUI command).
    #[arg(long, global = true)]
    herdr_app: Option<PathBuf>,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Install only this viewer's mod, helper and a separate "Codex + Images" menu entry.
    InstallDesktop,
    /// Launch your installed Codex and automatically show its image replies beside it.
    Codex {
        /// Explicit official Codex executable; otherwise resolved from PATH.
        #[arg(long)]
        codex: Option<PathBuf>,
        #[arg(last = true)]
        args: Vec<String>,
    },
    /// Display explicitly selected local images without a model call.
    Show {
        #[arg(required = true)]
        files: Vec<PathBuf>,
        #[arg(long)]
        no_open: bool,
    },
    /// Open the image panel for this terminal, or a manual image panel outside a terminal.
    Open,
    /// Clear this terminal's viewer; other terminals are unaffected.
    Clear,
    /// Read exactly one explicitly selected Codex rollout (no session guessing).
    Scan {
        #[arg(long)]
        session: PathBuf,
        #[arg(long)]
        thread: String,
        #[arg(long)]
        no_open: bool,
    },
    /// Open the current image in the operating system's viewer, following an explicit click.
    OpenOriginal {
        #[arg(long)]
        source: Option<String>,
        #[arg(long, default_value_t = 0)]
        index: usize,
    },
    /// Check managed installation files; does not start Herdr or a model.
    Doctor,
    /// Remove unchanged owned integration files; preserve personal files and image data.
    Uninstall,
    /// Verify and install one explicit immutable release using GitHub provenance.
    Update {
        #[arg(long)]
        version: String,
    },
    /// Print a small project-scoped instruction for calling the viewer from Codex.
    AgentHelp,
}

#[derive(Clone)]
struct ContextPaths {
    home: PathBuf,
    app: Option<PathBuf>,
}

impl ContextPaths {
    fn data(&self) -> PathBuf {
        self.home.join("data").join(MOD)
    }
    fn source(&self) -> Result<String> {
        let source = std::env::var("HC_TERMINAL_ID").unwrap_or_else(|_| "manual".into());
        valid_source(&source)?;
        Ok(source)
    }
}

fn valid_source(source: &str) -> Result<()> {
    if source != "manual" && !regex::Regex::new(r"^t[0-9a-z]+$")?.is_match(source) {
        bail!("Only a local Herdr terminal ID is supported; remote sources are not read");
    }
    Ok(())
}

fn default_home() -> Result<PathBuf> {
    if let Some(home) = std::env::var_os("HERDR_APP_HOME") {
        return Ok(home.into());
    }
    if let Some(home) = std::env::var_os("XDG_CONFIG_HOME") {
        return Ok(PathBuf::from(home).join("herdr-app"));
    }
    let home = std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
        .context("Home directory is unavailable")?;
    Ok(PathBuf::from(home).join(".config/herdr-app"))
}

fn atomic_write(path: &Path, bytes: &[u8]) -> Result<()> {
    use std::io::Write;
    let parent = path.parent().context("Missing parent directory")?;
    std::fs::create_dir_all(parent)?;
    let mut file = tempfile::NamedTempFile::new_in(parent)?;
    file.write_all(bytes)?;
    file.as_file().sync_all()?;
    file.persist(path).map_err(|e| e.error)?;
    Ok(())
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let cx = ContextPaths {
        home: std::path::absolute(cli.app_home.map(Ok).unwrap_or_else(default_home)?)?,
        app: cli.herdr_app,
    };
    match cli.command {
        Commands::InstallDesktop => install::install(&cx),
        Commands::Codex { codex, args } => follow::launch(&cx, codex, args),
        Commands::Show { files, no_open } => {
            let source = cx.source()?;
            state::publish(&cx, &source, None, &files, "Selected local images")?;
            if !no_open {
                desktop::open(&cx, &source)?;
            }
            Ok(())
        }
        Commands::Open => desktop::open(&cx, &cx.source()?),
        Commands::Clear => state::clear(&cx, &cx.source()?, None, "Waiting for an image reply"),
        Commands::Scan {
            session,
            thread,
            no_open,
        } => {
            let source = cx.source()?;
            follow::scan(&cx, &source, &session, &thread)?;
            if !no_open {
                desktop::open(&cx, &source)?;
            }
            Ok(())
        }
        Commands::OpenOriginal { source, index } => {
            state::open_original(&cx, &source.unwrap_or(cx.source()?), index)
        }
        Commands::Doctor => install::doctor(&cx),
        Commands::Uninstall => install::uninstall(&cx),
        Commands::Update { version } => update::run(&cx, &version),
        Commands::AgentHelp => {
            println!(
                "To display a local raster image beside this Codex conversation, run:\nherdr-image-viewer show <image-path>\nThis reads only the explicitly selected image. It does not change Herdr, Codex, or global agent instructions."
            );
            Ok(())
        }
    }
}
