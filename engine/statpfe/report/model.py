"""Document intermédiaire, indépendant du format : le même contenu sert au rendu Word et PDF."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class Para:
    runs: list[Run]
    style: str = "body"  # body | note | placeholder | lead | warning | ai

    @classmethod
    def of(cls, text: str, style: str = "body") -> "Para":
        return cls([Run(text, italic=style in ("placeholder", "note"))], style)


@dataclass
class Heading:
    level: int
    text: str
    number: str = ""

    @property
    def full(self) -> str:
        return f"{self.number} {self.text}".strip() if self.number else self.text


@dataclass
class Bullets:
    items: list[list[Run]]


@dataclass
class Table:
    number: int | None
    caption: str
    columns: list[str]
    rows: list[list[str]]
    note: str = ""
    source: str = ""
    numeric: list[bool] = field(default_factory=list)
    key_value: bool = False

    @property
    def label(self) -> str:
        return f"Tableau {self.number}. {self.caption}" if self.number else self.caption


@dataclass
class Figure:
    number: int
    caption: str
    png: bytes
    description: str
    source: str
    width_cm: float = 15.0

    @property
    def label(self) -> str:
        return f"Figure {self.number}. {self.caption}"


@dataclass
class PageBreak:
    pass


@dataclass
class Toc:
    pass


@dataclass
class Cover:
    document: str
    title: str
    fields: list[tuple[str, str]]
    date: str
    disclaimer: str


Block = Para | Heading | Bullets | Table | Figure | PageBreak | Toc | Cover


@dataclass
class Document:
    title: str
    footer: str
    blocks: list[Block] = field(default_factory=list)

    def outline(self) -> list[dict]:
        out = []
        for b in self.blocks:
            if isinstance(b, Heading):
                out.append({"kind": "heading", "level": b.level, "text": b.full})
            elif isinstance(b, Table) and b.number:
                out.append({"kind": "table", "text": b.label})
            elif isinstance(b, Figure):
                out.append({"kind": "figure", "text": b.label})
        return out

    def text(self) -> str:
        """Texte brut du document (tests et contrôles)."""
        parts: list[str] = []
        for b in self.blocks:
            if isinstance(b, Para):
                parts.append("".join(r.text for r in b.runs))
            elif isinstance(b, Heading):
                parts.append(b.full)
            elif isinstance(b, Bullets):
                parts += ["".join(r.text for r in it) for it in b.items]
            elif isinstance(b, Table):
                parts.append(b.label)
                parts.append(" | ".join(b.columns))
                parts += [" | ".join(r) for r in b.rows]
                parts += [b.note, b.source]
            elif isinstance(b, Figure):
                parts += [b.label, b.description, b.source]
            elif isinstance(b, Cover):
                parts += [b.document, b.title] + [f"{k} : {v}" for k, v in b.fields] + [b.date, b.disclaimer]
        return "\n".join(p for p in parts if p)
