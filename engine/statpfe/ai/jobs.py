"""Générations en arrière-plan.

Le moteur ne traite qu'une requête à la fois ; une génération sur processeur peut durer
une minute. Elle tourne donc dans un fil séparé qui ne fait que dialoguer avec le serveur
de modèles local (aucun accès au projet ni à SQLite). L'interface interroge l'état par
`ai.job` et peut annuler. Une seule génération à la fois.
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from statpfe.ai import client
from statpfe.ai.settings import AiSettings
from statpfe.errors import ValidationError

KEEP_FINISHED = 5


@dataclass
class Job:
    id: int
    settings: AiSettings
    messages: list[dict[str, str]]
    meta: dict[str, Any]
    started: float = field(default_factory=time.monotonic)
    text: str = ""
    status: str = "en_cours"  # en_cours | termine | erreur | annule
    error: str | None = None
    finish: dict[str, Any] = field(default_factory=dict)
    ended: float | None = None
    stored: bool = False
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            end = self.ended or time.monotonic()
            return {"id": self.id, "status": self.status, "text": self.text, "error": self.error,
                    "elapsed": round(end - self.started, 1), "finish": dict(self.finish), "meta": dict(self.meta)}


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[int, Job] = {}
        self._ids = itertools.count(1)

    def running(self) -> Job | None:
        return next((j for j in self._jobs.values() if j.status == "en_cours"), None)

    def start(self, settings: AiSettings, messages: list[dict[str, str]], meta: dict[str, Any]) -> Job:
        if self.running() is not None:
            raise ValidationError("Une proposition est déjà en cours de rédaction : attendez-la ou annulez-la.")
        job = Job(next(self._ids), settings, messages, meta)
        self._jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), name=f"statpfe-ia-{job.id}", daemon=True).start()
        self._prune()
        return job

    def get(self, job_id: Any) -> Job:
        job = self._jobs.get(job_id) if isinstance(job_id, int) else None
        if job is None:
            raise ValidationError("Cette proposition n'existe plus.")
        return job

    def cancel(self, job_id: Any) -> Job:
        job = self.get(job_id)
        with job.lock:
            if job.status == "en_cours":
                job.cancel.set()
                job.status = "annule"
                job.ended = time.monotonic()
        return job

    def cancel_all(self) -> None:
        for job in list(self._jobs.values()):
            if job.status == "en_cours":
                self.cancel(job.id)

    def _prune(self) -> None:
        done = [j for j in self._jobs.values() if j.status != "en_cours"]
        for j in done[:-KEEP_FINISHED]:
            self._jobs.pop(j.id, None)

    @staticmethod
    def _run(job: Job) -> None:
        def on_text(piece: str) -> None:
            with job.lock:
                if job.status == "en_cours":
                    job.text += piece

        try:
            finish = client.stream_chat(job.settings, job.messages, job.cancel, on_text,
                                        json_mode=bool(job.meta.get("json")))
            with job.lock:
                job.finish = finish
                if job.status == "en_cours":
                    job.status = "termine"
        except client.AiUnavailable as exc:
            with job.lock:
                if job.status == "en_cours":
                    job.status, job.error = "erreur", str(exc)
        except Exception:  # noqa: BLE001 - le fil ne doit jamais faire tomber le moteur
            with job.lock:
                if job.status == "en_cours":
                    job.status, job.error = "erreur", "Erreur inattendue pendant la rédaction de la proposition."
        finally:
            with job.lock:
                if job.ended is None:
                    job.ended = time.monotonic()
