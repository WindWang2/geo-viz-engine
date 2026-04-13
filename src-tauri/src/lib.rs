use rand::distributions::Alphanumeric;
use rand::Rng;
use tauri::Manager;

/// Application state shared across Tauri commands.
pub struct AppState {
    /// 32-character random token generated at startup.
    /// Passed to Python backend via environment variable.
    pub api_token: String,
}

/// Generate a cryptographically-adequate 32-character alphanumeric token.
pub fn generate_api_token() -> String {
    rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .take(32)
        .map(char::from)
        .collect()
}

/// Tauri command: return the API token to the frontend.
/// The frontend uses this token in X-API-Token header for backend calls.
#[tauri::command]
pub fn get_api_token(app: tauri::AppHandle) -> String {
    app.state::<AppState>().api_token.clone()
}

/// Entry point called from main.rs.
pub fn run() {
    let token = generate_api_token();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            api_token: token.clone(),
        })
        .invoke_handler(tauri::generate_handler![get_api_token])
        .setup(move |app| {
            let mode = std::env::var("GEOVIZ_MODE").unwrap_or_else(|_| "prod".to_string());
            if mode == "prod" {
                // In production: spawn embedded Python sidecar
                // The sidecar binary is named geoviz-backend-<target-triple>
                // and placed in src-tauri/binaries/ at build time.
                // For Phase 1 (dev only), this branch is a no-op placeholder.
                let _ = app; // suppress unused warning
            }
            // In dev mode: Python is started separately by dev.sh
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}
