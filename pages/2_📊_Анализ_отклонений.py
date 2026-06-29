import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.kpi import fmt_kusd
from components.styles import (PALETTE, apply, chart_card_close, chart_card_open,
                               hero, style_plotly_2d)
from config import (MONTH_NAMES_RU, MONTH_NAMES_SHORT, PL_FULL_METRICS,
                    TARGET_MONTH, TARGET_YEAR)
from data.sheets_loader import (load_pl_global_raw, pl_value, pl_rows_value,
                                seg_fact_months,
                                seg_margin_budget, seg_margin_fact, seg_margin_total)

st.set_page_config(page_title="Анализ отклонений", page_icon="📊", layout="wide")
apply()
render_assistant()

hero("📊 Анализ отклонений",
     "Факт против плана и против прошлого периода — с разбором по факторам и кратким выводом")

rows = load_pl_global_raw()

# Метрики с заполненным бюджетом (выручка/прямые расходы — пусто, не показываем)
PF_METRICS = [("turnover", "Оборот"), ("gross_profit", "Маржинальная прибыль"),
              ("opex", "OPEX"), ("net_profit", "Чистая прибыль")]
KPI_KEYS = ["turnover", "gross_profit", "net_profit"]

# Факторы P&L, складывающиеся в чистую прибыль (выручка/прямые расходы — внутри маржи)
PNL_FACTORS = [
    ("gross_profit",      "Валовая прибыль (маржа)"),
    ("revaluation",       "Переоценка"),
    ("realized_fx",       "Внутрибанк. конвертации"),
    ("unrealized_fx",     "Нереализ. FX"),
    ("opex",              "OPEX"),
    ("other_income",      "Прочие дох./расх."),
    ("financial_inc_exp", "Финансовые"),
    ("income_tax",        "Налог"),
]


def pl_sum(metric, a, b, source):
    return sum(pl_value(rows, metric, m, source) for m in range(a, b + 1))


