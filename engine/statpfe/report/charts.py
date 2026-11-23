"""Figures des rapports, dessinées avec matplotlib à partir des valeurs enregistrées.

Les figures ne recalculent rien : elles reprennent les données de graphique du
résultat enregistré (comme l'interface). Elles sont en niveaux de gris (hachures
pour distinguer les séries) avec le thème « sobre », ou en couleurs lisibles par les
personnes daltoniennes avec les autres thèmes (voir theme.py).
"""

from __future__ import annotations

import io
from typing import Any

from statpfe.errors import ValidationError
from statpfe.report import theme as themes
from statpfe.report.fmt import fixed

DPI = 220
INK = "#222222"
IMAGE_FORMATS = {"png": "PNG (image, 300 dpi)", "svg": "SVG (vectoriel)"}


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK, "axes.labelcolor": INK,
        "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
        "axes.formatter.use_locale": False, "svg.fonttype": "none", "hatch.color": INK, "hatch.linewidth": 0.6,
    })
    return plt


def _fr_axis(ax, which: str = "y") -> None:
    from matplotlib.ticker import FuncFormatter

    def f(x, _):
        a = abs(x)
        if a and (a >= 1e6 or a < 1e-3):
            return f"{x:.1e}".replace(".", ",")
        digits = 0 if a >= 100 or float(x).is_integer() else (1 if a >= 1 else 2)
        return fixed(x, digits)

    axis = ax.yaxis if which == "y" else ax.xaxis
    axis.set_major_formatter(FuncFormatter(f))


def render(chart: dict[str, Any], theme: str | None = "sobre", fmt: str = "png", dpi: int = DPI) -> bytes:
    if fmt not in IMAGE_FORMATS:
        raise ValidationError("Format d'image inconnu.")
    th = themes.get(theme)
    plt = _plt()
    line = th.primary if th.color else INK
    kind, d = chart["type"], chart["data"]
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    try:
        if kind == "histogram":
            edges, counts = d["edges"], d["counts"]
            widths = [b - a for a, b in zip(edges[:-1], edges[1:])]
            ax.bar(edges[:-1], counts, width=widths, align="edge", color=th.fill, edgecolor=line, linewidth=0.6)
            ax.set_xlabel(d["variable"] + (f" ({d['unit']})" if d.get("unit") else ""))
            ax.set_ylabel("Effectif")
            _fr_axis(ax, "x")
        elif kind == "boxplot":
            series = d["series"]
            stats = [{"med": s["median"], "q1": s["q1"], "q3": s["q3"], "whislo": s["whisker_low"],
                      "whishi": s["whisker_high"], "mean": s["mean"], "fliers": s["outliers"],
                      "label": f"{s['label']}\n(n = {s['n']})"} for s in series]
            ax.bxp(stats, showmeans=True, patch_artist=True, widths=0.5,
                   boxprops={"facecolor": th.light, "edgecolor": line, "linewidth": 0.8},
                   medianprops={"color": line, "linewidth": 1.6},
                   meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": line, "markersize": 5},
                   flierprops={"marker": "o", "markerfacecolor": "none", "markeredgecolor": line, "markersize": 4},
                   whiskerprops={"color": line}, capprops={"color": line})
            if th.color:
                for patch, color in zip(ax.patches, th.series):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.55)
            if d.get("unit"):
                ax.set_ylabel(d["unit"])
            _fr_axis(ax)
        elif kind == "bar":
            bars = d["bars"]
            labels = [b["label"] for b in bars]
            ax.bar(range(len(bars)), [b["count"] for b in bars], color=th.fill, edgecolor=line, linewidth=0.6)
            ax.set_xticks(range(len(bars)), labels, rotation=30 if max(map(len, labels), default=0) > 8 else 0,
                          ha="right" if max(map(len, labels), default=0) > 8 else "center")
            ax.set_ylabel("Effectif")
            for i, b in enumerate(bars):
                ax.annotate(f"{fixed(b['percent'] * 100, 1)} %", (i, b["count"]), ha="center", va="bottom",
                            fontsize=8, xytext=(0, 2), textcoords="offset points")
            _fr_axis(ax)
        elif kind == "stacked":
            rows, cols, pct = d["rows"], d["columns"], d["percent"]
            left = [0.0] * len(rows)
            for j, c in enumerate(cols):
                vals = [pct[i][j] * 100 for i in range(len(rows))]
                ax.barh(range(len(rows)), vals, left=left, color=th.series[j % len(th.series)],
                        edgecolor=INK if not th.color else "white", linewidth=0.6,
                        hatch=th.hatches[j % len(th.hatches)], label=c)
                left = [a + b for a, b in zip(left, vals)]
            ax.set_yticks(range(len(rows)), rows)
            ax.invert_yaxis()
            ax.set_xlim(0, 100)
            ax.set_xlabel("Pourcentage en ligne (%)")
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=min(len(cols), 5), frameon=False,
                      fontsize=8)
        elif kind == "scatter":
            pts = d["points"]
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=12, facecolors=th.light if th.color else "none",
                       edgecolors=th.fill if th.color else INK, linewidths=0.7)
            ax.set_xlabel(d["x_label"])
            ax.set_ylabel(d["y_label"])
            _fr_axis(ax)
            _fr_axis(ax, "x")
        elif kind == "power_curve":
            styles = ["-", "--", ":", "-.", (0, (5, 1, 1, 1)), (0, (1, 3))]
            for i, ser in enumerate(d["series"]):
                pts = [p for p in ser["points"] if p[1] is not None]
                ax.plot([p[0] for p in pts], [p[1] * 100 for p in pts], color=th.series[i % len(th.series)] if th.color else INK,
                        linewidth=1.4 if th.color else 1.2, linestyle=styles[i % len(styles)], label=ser["label"])
            if d.get("target") is not None:
                ax.axhline(d["target"] * 100, color="#8c8c8c", linewidth=0.8, linestyle="--")
                ax.annotate(f"puissance visée {fixed(d['target'] * 100, 0)} %", (1, d["target"] * 100),
                            xycoords=("axes fraction", "data"), ha="right", va="bottom", fontsize=7.5,
                            color="#4d4d4d")
            if d.get("marker") is not None:
                ax.axvline(d["marker"], color="#8c8c8c", linewidth=0.8, linestyle=":")
            ax.set_ylim(0, 100)
            ax.set_xlabel(d["x_label"])
            ax.set_ylabel("Puissance (%)")
            _fr_axis(ax, "x")
            if len(d["series"]) > 1:
                ax.legend(frameon=False, fontsize=8, loc="lower right")
        else:
            raise ValueError(f"type de graphique inconnu : {kind}")
        if th.color:
            ax.title.set_color(th.primary)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi, metadata=None if fmt == "png" else {"Date": None})
        return buf.getvalue()
    finally:
        plt.close(fig)


