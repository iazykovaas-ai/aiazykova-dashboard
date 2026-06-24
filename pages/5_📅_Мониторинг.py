import math
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.kpi import format_money
from components.styles import (CHART_COLORS, PALETTE, apply, chart_card_close,
                               chart_card_open, cuboid_mesh, hero,
                               style_plotly_2d, style_plotly_3d)
from config import (MON_LINE_BLOCKS, MON_METRIC_LABELS, MON_MONTH_TOTAL_COLS,
                    MON_SUMMARY_ROWS, MONTH_NAMES_RU)
from data.sheets_loader import (load_monitoring_raw, mon_line_breakdown,
                                mon_months_available, mon_summary_daily,
                                mon_summary_monthly)

st.set_page_config(page_title="Мониторинг", page_icon="📅", layout="wide")
apply()
render_assistant()

hero("📅 Мониторинг по дате закрытия сделки",
     "Дневная динамика оборота, маржи и сделок · таблица «Мониторинг»")


def fmt_val(v: float, fmt: str) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if fmt == "pct":
        return f"{v * 100:.2f}%"
    if fmt == "int":
        return f"{v:,.0f}".replace(",", " ")
    if fmt == "num":
        return f"{v:.2f}"
    return format_money(v)


rows = load_monitoring_raw()
months = mon_months_available(rows)
if not months:
    st.warning("Не удалось прочитать даты в листе мониторинга.")
    st.stop()

# ===== Выбор месяца и метрики =====
# по умолчанию — последний ЗАКРЫТЫЙ месяц (тот, у которого есть колонка итога)
closed = [m for m in months if m in MON_MONTH_TOTAL_COLS]
default_month = closed[-1] if closed else months[-1]
col_m, col_metric = st.columns([1, 2])
with col_m:
    month = st.selectbox("Месяц", months, index=months.index(default_month),
                         format_func=lambda m: MONTH_NAMES_RU[m - 1])
with col_metric:
    metric_keys = [k for k in MON_METRIC_LABELS if k != "active_clients"]
    metric = st.selectbox("Метрика", metric_keys,
                          format_func=lambda k: MON_METRIC_LABELS[k])

st.caption("ℹ️ Дневной ряд — всё, **включая** Other / Agent / Gold. "
           "Месячные итоги и разбивка по линиям — **без** Other / Agent / Gold "
           "(поэтому сумма по дням больше месячного итога).")

metric_fmt = MON_SUMMARY_ROWS[metric]["fmt"]
month_name = MONTH_NAMES_RU[month - 1]
prev_month = month - 1 if (month - 1) in months else None

# ===== KPI-строка: сводка за месяц =====
KPI_METRICS = ["turnover", "marginal_profit", "marginality", "avg_check", "deals"]
cols = st.columns(len(KPI_METRICS))
for col, key in zip(cols, KPI_METRICS):
    meta = MON_SUMMARY_ROWS[key]
    val = mon_summary_monthly(rows, key, month)
    delta = None
    if (prev_month is not None and meta["fmt"] in {"money", "int"}
            and not math.isnan(val)):
        prev = mon_summary_monthly(rows, key, prev_month)
        if prev and not math.isnan(prev):
            delta = f"{(val / prev - 1) * 100:+.1f}% MoM"
    col.metric(MON_METRIC_LABELS[key], fmt_val(val, meta["fmt"]), delta)

st.markdown("")

# ===== Дневная динамика выбранной метрики =====
chart_card_open(f"Дневная динамика · {MON_METRIC_LABELS[metric]} · {month_name}",
                "по дате закрытия сделки · включая Other / Agent / Gold")
daily = mon_summary_daily(rows, metric, month)
x = [d.strftime("%d.%m") for d, _ in daily]
y = [v for _, v in daily]

