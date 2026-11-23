"""Rendu LaTeX : archive .zip (rapport.tex + figures/) prête à compiler.

L'archive s'importe telle quelle dans Overleaf (« New Project > Upload Project »)
ou se compile avec pdflatex. Les caractères spéciaux (−, ≥, χ², α…) sont
convertis en commandes LaTeX standard, pour compiler sans police particulière.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from statpfe.report import theme as themes
from statpfe.report.model import Bullets, Cover, Document, Figure, Heading, PageBreak, Para, Run, Table, Toc

MAIN = "rapport.tex"

_SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
            "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
_UNICODE = {
    "−": r"\ensuremath{-}", "≥": r"\ensuremath{\geq}", "≤": r"\ensuremath{\leq}", "≠": r"\ensuremath{\neq}",
    "≈": r"\ensuremath{\approx}", "±": r"\ensuremath{\pm}", "×": r"\ensuremath{\times}", "÷": r"\ensuremath{\div}",
    "∞": r"\ensuremath{\infty}", "√": r"\ensuremath{\surd}", "→": r"\ensuremath{\rightarrow}",
    "α": r"\ensuremath{\alpha}", "β": r"\ensuremath{\beta}", "χ": r"\ensuremath{\chi}", "η": r"\ensuremath{\eta}",
    "μ": r"\ensuremath{\mu}", "ρ": r"\ensuremath{\rho}", "σ": r"\ensuremath{\sigma}", "τ": r"\ensuremath{\tau}",
    "Δ": r"\ensuremath{\Delta}", "ε": r"\ensuremath{\varepsilon}", "φ": r"\ensuremath{\varphi}",
    "²": r"\textsuperscript{2}", "³": r"\textsuperscript{3}", "¹": r"\textsuperscript{1}",
    "\u00a0": "~", "\u202f": r"\,", "\u2009": r"\,", "…": r"\dots{}", "–": "--", "—": "---",
    "’": "'", "‘": "`", "“": "``", "”": "''", "•": r"\textbullet{}", "·": r"\textperiodcentered{}",
    "✓": r"\ensuremath{\checkmark}", "°": r"\textdegree{}", "€": r"\texteuro{}", "‰": r"\textperthousand{}",
    "π": r"\ensuremath{\pi}", "Γ": r"\ensuremath{\Gamma}", "Σ": r"\ensuremath{\Sigma}", "λ": r"\ensuremath{\lambda}",
    "ω": r"\ensuremath{\omega}", "θ": r"\ensuremath{\theta}", "ν": r"\ensuremath{\nu}", "κ": r"\ensuremath{\kappa}",
    "ᵢ": r"\ensuremath{_{i}}", "™": r"\texttrademark{}", "\u0302": "", "\ufeff": "",
    **{chr(0x2080 + k): rf"\ensuremath{{_{{{k}}}}}" for k in range(10)},
}
# Lettres latines accentuées et symboles couverts par T1/textcomp : laissés tels quels (inputenc utf8).
_LATIN = re.compile(r"[\x00-\x7f¡-ÿŒœŸ]")


def tex(text: str) -> str:
    out = []
    for ch in text:
        if ch in _SPECIAL:
            out.append(_SPECIAL[ch])
        elif ch in _UNICODE:
            out.append(_UNICODE[ch])
        elif ch in "«":
            out.append(r"\og{}")
        elif ch in "»":
            out.append(r"\fg{}")
        elif ch == "\n":
            out.append(r"\\ ")
        elif _LATIN.match(ch):
            out.append(ch)
        else:
            out.append("?")  # caractère sans équivalent sûr sous pdflatex (écriture arabe, émoji…)
    return "".join(out)


def _runs(runs: list[Run]) -> str:
    parts = []
    for r in runs:
        t = tex(r.text)
        if r.bold:
            t = rf"\textbf{{{t}}}"
        if r.italic:
            t = rf"\textit{{{t}}}"
        parts.append(t)
    return "".join(parts)


def _color(name: str, hex_color: str) -> str:
    return rf"\definecolor{{{name}}}{{HTML}}{{{hex_color.lstrip('#').upper()}}}"


def _preamble(document: Document, author: str, th: themes.Theme) -> list[str]:
    return [
        r"% Rapport produit par STATPFE. Compiler avec pdflatex (ou importer l'archive dans Overleaf).",
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\IfFileExists{lmodern.sty}{\usepackage{lmodern}}{}",
        r"\usepackage{textcomp}",
        r"\usepackage[french]{babel}",
        r"\usepackage[a4paper,margin=2.5cm]{geometry}",
        r"\usepackage{amsmath,amssymb}",
        r"\usepackage{graphicx}",
        r"\usepackage{array,booktabs,longtable}",
        r"\usepackage[table]{xcolor}",
        r"\usepackage{caption}",
        r"\usepackage{float}",
        r"\usepackage{fancyhdr}",
        r"\usepackage{titlesec}",
        r"\usepackage[hidelinks]{hyperref}",
        _color("accent", th.primary if th.color else "#000000"),
        _color("enteteFond", th.header_fill),
        _color("enteteTexte", th.header_text),
        _color("ligneClaire", th.light if th.color else "#FFFFFF"),
        _color("noteIA", "#E8F0FE"),
        _color("aCompleter", "#FFF3B0"),
        _color("gris", "#555555"),
        r"\titleformat{\section}{\Large\bfseries\color{accent}}{}{0pt}{}",
        r"\titleformat{\subsection}{\large\bfseries\color{accent}}{}{0pt}{}",
        r"\captionsetup{labelfont={bf,color=accent},textfont=bf,labelsep=period,justification=centering}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{6pt}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        r"\renewcommand{\headrulewidth}{0pt}",
        rf"\fancyfoot[L]{{\scriptsize\color{{gris}} {tex(document.footer)}}}",
        r"\fancyfoot[R]{\scriptsize\color{gris}\thepage}",
        r"\newcommand{\encadre}[2]{\par\noindent\colorbox{#1}{\parbox{\dimexpr\linewidth-2\fboxsep\relax}{#2}}\par}",
        rf"\hypersetup{{pdftitle={{{tex(document.title)}}},pdfauthor={{{tex(author or 'Auteur')}}},"
        r"pdfsubject={Rapport statistique préparé avec STATPFE}}",
        r"\begin{document}",
    ]


def _col_spec(t: Table) -> str:
    if t.key_value:
        return r">{\raggedright\arraybackslash}p{0.30\linewidth}>{\raggedright\arraybackslash}p{0.62\linewidth}"
    lengths = []
    for j in range(len(t.columns)):
        texts = [t.columns[j]] + [r[j] for r in t.rows if j < len(r)]
        longest = max((len(w) for x in texts for w in x.split()), default=4)
        avg = sum(len(x) for x in texts) / max(1, len(texts))
        lengths.append(max(longest, min(avg, 60), 4))
    total = sum(lengths)
    usable = 0.99 - 0.03 * len(lengths)  # 2 × \tabcolsep par colonne
    spec = []
    for j, n in enumerate(lengths):
        align = r"\raggedleft" if j < len(t.numeric) and t.numeric[j] else r"\raggedright"
        spec.append(rf">{{{align}\arraybackslash}}p{{{usable * n / total:.3f}\linewidth}}")
    return "".join(spec)


def _table(t: Table, th: themes.Theme) -> list[str]:
    out = [r"{\small", rf"\begin{{longtable}}{{{_col_spec(t)}}}"]
    caption = rf"\caption{{{tex(t.caption)}}}" if t.number else rf"\caption*{{{tex(t.caption)}}}"
    out.append(caption + r"\\")
    out.append(r"\toprule")
    if not t.key_value:
        head = " & ".join(rf"\textbf{{\color{{enteteTexte}}{tex(c)}}}" for c in t.columns)
        out += [r"\rowcolor{enteteFond}" + head + r"\\", r"\midrule", r"\endfirsthead"]
        out += [r"\rowcolor{enteteFond}" + head + r"\\", r"\midrule", r"\endhead"]
    for i, row in enumerate(t.rows):
        cells = [tex(v) for v in row]
        if t.key_value and cells:
            cells[0] = rf"\textbf{{{cells[0]}}}"
        prefix = r"\rowcolor{ligneClaire}" if th.color and i % 2 == 1 and not t.key_value else ""
        out.append(prefix + " & ".join(cells) + r"\\")
    out += [r"\bottomrule", r"\end{longtable}", "}"]
    if t.note:
        out.append(rf"{{\footnotesize\itshape\color{{gris}} Note : {tex(t.note)}\par}}")
    if t.source:
        out.append(rf"{{\footnotesize\itshape\color{{gris}} {tex(t.source)}\par}}")
    return out


def render(document: Document, path: Path, author: str = "") -> None:
    th = themes.get(document.theme)
    lines = _preamble(document, author, th)
    figures: list[tuple[str, bytes]] = []
    for b in document.blocks:
        if isinstance(b, Cover):
            lines += [r"\begin{titlepage}", r"\centering", r"\vspace*{3cm}",
                      rf"{{\large\color{{gris}} {tex(b.document.upper())}\par}}", r"\vspace{1cm}",
                      rf"{{\huge\bfseries\color{{accent}} {tex(b.title)}\par}}", r"\vspace{1.5cm}"]
            lines += [rf"{{\color{{gris}}{tex(k)} :}} \textbf{{{tex(v)}}}\par" for k, v in b.fields]
            lines += [r"\vspace{1cm}", tex(b.date) + r"\par", r"\vfill",
                      rf"{{\footnotesize\itshape\color{{gris}} {tex(b.disclaimer)}\par}}", r"\end{titlepage}"]
        elif isinstance(b, PageBreak):
            lines.append(r"\clearpage")
        elif isinstance(b, Toc):
            lines += [r"\renewcommand{\contentsname}{Sommaire}", r"\tableofcontents"]
        elif isinstance(b, Heading):
            cmd = "section" if b.level == 1 else "subsection"
            lines += [rf"\{cmd}*{{{tex(b.full)}}}", rf"\addcontentsline{{toc}}{{{cmd}}}{{{tex(b.full)}}}"]
        elif isinstance(b, Para):
            body = _runs(b.runs)
            if b.style == "note":
                lines.append(rf"{{\small\itshape\color{{gris}} {body}\par}}")
            elif b.style == "ai":
                lines.append(rf"\encadre{{noteIA}}{{{body}}}")
            elif b.style == "placeholder":
                lines.append(rf"\encadre{{aCompleter}}{{\itshape {body}}}")
            else:
                lines.append(body + r"\par")
        elif isinstance(b, Bullets):
            lines.append(r"\begin{itemize}")
            lines += [rf"\item {_runs(item)}" for item in b.items]
            lines.append(r"\end{itemize}")
        elif isinstance(b, Table):
            lines += _table(b, th)
        elif isinstance(b, Figure):
            name = f"figures/figure-{b.number}.png"
            figures.append((name, b.png))
            width = min(b.width_cm / 16.0, 1.0)
            lines += [r"\begin{figure}[H]", r"\centering",
                      rf"\includegraphics[width={width:.2f}\linewidth]{{{name}}}",
                      rf"\caption{{{tex(b.caption)}}}", r"\end{figure}",
                      rf"{{\footnotesize\itshape\color{{gris}} Description : {tex(b.description)}\par}}",
                      rf"{{\footnotesize\itshape\color{{gris}} {tex(b.source)}\par}}"]
        lines.append("")
    lines.append(r"\end{document}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(MAIN, "\n".join(lines) + "\n")
        for name, data in figures:
            z.writestr(name, data)
        z.writestr("LISEZMOI.txt",
                   "Rapport STATPFE au format LaTeX.\n\n"
                   "Overleaf : New Project > Upload Project, puis choisir ce fichier .zip.\n"
                   f"Sur votre ordinateur : décompresser, puis compiler {MAIN} avec pdflatex (deux fois, pour le "
                   "sommaire).\n")
    path.write_bytes(buf.getvalue())


__all__ = ["render", "tex", "MAIN"]
