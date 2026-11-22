//! Gestion du processus moteur Python (« sidecar »).
//!
//! Le moteur est lancé à la première requête et redémarré s'il s'est arrêté.
//! Les messages JSON-RPC sont échangés ligne par ligne sur stdin/stdout : aucun
//! port réseau n'est ouvert. Les identifiants de requête sont réécrits ici pour
//! qu'un rechargement de l'interface ne puisse pas mélanger deux réponses.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::Value;
use tokio::sync::oneshot;

const CALL_TIMEOUT: Duration = Duration::from_secs(300);

type Pending = Arc<Mutex<HashMap<u64, oneshot::Sender<Value>>>>;

struct Process {
    child: Child,
    stdin: ChildStdin,
}

pub struct Engine {
    process: Mutex<Option<Process>>,
    pending: Pending,
    next_id: AtomicU64,
}

impl Engine {
    pub fn new() -> Self {
        Self {
            process: Mutex::new(None),
            pending: Arc::new(Mutex::new(HashMap::new())),
            next_id: AtomicU64::new(1),
        }
    }

    pub async fn call(&self, payload: String) -> Result<String, String> {
        let mut request: Value =
            serde_json::from_str(&payload).map_err(|_| "Requête invalide.".to_string())?;
        let original_id = request.get("id").cloned().unwrap_or(Value::Null);
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        request["id"] = Value::from(id);
        let line = serde_json::to_string(&request).map_err(|e| e.to_string())?;

        let (tx, rx) = oneshot::channel();
        self.pending.lock().unwrap().insert(id, tx);

        if let Err(err) = self.send_line(&line) {
            self.pending.lock().unwrap().remove(&id);
            return Err(err);
        }

        let mut response = match tokio::time::timeout(CALL_TIMEOUT, rx).await {
            Ok(Ok(value)) => value,
            Ok(Err(_)) => {
                return Err("Le moteur de calcul s'est arrêté de manière inattendue. \
                            Le fichier projet enregistré n'a pas été modifié."
                    .into())
            }
            Err(_) => {
                self.pending.lock().unwrap().remove(&id);
                return Err("Le moteur de calcul ne répond pas.".into());
            }
        };
        response["id"] = original_id;
        serde_json::to_string(&response).map_err(|e| e.to_string())
    }

    fn send_line(&self, line: &str) -> Result<(), String> {
        let mut guard = self.process.lock().unwrap();
        let alive = match guard.as_mut() {
            Some(p) => matches!(p.child.try_wait(), Ok(None)),
            None => false,
        };
        if !alive {
            *guard = Some(self.spawn()?);
        }
        let process = guard.as_mut().unwrap();
        writeln!(process.stdin, "{line}")
            .and_then(|_| process.stdin.flush())
            .map_err(|e| format!("Impossible de joindre le moteur de calcul : {e}"))
    }

    fn spawn(&self) -> Result<Process, String> {
        let mut command = engine_command()?;
        command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::inherit());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }
        let mut child = command
            .spawn()
            .map_err(|e| format!("Impossible de démarrer le moteur de calcul : {e}"))?;
        let stdin = child.stdin.take().ok_or("stdin du moteur indisponible")?;
        let stdout = child.stdout.take().ok_or("stdout du moteur indisponible")?;

        let pending = self.pending.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines() {
                let Ok(line) = line else { break };
                let Ok(value) = serde_json::from_str::<Value>(&line) else {
                    log::warn!("réponse illisible du moteur ignorée");
                    continue;
                };
                if let Some(id) = value.get("id").and_then(Value::as_u64) {
                    if let Some(tx) = pending.lock().unwrap().remove(&id) {
                        let _ = tx.send(value);
                    }
                }
            }
            // Le moteur s'est arrêté : les requêtes en attente échouent proprement.
            pending.lock().unwrap().clear();
        });
        Ok(Process { child, stdin })
    }

    /// Arrêt à la fermeture de l'application : fermer stdin laisse le moteur
    /// libérer son dossier de travail, puis on s'assure qu'il est terminé.
    pub fn shutdown(&self) {
        if let Some(Process { mut child, stdin }) = self.process.lock().unwrap().take() {
            drop(stdin);
            for _ in 0..30 {
                if matches!(child.try_wait(), Ok(Some(_))) {
                    return;
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// En développement : `python -m statpfe` depuis le dossier `engine/` du dépôt.
/// En version distribuée : l'exécutable `statpfe-engine` installé à côté de l'application.
fn engine_command() -> Result<Command, String> {
    if cfg!(debug_assertions) {
        let engine_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../engine");
        let python = std::env::var("STATPFE_PYTHON")
            .unwrap_or_else(|_| if cfg!(windows) { "python".into() } else { "python3".into() });
        let mut cmd = Command::new(python);
        cmd.args(["-m", "statpfe"]).current_dir(engine_dir);
        return Ok(cmd);
    }
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let dir = exe.parent().ok_or("dossier de l'application introuvable")?;
    let name = if cfg!(windows) { "statpfe-engine.exe" } else { "statpfe-engine" };
    Ok(Command::new(dir.join(name)))
}
