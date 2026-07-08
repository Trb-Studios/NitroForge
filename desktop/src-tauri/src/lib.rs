// Nitro Forge shell: enforces single-instance, spawns the Python sidecar
// (the tested system-control core), hands its port+token to the frontend,
// and guarantees a graceful sidecar shutdown (which reverts any active
// boost) when the app exits.

use rand::distr::Alphanumeric;
use rand::Rng;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

const SIDECAR_EXE: &str = "nitro-forge-sidecar.exe";

struct Sidecar {
    port: u16,
    token: String,
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn get_sidecar_info(state: tauri::State<Sidecar>) -> serde_json::Value {
    serde_json::json!({ "port": state.port, "token": state.token })
}

/// Locate the sidecar: a bundled PyInstaller exe next to the app in release,
/// or `py sidecar/server.py` from the repo during development.
fn sidecar_command() -> Command {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(PathBuf::from));
    if let Some(dir) = exe_dir {
        let bundled = dir.join(SIDECAR_EXE);
        if bundled.is_file() {
            return Command::new(bundled);
        }
    }
    // dev: CARGO_MANIFEST_DIR = <repo>/desktop/src-tauri
    let script = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../sidecar/server.py");
    let mut cmd = Command::new("py");
    cmd.arg(script);
    cmd
}

fn spawn_sidecar(token: &str) -> Result<(u16, Child), String> {
    let mut cmd = sidecar_command();
    cmd.args(["--token", token])
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let mut child = cmd
        .spawn()
        .map_err(|e| format!("could not start Python sidecar: {e}"))?;

    // First stdout line is "PORT <n>"
    let stdout = child.stdout.take().ok_or("no sidecar stdout")?;
    let mut reader = BufReader::new(stdout);
    let mut line = String::new();
    reader
        .read_line(&mut line)
        .map_err(|e| format!("sidecar produced no port line: {e}"))?;
    let port: u16 = line
        .trim()
        .strip_prefix("PORT ")
        .and_then(|p| p.parse().ok())
        .ok_or_else(|| format!("bad sidecar handshake: {line:?}"))?;

    // Keep draining stdout so the pipe never blocks the sidecar.
    std::thread::spawn(move || {
        let mut sink = std::io::sink();
        let _ = std::io::copy(&mut reader, &mut sink);
    });
    Ok((port, child))
}

/// Kill the whole process tree. A PyInstaller onefile exe is really two
/// processes (bootloader + app); killing only the direct child would
/// orphan the inner Python process.
#[cfg(windows)]
fn kill_tree(pid: u32) {
    use std::os::windows::process::CommandExt;
    let _ = Command::new("taskkill")
        .args(["/F", "/T", "/PID", &pid.to_string()])
        .creation_flags(0x0800_0000)
        .status();
}

/// Ask the sidecar to shut down cleanly (it reverts any active boost),
/// then hard-kill the tree if it lingers. Raw HTTP over TcpStream.
fn stop_sidecar(port: u16, token: &str, child: &mut Child) {
    if let Ok(mut s) = TcpStream::connect(("127.0.0.1", port)) {
        let req = format!(
            "POST /api/shutdown HTTP/1.1\r\nHost: 127.0.0.1\r\n\
             X-NF-Token: {token}\r\nContent-Length: 0\r\n\
             Connection: close\r\n\r\n"
        );
        let _ = s.write_all(req.as_bytes());
        let _ = s.set_read_timeout(Some(Duration::from_secs(3)));
        let mut buf = [0u8; 256];
        let _ = s.read(&mut buf);
    }
    for _ in 0..20 {
        if let Ok(Some(_)) = child.try_wait() {
            return; // exited gracefully (revert ran)
        }
        std::thread::sleep(Duration::from_millis(150));
    }
    #[cfg(windows)]
    kill_tree(child.id());
    let _ = child.kill();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        // Must be registered first: a second launch focuses the existing
        // window and exits immediately (fixes the multi-instance bug).
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.unminimize();
                let _ = win.show();
                let _ = win.set_focus();
            }
        }))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        // The sidecar is spawned HERE, after the single-instance gate: a
        // blocked second launch exits before this runs, so it can never
        // leak an orphan engine process.
        .setup(|app| {
            let token: String = rand::rng()
                .sample_iter(&Alphanumeric)
                .take(40)
                .map(char::from)
                .collect();
            let (port, child) = match spawn_sidecar(&token) {
                Ok((port, child)) => (port, Some(child)),
                Err(e) => {
                    // Still open the UI so the user sees a friendly error
                    // state; the frontend detects the dead sidecar.
                    eprintln!("FATAL: {e}");
                    (0, None)
                }
            };
            app.manage(Sidecar {
                port,
                token,
                child: Mutex::new(child),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_sidecar_info])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |app_handle, event| match event {
        // The hidden overlay window would keep the process alive after the
        // main window closes, leaving a ghost instance that blocks every
        // future launch. Closing the main window must quit the app.
        tauri::RunEvent::WindowEvent {
            label,
            event: tauri::WindowEvent::Destroyed,
            ..
        } if label == "main" => {
            app_handle.exit(0);
        }
        tauri::RunEvent::Exit => {
            let state: tauri::State<Sidecar> = app_handle.state();
            let taken = state.child.lock().unwrap().take();
            if let Some(mut child) = taken {
                stop_sidecar(state.port, &state.token, &mut child);
            }
        }
        _ => {}
    });
}
