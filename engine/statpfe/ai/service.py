"""Fonctions de l'IA locale exposées au protocole (voir rpc/server.py)."""

from __future__ import annotations

from typing import Any

from statpfe.ai import client, context, guard, prompts, settings, setup, system
from statpfe.ai.jobs import JobManager
from statpfe.errors import ValidationError

STATES = {
    "desactivee": "L'IA locale est désactivée. STATPFE fonctionne entièrement sans elle.",
    "serveur_absent": "Aucun serveur de modèles ne répond à l'adresse indiquée.",
    "aucun_modele": "Le serveur répond, mais aucun modèle n'y est installé.",
    "modele_absent": "Le modèle choisi n'est pas installé sur le serveur.",
    "modele_a_choisir": "Choisissez un des modèles installés.",
    "prete": "L'IA est prête.",
    "consentement_requis": "Claude Code envoie les résultats calculés au service en ligne d'Anthropic : votre "
                           "autorisation explicite est nécessaire.",
    "claude_absent": "Claude Code n'est pas installé sur cet ordinateur (ou ne démarre pas).",
    "claude_non_connecte": "Claude Code est installé, mais pas encore connecté à votre compte Claude.",
}


class AiService:
    def __init__(self) -> None:
        self.jobs = JobManager()
        self.setup = setup.SetupManager()

    # ------------------------------------------------------------------ état
    def status(self, probe: bool = True) -> dict[str, Any]:
        s = settings.load()
        res = system.resources()
        out: dict[str, Any] = {"settings": s.to_dict(), "providers": [{"key": k, **v} for k, v in
                                                                        settings.PROVIDERS.items()],
                               "resources": res, "server": None, "models": [],
                               "claude_models": settings.CLAUDE_MODELS, "claude_install": setup.claude_install_info(),
                               "local_catalog": system.local_catalog(res["memory_total"]),
                               "ollama_download": setup.OLLAMA_DOWNLOAD, "ollama_installed": None,
                               "claude_executable": None, "claude_auth": None}
        if not s.enabled:
            return {**out, "state": "desactivee", "message": STATES["desactivee"], "ready": False}
        cloud = s.provider == "claude_code"
        if cloud:
            # Ordre des étapes : installer, se connecter, autoriser l'envoi. Les deux premières
            # n'envoient aucune donnée d'étude.
            from statpfe.ai import claude_code

            out["claude_executable"] = claude_code.executable(s)
            if out["claude_executable"] is None:
                return {**out, "state": "claude_absent", "message": STATES["claude_absent"], "ready": False}
            if probe:
                out["claude_auth"] = claude_code.auth_status(s)
                if out["claude_auth"]["logged_in"] is False:
                    return {**out, "state": "claude_non_connecte", "message": STATES["claude_non_connecte"],
                            "ready": False}
        if cloud and not s.cloud_consent_at:
            return {**out, "state": "consentement_requis", "message": STATES["consentement_requis"], "ready": False}
        if not probe:
            return {**out, "state": "inconnu", "message": "", "ready": False}
        try:
            models = client.list_models(s)
            out["server"] = {"reachable": True, "error": None}
        except client.AiUnavailable as exc:
            out["server"] = {"reachable": False, "error": str(exc)}
            if s.provider == "ollama":
                out["ollama_installed"] = setup.ollama_executable() is not None
            state = "claude_absent" if cloud else "serveur_absent"
            return {**out, "state": state, "message": STATES[state], "ready": False}
        out["models"] = models
        if s.provider == "ollama":
            out["ollama_installed"] = True
            out["local_catalog"] = system.local_catalog(res["memory_total"], {m["name"] for m in models})
        names = {m["name"] for m in models}
        if not models:
            state = "aucun_modele"
        elif not s.model:
            state = "modele_a_choisir"
        elif s.model not in names and f"{s.model}:latest" not in names:
            state = "modele_absent"
        else:
            state = "prete"
        return {**out, "state": state, "message": STATES[state], "ready": state == "prete"}

    def update_settings(self, changes: Any) -> dict[str, Any]:
        settings.save(changes)
        if not settings.load().enabled:
            self.jobs.cancel_all()
        return self.status()

    # ------------------------------------------------------------------ génération
    def preview(self, project, analysis_id: Any) -> dict[str, Any]:
        a = project.analyses.get(analysis_id)
        return context.build(project, a)

    def generate(self, project, analysis_id: Any, task: Any, user_text: Any = None) -> dict[str, Any]:
        s = settings.load()
        if not s.enabled:
            raise ValidationError(STATES["desactivee"])
        if not s.model:
            raise ValidationError("Choisissez d'abord un modèle dans les réglages de l'IA.")
        if s.provider == "claude_code" and not s.cloud_consent_at:
            raise ValidationError(STATES["consentement_requis"])
        if task not in prompts.TASKS:
            raise ValidationError("Demande inconnue pour l'IA.")
        a = project.analyses.get(analysis_id)
        ctx = context.build(project, a)
        msgs = prompts.messages(task, ctx["text"], user_text)
        job = self.jobs.start(s, msgs, {"analysis_id": a["id"], "analysis_title": a["title"], "task": task,
                                        "task_label": prompts.TASKS[task]["label"], "project_id": project.project_id})
        job.context = ctx  # type: ignore[attr-defined]
        return self._snapshot(project, job)

    def job(self, project, job_id: Any) -> dict[str, Any]:
        return self._snapshot(project, self.jobs.get(job_id))

    def cancel(self, project, job_id: Any) -> dict[str, Any]:
        return self._snapshot(project, self.jobs.cancel(job_id))

    def _snapshot(self, project, job) -> dict[str, Any]:
        snap = job.snapshot()
        snap["text"] = guard.strip_thinking(snap["text"]) if snap["status"] != "en_cours" else _visible(snap["text"])
        snap["ai_text"] = None
        if snap["status"] == "termine":
            if not snap["text"]:
                snap["status"], snap["error"] = "erreur", ("Le modèle n'a renvoyé aucun texte. Essayez un autre "
                                                           "modèle ou augmentez la longueur maximale.")
            elif not job.stored and project is not None and project.project_id == snap["meta"]["project_id"]:
                label = f"l'analyse « {snap['meta']['analysis_title']} »"
                job.ai_text_id = project.ai_texts.record(  # type: ignore[attr-defined]
                    analysis_id=snap["meta"]["analysis_id"], analysis_label=label, task=snap["meta"]["task"],
                    settings=job.settings.to_dict(), model=snap["finish"].get("model") or job.settings.model,
                    messages=job.messages, context=job.context, raw_text=job.text,  # type: ignore[attr-defined]
                    duration=snap["elapsed"])
                project._touch()
                job.stored = True
            if job.stored and project is not None and project.project_id == snap["meta"]["project_id"]:
                snap["ai_text"] = project.ai_texts.get(job.ai_text_id)  # type: ignore[attr-defined]
        return snap


def _visible(text: str) -> str:
    """Pendant la rédaction, masque un éventuel raisonnement <think> non terminé."""
    return guard.strip_thinking(text)
