"""Client HTTP minimal vers un serveur de modèles local (Ollama ou compatible OpenAI).

- Seule la boucle locale est contactée (adresse vérifiée par `settings.loopback_url`).
- Les mandataires (proxy) du système sont ignorés : la requête ne peut pas être
  détournée vers l'extérieur par une variable d'environnement.
- Les redirections sont refusées.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator

from statpfe.ai.settings import AiSettings, connect_host

PROBE_TIMEOUT = 3
MAX_LINE = 1024 * 1024
MAX_TEXT = 40_000


class AiUnavailable(Exception):
    """Le serveur de modèles ne répond pas ou a renvoyé une erreur."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _request(settings: AiSettings, path: str, body: dict[str, Any] | None, timeout: float):
    url = connect_host(settings.base_url) + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        return _OPENER.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read(4096).decode("utf-8", "replace")).get("error", "")
            if isinstance(detail, dict):
                detail = detail.get("message", "")
        except (ValueError, AttributeError):
            pass
        raise AiUnavailable(f"Le serveur de modèles a répondu par une erreur ({exc.code})"
                            + (f" : {str(detail)[:300]}" if detail else ".")) from None
    except (urllib.error.URLError, OSError) as exc:
        raise AiUnavailable("Aucun serveur de modèles ne répond à cette adresse.") from exc


def _get_json(settings: AiSettings, path: str) -> Any:
    with _request(settings, path, None, PROBE_TIMEOUT) as resp:
        raw = resp.read(MAX_LINE)
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        raise AiUnavailable("Le serveur a répondu, mais pas comme un serveur de modèles.") from None


def list_models(settings: AiSettings) -> list[dict[str, Any]]:
    """Modèles installés sur le serveur local. Lève AiUnavailable si le serveur ne répond pas."""
    if settings.provider == "claude_code":
        from statpfe.ai import claude_code
        from statpfe.ai.settings import CLAUDE_MODELS

        try:
            ver = claude_code.version(settings)
        except claude_code.ClaudeCodeError as exc:
            raise AiUnavailable(str(exc)) from None
        return [{"name": m["name"], "size": None, "parameters": m["label"], "quantization": None, "version": ver,
                 "description": m["description"], "recommended": m["recommended"]} for m in CLAUDE_MODELS]
    if settings.provider == "ollama":
        data = _get_json(settings, "/api/tags")
        out = []
        for m in (data.get("models") or []) if isinstance(data, dict) else []:
            if isinstance(m, dict) and isinstance(m.get("name"), str):
                det = m.get("details") or {}
                out.append({"name": m["name"], "size": m.get("size"),
                            "parameters": det.get("parameter_size") if isinstance(det, dict) else None,
                            "quantization": det.get("quantization_level") if isinstance(det, dict) else None})
        return out
    data = _get_json(settings, "/v1/models")
    items = data.get("data") if isinstance(data, dict) else None
    return [{"name": m["id"], "size": None, "parameters": None, "quantization": None}
            for m in items or [] if isinstance(m, dict) and isinstance(m.get("id"), str)]


def stream_chat(settings: AiSettings, messages: list[dict[str, str]], cancel: threading.Event,
                on_text: Callable[[str], None], json_mode: bool = False) -> dict[str, Any]:
    """Envoie la conversation et transmet le texte au fur et à mesure. Renvoie les métadonnées finales."""
    if settings.provider == "claude_code":
        from statpfe.ai import claude_code

        try:
            return claude_code.stream_chat(settings, messages, cancel, on_text)
        except claude_code.ClaudeCodeError as exc:
            raise AiUnavailable(str(exc)) from None
    if settings.provider == "ollama":
        body = {"model": settings.model, "messages": messages, "stream": True, "think": False,
                "options": {"temperature": settings.temperature, "num_predict": settings.max_tokens,
                            "num_ctx": 8192, "seed": 7}}
        if json_mode:
            body["format"] = "json"  # Ollama contraint la sortie à un JSON valide
        path = "/api/chat"
    else:
        body = {"model": settings.model, "messages": messages, "stream": True,
                "temperature": settings.temperature, "max_tokens": settings.max_tokens, "seed": 7}
        path = "/v1/chat/completions"
    meta: dict[str, Any] = {"finish": None, "model": settings.model}
    total = 0
    with _request(settings, path, body, settings.timeout) as resp:
        for chunk in _lines(resp, cancel):
            if settings.provider == "ollama":
                piece, done = _ollama_piece(chunk, meta)
            else:
                piece, done = _openai_piece(chunk, meta)
            if piece:
                total += len(piece)
                if total > MAX_TEXT:
                    meta["finish"] = "trop_long"
                    break
                on_text(piece)
            if done:
                break
    if cancel.is_set():
        meta["finish"] = "annule"
    return meta


def _lines(resp, cancel: threading.Event) -> Iterator[str]:
    while not cancel.is_set():
        line = resp.readline(MAX_LINE)
        if not line:
            return
        text = line.decode("utf-8", "replace").strip()
        if text:
            yield text


def _ollama_piece(line: str, meta: dict[str, Any]) -> tuple[str, bool]:
    try:
        data = json.loads(line)
    except ValueError:
        return "", False
    if data.get("error"):
        raise AiUnavailable(f"Erreur du modèle : {str(data['error'])[:300]}")
    piece = (data.get("message") or {}).get("content") or ""
    if data.get("done"):
        meta["finish"] = data.get("done_reason") or "stop"
        meta["eval_count"] = data.get("eval_count")
        meta["prompt_eval_count"] = data.get("prompt_eval_count")
        if isinstance(data.get("model"), str):
            meta["model"] = data["model"]
        return piece, True
    return piece, False


def _openai_piece(line: str, meta: dict[str, Any]) -> tuple[str, bool]:
    if not line.startswith("data:"):
        return "", False
    payload = line[5:].strip()
    if payload == "[DONE]":
        meta["finish"] = meta.get("finish") or "stop"
        return "", True
    try:
        data = json.loads(payload)
    except ValueError:
        return "", False
    if data.get("error"):
        err = data["error"]
        raise AiUnavailable(f"Erreur du modèle : {str(err.get('message') if isinstance(err, dict) else err)[:300]}")
    if isinstance(data.get("model"), str) and data["model"]:
        meta["model"] = data["model"]
    piece = ""
    for choice in data.get("choices") or []:
        piece += (choice.get("delta") or {}).get("content") or ""
        if choice.get("finish_reason"):
            meta["finish"] = choice["finish_reason"]
    return piece, False
