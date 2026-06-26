import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.kpi import fmt_kusd
from components.styles import (PALETTE, apply, chart_card_close, chart_card_open,
                               hero, style_plotly_2d)
from config import MONTH_NAMES_RU, TARGET_MONTH, TARGET_YEAR
from data.sheets_loader import (load_pl_global_raw, pl_value, seg_fact_months,
                                seg_margin_budget, seg_margin_fact,
                                seg_margin_total)

st.set_page_config(page_title="Факторный анализ", page_icon="📊", layout="wide")
apply()
render_assistant()

hero("📊 План - Факт",
     "Что развело Бюджет и Факт и что изменилось от периода к периоду")

rows = load_pl_global_raw()

# Факторы P&L, которые в сумме дают чистую прибыль (выручку и прямые расходы НЕ показываем —
# они внутри валовой прибыли; в Бюджет/Факт бюджета по ним всё равно нет).
PNL_FACTORS = [
    ("gross_profit",      "Валовая прибыль (маржа)"),
    ("revaluation",       "Переоценка"),
    ("realized_fx",       "Реализ. FX"),
    ("unrealized_fx",     "Нереализ. FX"),
    ("opex",              "OPEX"),
    ("other_income",      "Прочие дох./расх."),
    ("financial_inc_exp", "Финансовые"),
    ("income_tax",        "Налог"),
]


def pl_sum(metric, m_from, m_to, source="fact", year=TARGET_YEAR):
    return sum(pl_value(rows, metric, m, source, year) for m in range(m_from, m_to + 1))


def waterfall_bridge(start_label, start_val, steps, end_label, end_val, title, subtitle):
    """steps = [(label, delta), ...]. Рисует мостик start → … → end."""
    chart_card_open(title, subtitle)
    labels = [start_label] + [s[0] for s in steps] + [end_label]
    measures = ["absolute"] + ["relative"] * len(steps) + ["total"]
    values = [start_val] + [s[1] for s in steps] + [end_val]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measures, x=labels, y=values,
        text=[fmt_kusd(v) for v in values],
        textposition="outside", textfont=dict(color=PALETTE["ink"], size=11),
        connector=dict(line=dict(color=PALETTE["line"], width=1)),
        increasing=dict(marker=dict(color="#2FD9A6")),
        decreasing=dict(marker=dict(color="#FF5C7A")),
        totals=dict(marker=dict(color="#8B7BF0")),
    ))
    style_plotly_2d(fig, height=470)
    fig.update_layout(yaxis=dict(title="тыс. USD"), xaxis=dict(showgrid=False, tickangle=-30))
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": True, "displaylogo": False})
    chart_card_close()


def seg_steps(cur: dict, base: dict):
    """Список (сегмент, изменение) отсортированный от худшего к лучшему."""
    out = [(label, cur.get(label, 0) - base.get(label, 0)) for label in cur]
    out = [(l, d) for l, d in out if abs(d) > 0.5]
    out.sort(key=lambda s: s[1])
    return out


FACT_MONTHS = seg_fact_months()   # месяцы с фактом по сегментам (1..6)

tab_bf, tab_pp = st.tabs(["💰 Бюджет / Факт", "🔄 Прошлый / Текущий период"])

