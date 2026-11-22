"""Construit l'exécutable autonome du moteur et le place là où Tauri l'attend.

Usage : python packaging/build_sidecar.py   (depuis le dossier engine/)

Tauri exige que le binaire embarqué porte le triplet de la plateforme cible,
par exemple `statpfe-engine-x86_64-pc-windows-msvc.exe`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1]
DEST_DIR = ENGINE_DIR.parent / "apps" / "desktop" / "src-tauri" / "binaries"


def target_triple() -> str:
    out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Impossible de déterminer le triplet de la plateforme (rustc -vV).")


def main() -> int:
    build = ENGINE_DIR / "build" / "pyinstaller"
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile", "--noconfirm", "--clean",
            "--name", "statpfe-engine",
            "--distpath", str(build / "dist"),
            "--workpath", str(build / "work"),
            "--specpath", str(build),
            "--paths", str(ENGINE_DIR),
            str(ENGINE_DIR / "packaging" / "entry.py"),
        ],
        check=True,
        cwd=ENGINE_DIR,
    )
    ext = ".exe" if sys.platform == "win32" else ""
    built = build / "dist" / f"statpfe-engine{ext}"
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest = DEST_DIR / f"statpfe-engine-{target_triple()}{ext}"
    shutil.copy2(built, dest)
    print(f"Moteur copié vers {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