if metric_fmt == "pct":
    # маржинальность — линия с заливкой
    fig = go.Figure(go.Scatter(
        x=x, y=[v * 100 for v in y], mode="lines+markers",
        line=dict(color="#36C5F0", width=3),
        marker=dict(size=8, color="#36C5F0"),
        fill="tozeroy", fillcolor="rgba(54,197,240,0.12)",
        hovertemplate="<b>%{x}</b><br>%{y:.2f}%<extra></extra>",
    ))
    style_plotly_2d(fig, height=380)
    fig.update_layout(yaxis=dict(ticksuffix="%"), xaxis=dict(showgrid=False))
else:
    # оборот / прибыль / сделки — столбцы; цвет по знаку для прибыли/переоценки
    colors = ["#2FD9A6" if v >= 0 else "#FF5C7A" for v in y]
    fig = go.Figure(go.Bar(
        x=x, y=y, marker=dict(color=colors, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
        customdata=[fmt_val(v, metric_fmt) for v in y],
    ))
    style_plotly_2d(fig, height=380)
    fig.update_layout(xaxis=dict(showgrid=False))
st.plotly_chart(fig, use_container_width=True,
                config={"displayModeBar": True, "displaylogo": False})
chart_card_close()

# ===== Сравнение месяцев + разбивка по линиям =====
left, right = st.columns([1, 1])

with left:
    chart_card_open(f"Помесячно · {MON_METRIC_LABELS[metric]}",
                    "месячные итоги · без Other / Agent / Gold")
    mmonths = [m for m in months if m in MON_MONTH_TOTAL_COLS]
    pairs = [(m, mon_summary_monthly(rows, metric, m)) for m in mmonths]
    pairs = [(m, v) for m, v in pairs if not math.isnan(v)]
    mvals = [v for _, v in pairs]
    my = [v * 100 for v in mvals] if metric_fmt == "pct" else mvals
    fig = go.Figure(go.Bar(
        x=[MONTH_NAMES_RU[m - 1] for m, _ in pairs], y=my,
        marker=dict(color=[CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(pairs))],
                    line=dict(width=0)),
        text=[fmt_val(v, metric_fmt) for v in mvals],
        textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
        width=0.55,
    ))
    style_plotly_2d(fig, height=380)
    fig.update_layout(xaxis=dict(showgrid=False),
                      yaxis=dict(ticksuffix="%" if metric_fmt == "pct" else ""))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()

with right:
    if metric in MON_LINE_BLOCKS:
        chart_card_open(f"По бизнес-линиям · {month_name}",
                        f"{MON_METRIC_LABELS[metric]} · без Other / Agent / Gold")
        bd = mon_line_breakdown(rows, metric, month)
        items = sorted(bd.items(), key=lambda kv: kv[1])
        ys = [k for k, _ in items]
        xs = [v * 100 for _, v in items] if metric_fmt == "pct" else [v for _, v in items]
        fig = go.Figure(go.Bar(
            x=xs, y=ys, orientation="h",
            marker=dict(color="#7B6FF0", line=dict(width=0)),
            text=[fmt_val(v, metric_fmt) for _, v in items],
            textposition="outside",
            textfont=dict(color=PALETTE["ink"], size=11),
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        ))
        style_plotly_2d(fig, height=380)
        fig.update_layout(xaxis=dict(showticklabels=False, showgrid=True),
                          yaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        chart_card_close()
    else:
        chart_card_open("По бизнес-линиям", "")
        st.caption("Для этой метрики разбивка по линиям в листе не ведётся.")
        chart_card_close()

# ===== Таблица: дни месяца =====
chart_card_open(f"Детализация по дням · {month_name}", "")
tbl = {"Дата": [d.strftime("%d.%m.%Y") for d, _ in daily]}
for key in KPI_METRICS:
    meta = MON_SUMMARY_ROWS[key]
    series = dict(mon_summary_daily(rows, key, month))
    tbl[MON_METRIC_LABELS[key]] = [fmt_val(series.get(d, 0.0), meta["fmt"])
                                   for d, _ in daily]
st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True, height=420)
chart_card_close()
