mod engine;

use engine::Engine;
use tauri::{Manager, RunEvent};

/// Relaie une requête JSON-RPC de l'interface vers le moteur Python.
#[tauri::command]
async fn engine_call(payload: String, engine: tauri::State<'_, Engine>) -> Result<String, String> {
    engine.call(payload).await
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Engine::new())
        .invoke_handler(tauri::generate_handler![engine_call])
        .build(tauri::generate_context!())
        .expect("impossible de démarrer STATPFE");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            handle.state::<Engine>().shutdown();
        }
    });
}
