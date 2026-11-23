"""Lois exactes des statistiques de rangs, calculées par dénombrement.

Ces fonctions reproduisent `pwilcox`, `psignrank` et l'algorithme AS 89
(`cor.test(method = "spearman")`) de R, afin d'obtenir les mêmes valeurs p
exactes que R pour les petits échantillons.
"""

from __future__ import annotations

import math
from functools import lru_cache
from itertools import permutations

import numpy as np
from scipy.stats import norm


@lru_cache(maxsize=64)
def _wilcox_counts(m: int, n: int) -> np.ndarray:
    """Nombre de façons d'obtenir chaque valeur de U (0..m*n) pour des échantillons de tailles m et n."""
    # f[i][j] = distribution de U pour (i, j) ; récurrence f(i,j,u) = f(i-1,j,u-j) + f(i,j-1,u)
    prev = [np.ones(1, dtype=object) for _ in range(n + 1)]  # i = 0 : U = 0 une seule façon
    for i in range(1, m + 1):
        cur = [np.ones(1, dtype=object)]  # j = 0
        for j in range(1, n + 1):
            size = i * j + 1
            arr = np.zeros(size, dtype=object)
            a = prev[j]          # (i-1, j), décalé de j
            arr[j:j + len(a)] += a
            b = cur[j - 1]       # (i, j-1)
            arr[:len(b)] += b
            cur.append(arr)
        prev = cur
    return prev[n]


def pwilcox(q: float, m: int, n: int, lower_tail: bool = True) -> float:
    counts = _wilcox_counts(m, n)
    total = math.comb(m + n, n)
    q = math.floor(q + 1e-7)
    if lower_tail:
        if q < 0:
            return 0.0
        return float(sum(counts[: min(q, m * n) + 1]) / total)
    if q < 0:
        return 1.0
    return float(sum(counts[q + 1:]) / total) if q < m * n else 0.0


@lru_cache(maxsize=64)
def _signrank_counts(n: int) -> np.ndarray:
    top = n * (n + 1) // 2
    c = np.zeros(top + 1, dtype=object)
    c[0] = 1
    for k in range(1, n + 1):
        c[k:] = c[k:] + c[:-k].copy() if k <= top else c[k:]
    return c


def psignrank(q: float, n: int, lower_tail: bool = True) -> float:
    counts = _signrank_counts(n)
    total = 2 ** n
    top = n * (n + 1) // 2
    q = math.floor(q + 1e-7)
    if lower_tail:
        if q < 0:
            return 0.0
        return float(sum(counts[: min(q, top) + 1]) / total)
    if q < 0:
        return 1.0
    return float(sum(counts[q + 1:]) / total) if q < top else 0.0


@lru_cache(maxsize=16)
def _spearman_exact_s(n: int) -> np.ndarray:
    base = np.arange(1, n + 1)
    return np.array([int(((base - np.array(p)) ** 2).sum()) for p in permutations(range(1, n + 1))])


def prho(s_value: float, n: int, lower_tail: bool) -> float:
    """Algorithme AS 89 tel que dans R : P[S ≥ is] (ou son complément si lower_tail)."""
    pv = 0.0 if lower_tail else 1.0
    if n <= 1 or s_value <= 0:
        return pv
    n3 = n * (n * n - 1) / 3
    if s_value > n3:
        return 1 - pv
    if n <= 9:
        all_s = _spearman_exact_s(n)
        ifr = int((all_s >= s_value).sum())
        nfac = math.factorial(n)
        return (nfac - ifr) / nfac if lower_tail else ifr / nfac
    c1, c2, c3, c4, c5, c6 = 0.2274, 0.2531, 0.1745, 0.0758, 0.1033, 0.3932
    c7, c8, c9, c10, c11, c12 = 0.0879, 0.0151, 0.0072, 0.0831, 0.0131, 4.6e-4
    b = 1 / n
    x = (6 * (s_value - 1) * b / (n * n - 1) - 1) * math.sqrt(1 / b - 1)
    y = x * x
    u = x * b * (c1 + b * (c2 + c3 * b) + y * (-c4 + b * (c5 + c6 * b)
                                                - y * b * (c7 + c8 * b - y * (c9 - c10 * b + y * b * (c11 - c12 * y)))))
    y = u / math.exp(y / 2)
    upper = min(max(y + float(norm.sf(x)), 0.0), 1.0)
    return 1 - upper if lower_tail else upper


def pspearman(q: float, n: int, lower_tail: bool, exact: bool) -> float:
    if n <= 1290 and exact:
        return prho(round(q) + 2 * lower_tail, n, lower_tail)
    from scipy.stats import t

    den = n * (n * n - 1) / 6
    r = 1 - q / den
    stat = r / math.sqrt((1 - r * r) / (n - 2)) if abs(r) < 1 else math.copysign(math.inf, r)
    return float(t.cdf(stat, n - 2) if not lower_tail else t.sf(stat, n - 2))