def waterfall_bridge(start_label, start_val, steps, end_label, end_val, title, subtitle):
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
                    config={"displayModeBar": True, "displaylogo": False,
                            "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
    chart_card_close()


def insight_box(total_dev, steps):
    """Краткий авто-вывод: общее отклонение + топ факторов вверх/вниз."""
    real = [(l, d) for l, d in steps if "Прочее" not in l]
    pos = sorted([s for s in real if s[1] > 0], key=lambda s: -s[1])[:2]
    neg = sorted([s for s in real if s[1] < 0], key=lambda s: s[1])[:2]
    dirn = "выше" if total_dev >= 0 else "ниже"
    parts = [f"📌 **Итого {dirn} на {fmt_kusd(abs(total_dev))}.**"]
    if neg:
        parts.append("Снизили: " + ", ".join(f"{l} ({fmt_kusd(d)})" for l, d in neg) + ".")
    if pos:
        parts.append("Помогли: " + ", ".join(f"{l} ({fmt_kusd(d)})" for l, d in pos) + ".")
    st.info(" ".join(parts))


def seg_steps(cur: dict, base: dict):
    out = [(l, cur.get(l, 0) - base.get(l, 0)) for l in cur]
    out = [(l, d) for l, d in out if abs(d) > 0.5]
    out.sort(key=lambda s: s[1])
    return out


def seg_sum(func, months):
    out: dict = {}
    for m in months:
        for k, v in func(m).items():
            out[k] = out.get(k, 0) + v
    return out


FACT_MONTHS = seg_fact_months()

tab_pf, tab_pp = st.tabs(["🎯 План vs Факт", "🔄 Период к периоду"])

# ============================ ПЛАН vs ФАКТ ============================
with tab_pf:
    st.markdown("##### 📅 Период")
    cfrom, cto = st.columns(2)
    with cfrom:
        st.session_state.setdefault("ao_from", 1)
        from_m = st.selectbox("С месяца", list(range(1, 13)),
                              format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_from")
    with cto:
        st.session_state.setdefault("ao_to", 1)
        to_m = st.selectbox("По месяц", list(range(1, 13)),
                            format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_to")
    if from_m > to_m:
        from_m, to_m = to_m, from_m
    period_label = (f"{MONTH_NAMES_RU[from_m - 1]} {TARGET_YEAR}" if from_m == to_m
                    else f"{MONTH_NAMES_RU[from_m - 1]} — {MONTH_NAMES_RU[to_m - 1]} {TARGET_YEAR}")

    # KPI: факт + % к плану
    labels = dict(PF_METRICS)
    for col, key in zip(st.columns(len(KPI_KEYS)), KPI_KEYS):
        fact = pl_sum(key, from_m, to_m, "fact")
        budget = pl_sum(key, from_m, to_m, "budget")
        done = fact / budget * 100 if budget else None
        col.metric(labels[key], fmt_kusd(fact),
                   f"{done - 100:+.1f}% к плану" if done is not None else "нет плана")

    st.markdown("")

    # Помесячно план/факт + % выполнения
    mi = st.selectbox("Метрика для графика", list(range(len(PL_FULL_METRICS))),
                      format_func=lambda i: PL_FULL_METRICS[i][0].strip(), key="ao_metric")
    m_label, m_rows = PL_FULL_METRICS[mi]
    m_label = m_label.strip()
    chart_card_open(f"План vs Факт по месяцам · {m_label} · {period_label}", "тыс. USD")
    months = list(range(from_m, to_m + 1))
    plan = [pl_rows_value(rows, m_rows, m, "budget") for m in months]
    fact = [pl_rows_value(rows, m_rows, m, "fact") for m in months]
    if not any(plan):
        st.caption("ℹ️ По этой статье плана нет — показан только факт.")
    xnames = [MONTH_NAMES_SHORT[m - 1] for m in months]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=xnames, y=plan, name="План", marker=dict(color="#8B7BF0"),
                         text=[fmt_kusd(v) for v in plan], textposition="outside",
                         textfont=dict(color=PALETTE["ink"], size=10),
                         hovertemplate="<b>%{x}</b><br>План: %{text}<extra></extra>"))
    fig.add_trace(go.Bar(x=xnames, y=fact, name="Факт",
                         marker=dict(color=["#2FD9A6" if f >= p else "#FF5C7A"
                                            for f, p in zip(fact, plan)]),
                         text=[fmt_kusd(v) for v in fact], textposition="outside",
                         textfont=dict(color=PALETTE["ink"], size=10),
                         hovertemplate="<b>%{x}</b><br>Факт: %{text}<extra></extra>"))
    style_plotly_2d(fig, height=400)
    fig.update_layout(barmode="group", xaxis=dict(showgrid=False),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()

    # Факторный мостик «Бюджет → Факт»
    st.markdown("##### 🔻 Разбор отклонения от плана")
    dim = st.radio("Разрез", ["Статьи P&L", "Сегменты (маржа)"], horizontal=True, key="ao_bf_dim")
    if dim == "Статьи P&L":
        net_budget = pl_sum("net_profit", from_m, to_m, "budget")
        net_fact = pl_sum("net_profit", from_m, to_m, "fact")
        steps, covered = [], 0.0
        for key, label in PNL_FACTORS:
            bud = pl_sum(key, from_m, to_m, "budget")
            if bud == 0:
                continue
            var = pl_sum(key, from_m, to_m, "fact") - bud
            steps.append((label, var))
            covered += var
        residual = (net_fact - net_budget) - covered
        if abs(residual) > 1:
            steps.append(("Прочее (без бюджета)", residual))
        waterfall_bridge("Бюджет ЧП", net_budget, steps, "Факт ЧП", net_fact,
                         f"Бюджет → Факт чистой прибыли · {period_label}",
                         "Вклад статей в отклонение (тыс. USD)")
        insight_box(net_fact - net_budget, steps)
    else:
        fmonths = [m for m in months if m in FACT_MONTHS]
        if not fmonths:
            st.warning("За выбранный период нет фактических данных по сегментам (факт по июнь).")
        else:
            budget = seg_sum(seg_margin_budget, fmonths)
            fact_seg = seg_sum(seg_margin_fact, fmonths)
            tot_b = sum(seg_margin_total(m, "budget") for m in fmonths)
            tot_f = sum(seg_margin_total(m, "fact") for m in fmonths)
            steps = seg_steps(fact_seg, budget)
            residual = (tot_f - tot_b) - sum(d for _, d in steps)
            if abs(residual) > 1:
                steps.append(("Прочее/неучтённое", residual))
            plabel = (MONTH_NAMES_RU[fmonths[0] - 1] if len(fmonths) == 1
                      else f"{MONTH_NAMES_RU[fmonths[0] - 1]} — {MONTH_NAMES_RU[fmonths[-1] - 1]}")
            waterfall_bridge("Бюджет маржи", tot_b, steps, "Факт маржи", tot_f,
                             f"Бюджет → Факт маржинальной прибыли по сегментам · {plabel}",
                             "Вклад каждого сегмента в отклонение от плана (тыс. USD)")
            insight_box(tot_f - tot_b, steps)

    # Сводная таблица план/факт
    chart_card_open(f"Сводка за период · {period_label}", "")
    table = []
    for key, label in PF_METRICS:
        budget = pl_sum(key, from_m, to_m, "budget")
        if budget == 0:
            continue
        fact_v = pl_sum(key, from_m, to_m, "fact")
        table.append({"Метрика": label, "Факт": fmt_kusd(fact_v), "План": fmt_kusd(budget),
                      "Отклонение": fmt_kusd(fact_v - budget),
                      "Выполнение, %": f"{fact_v / budget * 100:.1f}%"})
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
    chart_card_close()

# ========================= ПЕРИОД К ПЕРИОДУ =========================
with tab_pp:
    dim2 = st.radio("Разрез", ["Статьи P&L", "Сегменты (маржа)"], horizontal=True, key="ao_pp_dim")

    if dim2 == "Статьи P&L":
        c1, c2 = st.columns(2)
        with c1:
            cur_m = st.selectbox("Текущий месяц", list(range(1, 13)),
                                 format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                 index=TARGET_MONTH - 1, key="ao_pp_cur")
        with c2:
            prev_m = st.selectbox("Сравнить с месяцем", list(range(1, 13)),
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                  index=max(0, TARGET_MONTH - 2), key="ao_pp_prev")
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
        insight_box(net_cur - net_prev, steps)
    else:
        if len(FACT_MONTHS) < 2:
            st.warning("Недостаточно фактических месяцев по сегментам.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                sc = st.selectbox("Текущий месяц", FACT_MONTHS, index=len(FACT_MONTHS) - 1,
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_pp_seg_cur")
            with c2:
                sp = st.selectbox("Сравнить с месяцем", FACT_MONTHS, index=len(FACT_MONTHS) - 2,
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_pp_seg_prev")
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
            insight_box(tot_cur - tot_prev, steps)
