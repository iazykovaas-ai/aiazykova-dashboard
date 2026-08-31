"""Общие хелперы форматирования и мелкие утилиты — чтобы не дублировать по страницам.

Собрано из локальных копий, которые раньше были на каждой странице
(_qp_int, _md, форматтеры денег/процентов, заливка таблиц).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def qp_int(key: str, default: int) -> int:
    """Целое из URL query-параметра (?key=), либо default."""
    try:
        return int(st.query_params.get(key, default))
    except (TypeError, ValueError):
        return default


def md_escape(s: str) -> str:
    """Экранирует $ — иначе markdown трактует $…$ как формулу LaTeX
    (курсив и съеденные пробелы между разрядами)."""
    return s.replace("$", "\\$")


def usd_spaced(v: float) -> str:
    """Деньги: '$ 1 234 567' (пробелы-разряды). $ безопасен в st.dataframe."""
    return f"$ {v:,.0f}".replace(",", " ")


def num_spaced(v: float) -> str:
    """Число с пробелами-разрядами без знака валюты: '1 234 567' (для подписей на барах)."""
    return f"{v:,.0f}".replace(",", " ")


def pct_ru(v: float, digits: int = 2) -> str:
    """Доля → процент с русской запятой: 0.0214 → '2,14%'."""
    return f"{v * 100:.{digits}f}%".replace(".", ",")


def eff_ru(v) -> str:
    """Эффективность (кратность): 5.1 → '5,1×'; NaN → '—'."""
    return "—" if pd.isna(v) else f"{v:.1f}×".replace(".", ",")


def bg_diverging(s: pd.Series) -> list[str]:
    """«Тепловая» заливка ячеек столбца: зелёный (плюс) / красный (минус),
    яркость ∝ величине. Для Styler.apply(subset=[...])."""
    m = s.abs().max() or 1
    out = []
    for v in s:
        if pd.isna(v) or v == 0:
            out.append("color:#8A90B8;")
        elif v > 0:
            a = 0.14 + 0.34 * min(v / m, 1)
            out.append(f"background-color: rgba(47,217,166,{a:.2f}); color:#EAFBF4;")
        else:
            a = 0.14 + 0.34 * min(abs(v) / m, 1)
            out.append(f"background-color: rgba(255,92,122,{a:.2f}); color:#FFECEF;")
    return out
