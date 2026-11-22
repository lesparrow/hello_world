"""Ressources de l'ordinateur et conseil de taille de modèle.

Les seuils sont indicatifs : un modèle quantifié sur 4 bits occupe environ
0,6 à 0,7 Go de mémoire par milliard de paramètres, plus le contexte.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from typing import Any

from statpfe.core import recent

GB = 1024 ** 3

# (mémoire totale minimale en Go, conseil). Noms de modèles Ollama, vérifiés en novembre 2026.
RECOMMENDATIONS = [
    (16, {"size": "7 à 8 milliards de paramètres", "examples": ["qwen2.5:7b", "mistral:7b", "llama3.1:8b"],
          "note": "Bonne qualité de rédaction en français ; quelques secondes à une minute par paragraphe sans carte graphique."}),
    (8, {"size": "3 à 4 milliards de paramètres", "examples": ["qwen2.5:3b", "llama3.2:3b", "phi3.5"],
         "note": "Compromis raisonnable ; relisez attentivement le français et les nuances."}),
    (4, {"size": "1 à 2 milliards de paramètres", "examples": ["qwen2.5:1.5b", "llama3.2:1b"],
         "note": "Utilisable pour expliquer une méthode ; rédaction souvent approximative."}),
]


def memory() -> tuple[int | None, int | None]:
    """(mémoire totale, mémoire disponible) en octets, ou None si inconnue."""
    try:
        if sys.platform == "win32":
            class MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MemStatus()
            st.dwLength = ctypes.sizeof(MemStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):  # type: ignore[attr-defined]
                return int(st.ullTotalPhys), int(st.ullAvailPhys)
            return None, None
        if sys.platform == "darwin":
            total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                                       timeout=3).stdout.strip())
            return total, None
        info: dict[str, int] = {}
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0]) * 1024
        return info.get("MemTotal"), info.get("MemAvailable")
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
        return None, None


def resources() -> dict[str, Any]:
    total, available = memory()
    try:
        disk = shutil.disk_usage(recent.config_dir().anchor or "/").free
    except OSError:
        disk = None
    cores = os.cpu_count()
    rec = None
    if total is not None:
        for threshold, r in RECOMMENDATIONS:
            if total >= threshold * GB * 0.95:  # 16 Go annoncés font souvent 15,6 Go visibles
                rec = dict(r)
                break
    warnings = []
    if total is not None and rec is None:
        warnings.append("Moins de 4 Go de mémoire : un modèle local risque d'être très lent ou de ne pas démarrer. "
                        "STATPFE reste entièrement utilisable sans IA.")
    if available is not None and available < 2 * GB:
        warnings.append("Moins de 2 Go de mémoire libre en ce moment : fermez d'autres applications avant d'utiliser l'IA.")
    if disk is not None and disk < 5 * GB:
        warnings.append("Moins de 5 Go d'espace disque libre : l'installation d'un modèle peut échouer.")
    return {"memory_total": total, "memory_available": available, "disk_free": disk, "cpu_cores": cores,
            "recommendation": rec, "warnings": warnings}
