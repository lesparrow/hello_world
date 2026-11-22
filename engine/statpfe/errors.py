"""Erreurs métier, avec un message compréhensible par l'utilisateur."""


class StatpfeError(Exception):
    """Erreur prévue, affichable telle quelle à l'utilisateur."""

    code = "erreur"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class ValidationError(StatpfeError):
    code = "validation"


class ProjectFileError(StatpfeError):
    code = "fichier_projet"


class NoProjectOpenError(StatpfeError):
    code = "aucun_projet"

    def __init__(self) -> None:
        super().__init__("Aucun projet n'est ouvert.")


class ProjectAlreadyOpenError(StatpfeError):
    code = "projet_deja_ouvert"

    def __init__(self) -> None:
        super().__init__(
            "Un projet est déjà ouvert. Fermez-le avant d'en ouvrir ou d'en créer un autre."
        )


class UnsavedChangesError(StatpfeError):
    code = "modifications_non_enregistrees"

    def __init__(self) -> None:
        super().__init__("Le projet contient des modifications non enregistrées.")
