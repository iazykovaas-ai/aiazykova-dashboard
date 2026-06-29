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
from config import MONTH_NAMES_RU, MONTH_NAMES_SHORT, TARGET_MONTH, TARGET_YEAR
from data.sheets_loader import load_pl_global_raw, pl_value

st.set_page_config(page_title="План vs Факт", page_icon="🎯", layout="wide")
apply()
render_assistant()

hero("🎯 План vs Факт",
     "Факт против бюджета по PL GLOBAL · выберите период (месяц или диапазон)")

rows = load_pl_global_raw()

# Метрики, по которым в PL GLOBAL заполнен бюджет (выручка/прямые расходы — пусто, не показываем).
PF_METRICS = [
    ("turnover",          "Оборот"),
    ("gross_profit",      "Маржинальная прибыль"),
    ("opex",              "OPEX"),
    ("net_profit",        "Чистая прибыль"),
]
KPI_KEYS = ["turnover", "gross_profit", "net_profit"]   # для верхних карточек


def pl_sum(metric, m_from, m_to, source):
    return sum(pl_value(rows, metric, m, source) for m in range(m_from, m_to + 1))


# ===== Переключатель периода =====
st.markdown("##### 📅 Период")
c_from, c_to = st.columns(2)
with c_from:
    from_m = st.selectbox("С месяца", list(range(1, 13)),
                          format_func=lambda x: MONTH_NAMES_RU[x - 1], index=0, key="pf_from")
with c_to:
    to_m = st.selectbox("По месяц", list(range(1, 13)),
                        format_func=lambda x: MONTH_NAMES_RU[x - 1],
                        index=TARGET_MONTH - 1, key="pf_to")
if from_m > to_m:
    from_m, to_m = to_m, from_m
period_label = (f"{MONTH_NAMES_RU[from_m - 1]} {TARGET_YEAR}" if from_m == to_m
                else f"{MONTH_NAMES_RU[from_m - 1]} — {MONTH_NAMES_RU[to_m - 1]} {TARGET_YEAR}")

# ===== KPI: факт + % к плану за период =====
cols = st.columns(len(KPI_KEYS))
labels = dict(PF_METRICS)
for col, key in zip(cols, KPI_KEYS):
    fact = pl_sum(key, from_m, to_m, "fact")
    budget = pl_sum(key, from_m, to_m, "budget")
    done = fact / budget * 100 if budget else None
    delta = f"{done - 100:+.1f}% к плану" if done is not None else "нет плана"
    col.metric(labels[key], fmt_kusd(fact), delta)

st.markdown("")

# ===== План vs Факт по месяцам (выбранная метрика) =====
m_sel = st.selectbox("Метрика для графика", KPI_KEYS,
                     format_func=lambda k: labels[k], key="pf_metric")
chart_card_open(f"План vs Факт по месяцам · {labels[m_sel]} · {period_label}", "тыс. USD")
months = list(range(from_m, to_m + 1))
plan = [pl_value(rows, m_sel, m, "budget") for m in months]
fact = [pl_value(rows, m_sel, m, "fact") for m in months]
xnames = [MONTH_NAMES_SHORT[m - 1] for m in months]
fig = go.Figure()
fig.add_trace(go.Bar(
    x=xnames, y=plan, name="План", marker=dict(color="#8B7BF0"),
    text=[fmt_kusd(v) for v in plan], textposition="outside",
    textfont=dict(color=PALETTE["ink"], size=10),
    hovertemplate="<b>%{x}</b><br>План: %{text}<extra></extra>",
))
fig.add_trace(go.Bar(
    x=xnames, y=fact, name="Факт",
    marker=dict(color=["#2FD9A6" if f >= p else "#FF5C7A" for f, p in zip(fact, plan)]),
    text=[fmt_kusd(v) for v in fact], textposition="outside",
    textfont=dict(color=PALETTE["ink"], size=10),
    hovertemplate="<b>%{x}</b><br>Факт: %{text}<extra></extra>",
))
style_plotly_2d(fig, height=420)
fig.update_layout(barmode="group", xaxis=dict(showgrid=False),
                  legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== % выполнения плана по месяцам =====
chart_card_open(f"Выполнение плана по месяцам · {labels[m_sel]}", "Факт / План, %")
done_m = [fact[i] / plan[i] * 100 if plan[i] else 0 for i in range(len(months))]
# оттенки: выше 100% — зелёные, ниже — красные; насыщенность ~ отклонению от плана
_dev = [v - 100 for v in done_m]
_maxd = max((abs(d) for d in _dev), default=1) or 1
colors = [(f"rgba(47,217,166,{0.4 + 0.6 * min(abs(d) / _maxd, 1):.2f})" if v >= 100
           else f"rgba(255,92,122,{0.4 + 0.6 * min(abs(d) / _maxd, 1):.2f})")
          for v, d in zip(done_m, _dev)]
fig = go.Figure(go.Bar(
    x=xnames, y=done_m, marker=dict(color=colors),
    text=[f"{v:.0f}%" if v else "—" for v in done_m], textposition="outside",
    textfont=dict(color=PALETTE["ink"], size=12),
    hovertemplate="<b>%{x}</b><br>Выполнение: %{y:.1f}%<extra></extra>", width=0.5,
))
fig.add_hline(y=100, line=dict(color=PALETTE["muted"], width=1, dash="dash"),
              annotation_text="100%", annotation_position="right",
              annotation_font_color=PALETTE["muted"])
style_plotly_2d(fig, height=320)
fig.update_layout(yaxis=dict(ticksuffix="%"), xaxis=dict(showgrid=False))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== Таблица: план/факт/отклонение по метрикам за период =====
chart_card_open(f"Сводка за период · {period_label}", "")
table = []
for key, label in PF_METRICS:
    budget = pl_sum(key, from_m, to_m, "budget")
    if budget == 0:
        continue
    fact_v = pl_sum(key, from_m, to_m, "fact")
    table.append({
        "Метрика": label,
        "Факт": fmt_kusd(fact_v),
        "План": fmt_kusd(budget),
        "Отклонение": fmt_kusd(fact_v - budget),
        "Выполнение, %": f"{fact_v / budget * 100:.1f}%",
    })
st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
chart_card_close()