def describe(chart: dict[str, Any]) -> str:
    """Description textuelle d'une figure (accessibilité, lecture sans l'image)."""
    kind, d = chart["type"], chart["data"]
    if kind == "histogram":
        edges = d["edges"]
        return (f"Histogramme de « {d['variable']} » : {len(d['counts'])} classes de {fixed(edges[0], 2)} à "
                f"{fixed(edges[-1], 2)}, n = {d['n']}. La classe la plus fréquente regroupe {max(d['counts'])} "
                "observation(s).")
    if kind == "boxplot":
        parts = [f"« {s['label']} » : médiane {fixed(s['median'], 2)}, quartiles {fixed(s['q1'], 2)} et "
                 f"{fixed(s['q3'], 2)}, {s['outlier_count']} valeur(s) extrême(s), n = {s['n']}"
                 for s in d["series"]]
        return "Boîtes à moustaches (méthode de Tukey, 1,5 × EIQ ; losange : moyenne). " + " ; ".join(parts) + "."
    if kind == "bar":
        parts = [f"{b['label']} : {b['count']} ({fixed(b['percent'] * 100, 1)} %)" for b in d["bars"]]
        return f"Diagramme en barres des effectifs (n = {d['n']}). " + " ; ".join(parts) + "."
    if kind == "stacked":
        return (f"Barres empilées des pourcentages en ligne : {len(d['rows'])} ligne(s) ({', '.join(d['rows'])}) "
                f"et {len(d['columns'])} modalité(s) ({', '.join(d['columns'])}).")
    if kind == "scatter":
        extra = " (échantillon des points affiché)" if d.get("truncated") else ""
        return f"Nuage de points de « {d['y_label']} » en fonction de « {d['x_label']} », n = {d['n']}{extra}."
    if kind == "power_curve":
        target = (f" La ligne horizontale marque la puissance visée ({fixed(d['target'] * 100, 0)} %)."
                  if d.get("target") is not None else "")
        parts = []
        for ser in d["series"]:
            pts = [p for p in ser["points"] if p[1] is not None]
            if pts:
                parts.append(f"{ser['label']} : de {fixed(pts[0][1] * 100, 0)} % à {fixed(pts[-1][1] * 100, 0)} %")
        xs = d["series"][0]["points"]

        def xf(v: float) -> str:
            return fixed(v, 0 if float(v).is_integer() else 2)
        return (f"Courbe de la puissance (en %) selon « {d['x_label']} », de {xf(xs[0][0])} à {xf(xs[-1][0])}. " + " ; ".join(parts) + "." + target)
    return ""