# ======================= БЮДЖЕТ / ФАКТ =======================
with tab_bf:
    dim = st.radio("Разрез", ["Статьи P&L", "Сегменты (маржа)"], horizontal=True, key="bf_dim")

    if dim == "Статьи P&L":
        c1, c2 = st.columns(2)
        with c1:
            bf_from = st.selectbox("С месяца", list(range(1, 13)),
                                   format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                   index=0, key="bf_from")
        with c2:
            bf_to = st.selectbox("По месяц", list(range(1, 13)),
                                 format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                 index=TARGET_MONTH - 1, key="bf_to")
        if bf_from > bf_to:
            bf_from, bf_to = bf_to, bf_from
        bf_label = (f"{MONTH_NAMES_RU[bf_from - 1]} {TARGET_YEAR}" if bf_from == bf_to
                    else f"{MONTH_NAMES_RU[bf_from - 1]} — {MONTH_NAMES_RU[bf_to - 1]} {TARGET_YEAR}")
        net_budget = pl_sum("net_profit", bf_from, bf_to, "budget")
        net_fact = pl_sum("net_profit", bf_from, bf_to, "fact")
        steps, covered = [], 0.0
        for key, label in PNL_FACTORS:
            bud = pl_sum(key, bf_from, bf_to, "budget")
            if bud == 0:
                continue
            var = pl_sum(key, bf_from, bf_to, "fact") - bud
            steps.append((label, var))
            covered += var
        residual = (net_fact - net_budget) - covered
        if abs(residual) > 1:
            steps.append(("Прочее (без бюджета)", residual))
        waterfall_bridge("Бюджет ЧП", net_budget, steps, "Факт ЧП", net_fact,
                         f"Бюджет → Факт чистой прибыли · {bf_label}",
                         "Вклад статей в отклонение (тыс. USD). Выручка/прямые расходы — внутри маржи")
    else:
        if not FACT_MONTHS:
            st.warning("Нет фактических данных по сегментам.")
        else:
            m = st.selectbox("Месяц", FACT_MONTHS, index=len(FACT_MONTHS) - 1,
                             format_func=lambda x: MONTH_NAMES_RU[x - 1], key="bf_seg_m")
            budget = seg_margin_budget(m)
            fact = seg_margin_fact(m)
            tot_b = seg_margin_total(m, "budget")
            tot_f = seg_margin_total(m, "fact")
            steps = seg_steps(fact, budget)
            covered = sum(d for _, d in steps)
            residual = (tot_f - tot_b) - covered
            if abs(residual) > 1:
                steps.append(("Прочее/неучтённое", residual))
            waterfall_bridge("Бюджет маржи", tot_b, steps, "Факт маржи", tot_f,
                             f"Бюджет → Факт маржинальной прибыли по сегментам · {MONTH_NAMES_RU[m - 1]} {TARGET_YEAR}",
                             "Вклад каждого сегмента в отклонение факта от плана (тыс. USD)")

# ======================= ПРОШЛЫЙ / ТЕКУЩИЙ ПЕРИОД =======================
with tab_pp:
    dim2 = st.radio("Разрез", ["Статьи P&L", "Сегменты (маржа)"], horizontal=True, key="pp_dim")

    if dim2 == "Статьи P&L":
        c1, c2 = st.columns(2)
        with c1:
            cur_m = st.selectbox("Текущий месяц", list(range(1, 13)),
                                 format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                 index=TARGET_MONTH - 1, key="pp_cur")
        with c2:
            prev_m = st.selectbox("Сравнить с месяцем", list(range(1, 13)),
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                  index=max(0, TARGET_MONTH - 2), key="pp_prev")
        net_prev = pl_sum("net_profit", prev_m, prev_m, "fact")
        net_cur = pl_sum("net_profit", cur_m, cur_m, "fact")
        steps = []
        for key, label in PNL_FACTORS:
            delta = pl_sum(key, cur_m, cur_m, "fact") - pl_sum(key, prev_m, prev_m, "fact")
            if abs(delta) > 1:
                steps.append((label, delta))
        waterfall_bridge(f"ЧП {MONTH_NAMES_RU[prev_m - 1]}", net_prev, steps,
                         f"ЧП {MONTH_NAMES_RU[cur_m - 1]}", net_cur,
                         f"Чистая прибыль: {MONTH_NAMES_RU[prev_m - 1]} → {MONTH_NAMES_RU[cur_m - 1]} {TARGET_YEAR}",
                         "Вклад статей в изменение (тыс. USD)")
    else:
        if len(FACT_MONTHS) < 2:
            st.warning("Недостаточно фактических месяцев по сегментам для сравнения.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                sc = st.selectbox("Текущий месяц", FACT_MONTHS, index=len(FACT_MONTHS) - 1,
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1], key="pp_seg_cur")
            with c2:
                sp = st.selectbox("Сравнить с месяцем", FACT_MONTHS, index=len(FACT_MONTHS) - 2,
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1], key="pp_seg_prev")
            fact_cur = seg_margin_fact(sc)
            fact_prev = seg_margin_fact(sp)
            tot_cur = seg_margin_total(sc, "fact")
            tot_prev = seg_margin_total(sp, "fact")
            steps = seg_steps(fact_cur, fact_prev)
            residual = (tot_cur - tot_prev) - sum(d for _, d in steps)
            if abs(residual) > 1:
                steps.append(("Прочее/неучтённое", residual))
            waterfall_bridge(f"Маржа {MONTH_NAMES_RU[sp - 1]}", tot_prev, steps,
                             f"Маржа {MONTH_NAMES_RU[sc - 1]}", tot_cur,
                             f"Маржинальная прибыль по сегментам: {MONTH_NAMES_RU[sp - 1]} → {MONTH_NAMES_RU[sc - 1]} {TARGET_YEAR}",
                             "Вклад каждого сегмента в изменение (тыс. USD)")
