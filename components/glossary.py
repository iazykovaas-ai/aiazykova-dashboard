"""Единый словарь аббревиатур/англ. терминов дашборда + расшифровка по страницам.

Используется и в свёртке «Расшифровка аббревиатур» на каждой странице
(render_abbr_expander), и в ИИ-навигаторе (assistant.py импортирует ABBR).
"""
from __future__ import annotations

import streamlit as st

# key -> (как показываем сокращение, расшифровка на русском)
ABBR: dict[str, tuple[str, str]] = {
    "YoY": ("YoY (Year-over-Year)", "изменение к тому же периоду прошлого года"),
    "MoM": ("MoM (Month-over-Month)", "изменение к предыдущему месяцу"),
    "YTD": ("YTD (Year-to-Date)", "накопительно с начала года"),
    "pp": ("п.п.", "процентные пункты — разница между двумя значениями в %"),
    "Revenue": ("Revenue", "Выручка"),
    "GP": ("GP / Gross Profit", "Валовая прибыль = Выручка − Прямые расходы"),
    "OPEX": ("OPEX (Operating Expenses)",
             "операционные (текущие) расходы: ПО и ИТ, маркетинг, персонал, аренда и т.д."),
    "GA": ("G&A (General & Administrative)", "общехозяйственные и административные расходы"),
    "FX": ("FX (Foreign Exchange)", "валютные курсовые разницы"),
    "OperatingProfit": ("Operating Profit",
                        "Операционная прибыль = Валовая прибыль − OPEX ± переоценка"),
    "PBT": ("PBT (Profit Before Tax)", "прибыль до налогообложения"),
    "Net": ("Net Profit", "Чистая прибыль — прибыль после уплаты налога, нижняя строка P&L"),
    "PL": ("P&L (Profit & Loss)", "отчёт о прибылях и убытках"),
    "Turnover": ("Turnover / Turnover ratio",
                 "Оборот / маржинальность (отношение прибыли к обороту, %)"),
    "units": ("k / M USD", "тысячи / миллионы долларов США (k = тыс., M = млн)"),
    "nm": ("n/m (not meaningful)", "% не показателен — план ≈ 0 или смена знака"),
    "vs": ("vs (versus)", "«против», сравнение — напр. Факт vs План"),
    "Waterfall": ("Waterfall",
                  "каскадная диаграмма («мостик») — как из стартовой суммы складывается итог"),
    "Treemap": ("Treemap", "плиточная диаграмма — площадь плитки = доля статьи"),
    "OAG": ("Other / Agent / Gold",
            "прочие / агентские / золото — исключаются из месячных итогов и разбивки по линиям"),
    "marginality": ("Маржинальность",
                    "отношение прибыли к обороту, % — сколько зарабатываем с каждого $ оборота"),
    "MP": ("Маржинальная прибыль", "прибыль от сделок до операционных расходов"),
    "avgcheck": ("Средний чек", "средний оборот на одну сделку за период"),
}

# Какие термины показывать на каждой странице (только те, что реально встречаются).
PAGE_FIN = ["Revenue", "GP", "OPEX", "GA", "FX", "OperatingProfit", "PBT", "Net",
            "Turnover", "marginality", "Waterfall", "Treemap", "YoY", "MoM", "YTD",
            "pp", "units", "PL"]
PAGE_DEV = ["GP", "OPEX", "PBT", "Net", "Waterfall", "vs", "nm", "pp", "units", "PL"]
PAGE_MON = ["MoM", "OAG", "marginality", "MP", "avgcheck", "Turnover", "units"]
PAGE_SEG = ["marginality", "MP", "avgcheck", "Turnover", "units"]


def render_abbr_expander(keys: list[str], title: str = "ℹ️ Расшифровка аббревиатур") -> None:
    """Свёртка с таблицей расшифровок только по переданным ключам."""
    seen, rows_md = set(), []
    for k in keys:
        if k in ABBR and k not in seen:
            seen.add(k)
            term, expl = ABBR[k]
            rows_md.append(f"| **{term}** | {expl} |")
    if not rows_md:
        return
    with st.expander(title):
        st.markdown("| Сокр. | Расшифровка |\n|---|---|\n" + "\n".join(rows_md))
