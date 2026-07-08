// FPSBooster shell: spawns the Python sidecar (the tested system-control
// core), hands its port+token to the frontend, and guarantees a graceful
// sidecar shutdown (which reverts any active boost) when the app exits.

use rand::distr::Alphanumeric;
use rand::Rng;
use tauri::Manager;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

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
        let bundled = dir.join("FPSBoosterSidecar.exe");
        if bundled.is_file() {
            return Command::new(bundled);
        }
    }
    // dev: CARGO_MANIFEST_DIR = <repo>/app/src-tauri
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

/// Ask the sidecar to shut down cleanly (it reverts any active boost),
/// then hard-kill if it lingers. Raw HTTP over TcpStream - no client dep.
fn stop_sidecar(port: u16, token: &str, child: &mut Child) {
    if let Ok(mut s) = TcpStream::connect(("127.0.0.1", port)) {
        let req = format!(
            "POST /api/shutdown HTTP/1.1\r\nHost: 127.0.0.1\r\n\
             X-FPSB-Token: {token}\r\nContent-Length: 0\r\n\
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
    let _ = child.kill();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let token: String = rand::rng()
        .sample_iter(&Alphanumeric)
        .take(40)
        .map(char::from)
        .collect();
    let (port, child) = match spawn_sidecar(&token) {
        Ok(ok) => ok,
        Err(e) => {
            eprintln!("FATAL: {e}");
            // Still open the UI so the user sees an error state instead of
            // nothing; the frontend shows a friendly message when the
            // sidecar is unreachable.
            (0, Command::new("cmd").arg("/c").arg("exit").spawn().unwrap())
        }
    };

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Sidecar {
            port,
            token: token.clone(),
            child: Mutex::new(Some(child)),
        })
        .invoke_handler(tauri::generate_handler![get_sidecar_info])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            let state: tauri::State<Sidecar> = app_handle.state();
            let taken = state.child.lock().unwrap().take();
            if let Some(mut child) = taken {
                stop_sidecar(state.port, &state.token, &mut child);
            }
        }
    });
}
