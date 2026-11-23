"""Point d'entrée de l'exécutable autonome du moteur (PyInstaller)."""

from statpfe.rpc.server import main

if __name__ == "__main__":
    raise SystemExit(main())
