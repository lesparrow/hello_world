"""Réglages de l'IA locale, stockés dans le dossier de configuration de l'utilisateur.

Les réglages ne concernent que l'application (pas un projet) et ne contiennent aucune
donnée d'étude. L'IA est désactivée tant que l'utilisateur ne l'a pas activée.
"""

from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from statpfe.core import recent
from statpfe.errors import ValidationError

PROVIDERS = {
    "ollama": {"label": "Ollama", "default_url": "http://127.0.0.1:11434"},
    "openai": {"label": "Serveur compatible OpenAI (llama.cpp, LM Studio…)", "default_url": "http://127.0.0.1:8080"},
}
LOOPBACK_NAMES = {"localhost"}
MAX_TOKENS_RANGE = (64, 2048)
TIMEOUT_RANGE = (10, 900)


@dataclass
class AiSettings:
    enabled: bool = False
    provider: str = "ollama"
    base_url: str = PROVIDERS["ollama"]["default_url"]
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 700
    timeout: int = 300

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _file() -> Path:
    return recent.config_dir() / "ai-settings.json"


def load() -> AiSettings:
    try:
        raw = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AiSettings()
    try:
        return clean(raw, AiSettings())
    except ValidationError:
        return AiSettings()  # fichier altéré : on repart des réglages sûrs (IA désactivée)


def save(changes: Any) -> AiSettings:
    settings = clean(changes, load())
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return settings


def clean(changes: Any, base: AiSettings) -> AiSettings:
    if not isinstance(changes, dict):
        raise ValidationError("Réglages de l'IA invalides.")
    s = AiSettings(**base.to_dict())
    if "enabled" in changes:
        s.enabled = bool(changes["enabled"])
    if "provider" in changes:
        if changes["provider"] not in PROVIDERS:
            raise ValidationError("Type de serveur de modèles inconnu.")
        if changes["provider"] != s.provider and "base_url" not in changes:
            s.base_url = PROVIDERS[changes["provider"]]["default_url"]
        s.provider = changes["provider"]
    if "base_url" in changes:
        s.base_url = loopback_url(changes["base_url"])
    if "model" in changes:
        model = str(changes["model"] or "").strip()
        if len(model) > 200 or any(c in model for c in "\r\n\t"):
            raise ValidationError("Nom de modèle invalide.")
        s.model = model
    if "temperature" in changes:
        s.temperature = _number(changes["temperature"], 0.0, 1.0, "La température")
    if "max_tokens" in changes:
        s.max_tokens = int(_number(changes["max_tokens"], *MAX_TOKENS_RANGE, "La longueur maximale"))
    if "timeout" in changes:
        s.timeout = int(_number(changes["timeout"], *TIMEOUT_RANGE, "Le délai maximal"))
    return s


def _number(value: Any, low: float, high: float, name: str) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} doit être un nombre.") from None
    if not low <= x <= high:
        raise ValidationError(f"{name} doit être comprise entre {low:g} et {high:g}.")
    return x


def loopback_url(value: Any) -> str:
    """N'accepte qu'une adresse http de la boucle locale : rien ne doit quitter l'ordinateur."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Adresse du serveur de modèles manquante.")
    text = value.strip().rstrip("/")
    parts = urlsplit(text)
    if parts.scheme != "http":
        raise ValidationError("L'adresse doit commencer par http:// (serveur installé sur cet ordinateur).")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValidationError("L'adresse du serveur de modèles ne doit contenir ni identifiants ni paramètres.")
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        raise ValidationError("Port invalide dans l'adresse du serveur de modèles.") from None
    if host not in LOOPBACK_NAMES:
        try:
            ok = ipaddress.ip_address(host).is_loopback
        except ValueError:
            ok = False
        if not ok:
            raise ValidationError(
                "Seul un serveur installé sur cet ordinateur est accepté (127.0.0.1, localhost ou ::1) : "
                "STATPFE n'envoie jamais vos résultats à un service extérieur.")
    if parts.path not in ("", "/"):
        raise ValidationError("Indiquez seulement l'adresse et le port du serveur, sans chemin.")
    shown = f"[{host}]" if ":" in host else host
    return f"http://{shown}" + (f":{port}" if port else "")


def connect_host(base_url: str) -> str:
    """Adresse effectivement contactée : « localhost » est remplacé par 127.0.0.1 (pas de résolution DNS)."""
    parts = urlsplit(loopback_url(base_url))
    host = parts.hostname or "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"
    shown = f"[{host}]" if ":" in host else host
    return f"http://{shown}" + (f":{parts.port}" if parts.port else "")
