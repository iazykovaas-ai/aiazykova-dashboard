import math
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.kpi import format_money
from components.styles import (CHART_COLORS, PALETTE, apply, chart_card_close, mom_colors,
                               chart_card_open, col_separators, cuboid_mesh, hero,
                               row_separators, style_plotly_2d, style_plotly_3d)
from config import (MON_LINE_BLOCKS, MON_LINES, MON_METRIC_LABELS, MON_MONTH_TOTAL_COLS,
                    MON_SUMMARY_ROWS, MONTH_NAMES_RU)
from data.sheets_loader import (load_monitoring_raw, mon_line_breakdown,
                                mon_line_daily, mon_months_available,
                                mon_summary_daily, mon_summary_monthly)

st.set_page_config(page_title="Мониторинг", page_icon="📅", layout="wide")
apply()
render_assistant()

hero("📅 Мониторинг по дате закрытия сделки",
     "Дневная динамика оборота, маржи и сделок · таблица «Мониторинг»")

st.info("ℹ️ В данной вкладке показатели считаются **от даты исполнения обязательств с нашей "
        "стороны** — то есть когда мы произвели платёж по сделке (а не от фактической даты каждой "
        "транзакции). Поэтому возможны явные расхождения с данными в разделах **«Финансовые "
        "результаты»** и **«Анализ отклонений»**.")


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

metric_fmt = MON_SUMMARY_ROWS[metric]["fmt"]
month_name = MONTH_NAMES_RU[month - 1]
prev_month = month - 1 if (month - 1) in months else None

# ===== KPI-строка: сводка за месяц =====
st.markdown("##### 📦 Сводка за месяц")
st.caption("месячные итоги · **без** Other / Agent / Gold")
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
                "по дням · включая Other / Agent / Gold (сумма по дням > месячного итога)")
daily = mon_summary_daily(rows, metric, month)
x = [d.strftime("%d.%m") for d, _ in daily]
y = [v for _, v in daily]


def _bar_label(v: float) -> str:
    """Подпись над столбцом: деньги — в тысячах ($…k), целые — как есть."""
    if metric_fmt == "money":
        return f"{v / 1000:,.0f}".replace(",", " ") + "k"
    if metric_fmt == "int":
        return f"{v:,.0f}".replace(",", " ")
    return fmt_val(v, metric_fmt)


if metric_fmt == "pct":
    # маржинальность — линия с заливкой
    fig = go.Figure(go.Scatter(
        x=x, y=[v * 100 for v in y], mode="lines+markers",
        line=dict(color="#36C5F0", width=3),
        marker=dict(size=8, color="#36C5F0"),
        fill="tozeroy", fillcolor="rgba(54,197,240,0.12)",
        hovertemplate="<b>%{x}</b><br>%{y:.2f}%<extra></extra>",
    ))
    style_plotly_2d(fig, height=400)
    fig.update_layout(yaxis=dict(ticksuffix="%"),
                      xaxis=dict(showgrid=False, type="category", tickangle=-45))
else:
    # оборот / прибыль / сделки — столбцы; цвет по знаку для прибыли/переоценки
    colors = ["#2FD9A6" if v >= 0 else "#FF5C7A" for v in y]
    fig = go.Figure(go.Bar(
        x=x, y=y, marker=dict(color=colors, line=dict(width=0)),
        text=[_bar_label(v) for v in y],
        textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=10),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
        customdata=[fmt_val(v, metric_fmt) for v in y],
    ))
    style_plotly_2d(fig, height=420)
    fig.update_layout(xaxis=dict(showgrid=False, type="category", tickangle=-45))
st.plotly_chart(fig, use_container_width=True,
                config={"displayModeBar": True, "displaylogo": False})
chart_card_close()

# ===== Сравнение месяцев + разбивка по линиям =====
left, right = st.columns([2, 3])   # левый (помесячно) уже, правый (по линиям) шире

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
        marker=dict(color=mom_colors(mvals, "#8B7BF0")[0],
                    line=dict(color="rgba(255,255,255,0.12)", width=1)),
        text=[fmt_val(v, metric_fmt) for v in mvals],
        textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
        width=0.55,
    ))
    style_plotly_2d(fig, height=380)
    fig.update_layout(xaxis=dict(showgrid=False),
                      yaxis=dict(ticksuffix="%" if metric_fmt == "pct" else ""),
                      shapes=col_separators(len(pairs)))
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
        # запас справа и СЛЕВА (для отрицательных, напр. Export), чтобы подписи не обрезались
        _xmax = max(xs) if xs else 0
        _xmin = min(xs) if xs else 0
        _left = _xmin * 1.30 if _xmin < 0 else 0
        fig.update_layout(xaxis=dict(showticklabels=False, showgrid=True,
                                     range=[_left, _xmax * 1.22]),
                          yaxis=dict(showgrid=False, tickfont=dict(size=12)),
                          shapes=row_separators(len(items)))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        chart_card_close()
    else:
        chart_card_open("По бизнес-линиям", "")
        st.caption("Для этой метрики разбивка по линиям в листе не ведётся.")
        chart_card_close()

# ===== Таблица: дни месяца =====
chart_card_open(f"Детализация по дням · {month_name}",
                "по дням · включая Other / Agent / Gold")
tbl = {"Дата": [d.strftime("%d.%m.%Y") for d, _ in daily]}
for key in KPI_METRICS:
    meta = MON_SUMMARY_ROWS[key]
    series = dict(mon_summary_daily(rows, key, month))
    tbl[MON_METRIC_LABELS[key]] = [fmt_val(series.get(d, 0.0), meta["fmt"])
                                   for d, _ in daily]
st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True, height=420)
chart_card_close()


def _k(v: float) -> str:
    return f"{v / 1000:,.0f}".replace(",", " ") + "k"


mm = [m for m in months if m in MON_MONTH_TOTAL_COLS]
cnames = [MONTH_NAMES_RU[m - 1] for m in mm]   # подписи месяцев для тепловой карты

# ===== Комбо: оборот (бары) + маржинальность (линия) по ДНЯМ =====
combo_seg = st.selectbox("Сегмент для графика по дням", ["Все сегменты"] + MON_LINES,
                         key="mon_combo_seg")
if combo_seg == "Все сегменты":
    dturn = mon_summary_daily(rows, "turnover", month)
    dmarg = dict(mon_summary_daily(rows, "marginality", month))
    _seg_note = "все сегменты · включая Other / Agent / Gold"
else:
    dturn = mon_line_daily(rows, "turnover", combo_seg, month)
    dmarg = dict(mon_line_daily(rows, "marginality", combo_seg, month))
    _seg_note = f"сегмент: {combo_seg} · без Other / Agent / Gold"
chart_card_open(f"Оборот и маржинальность по дням · {month_name}",
                f"бары — оборот ($), линия — маржинальность (%) · {_seg_note}")
dx = [d.strftime("%d.%m") for d, _ in dturn]
dt = [v for _, v in dturn]
dg = [dmarg.get(d, 0.0) * 100 for d, _ in dturn]
dcfig = make_subplots(specs=[[{"secondary_y": True}]])
# цвет оборота по динамике ко вчера: рост — зелёный, спад — красный, яркость ~ силе изменения
_dcolors = mom_colors(dt, "#36C5F0")[0]
dcfig.add_trace(go.Bar(
    x=dx, y=dt, name="Оборот",
    marker=dict(color=_dcolors, line=dict(width=0)),
    # короткая подпись в млн (4,9M) — влезает горизонтально; точное значение (k) — в подсказке
    text=[f"{v / 1e6:.1f}".replace(".", ",") + "M" for v in dt],
    textposition="outside", textangle=0,
    textfont=dict(color=PALETTE["ink"], size=10), cliponaxis=False,
    customdata=[_k(v) for v in dt],
    hovertemplate="<b>%{x}</b><br>Оборот: %{customdata}<extra></extra>",
), secondary_y=False)
dcfig.add_trace(go.Scatter(
    x=dx, y=dg, name="Маржинальность",
    mode="lines+markers+text", line=dict(color="#F5B544", width=2),
    marker=dict(size=7),
    text=[f"{v:.2f}".replace(".", ",") + "%" for v in dg], textposition="top center",
    textfont=dict(color="#F5B544", size=10),
    hovertemplate="<b>%{x}</b><br>Маржинальность: %{y:.2f}%<extra></extra>",
), secondary_y=True)
style_plotly_2d(dcfig, height=520)
dcfig.update_layout(legend=dict(orientation="h", y=1.12), bargap=0.3,
                    xaxis=dict(showgrid=False, type="category", tickangle=-45))
# запас сверху → бары короче, подписи влезают; метки оси — авто (k/M под масштаб месяца)
dcfig.update_yaxes(title_text="Оборот, $", tickformat="~s", showgrid=True,
                   range=[0, (max(dt) if dt else 1) * 1.25], secondary_y=False)
# ось маржи: пускаем ниже 0, если есть отрицательные дни, и рисуем нулевую линию
_gmin = min(dg) if dg else 0
_glow = _gmin * 1.2 if _gmin < 0 else 0
dcfig.update_yaxes(title_text="Маржа, %", ticksuffix="%", showgrid=False,
                   range=[_glow, (max(dg) if dg else 1) * 1.3],
                   zeroline=True, zerolinecolor="rgba(255,255,255,0.25)",
                   zerolinewidth=1, secondary_y=True)
st.plotly_chart(dcfig, use_container_width=True, config={"displayModeBar": False})
st.caption("🟢 рост оборота ко вчера · 🔴 спад · насыщеннее = сильнее изменение. "
           "Подписи: оборот — над столбцами, маржинальность — над точками. "
           "Тесно? Откройте график на весь экран кнопкой ⛶ сверху справа.")
chart_card_close()

# ===== Тепловая карта: бизнес-линии × месяцы (оборот) =====
chart_card_open("Тепловая карта оборота · линии × месяцы",
                "цвет — величина оборота, $ (без Other / Agent / Gold)")
hb = {m: mon_line_breakdown(rows, "turnover", m) for m in mm}
z = [[hb[m].get(line, 0.0) for m in mm] for line in MON_LINES]
ztext = [[_k(hb[m].get(line, 0.0)) for m in mm] for line in MON_LINES]
hfig = go.Figure(go.Heatmap(
    z=z, x=cnames, y=MON_LINES,
    colorscale=[[0, "#0E1430"], [0.5, "#27506E"], [1, "#2FD9A6"]],
    text=ztext, texttemplate="%{text}", textfont=dict(size=10, color="#E8EAF6"),
    hovertemplate="<b>%{y}</b> · %{x}<br>%{text}<extra></extra>",
    colorbar=dict(title="$", tickfont=dict(color="#8A90B8")),
))
hfig.update_layout(height=460, paper_bgcolor="rgba(0,0,0,0)",
                   plot_bgcolor="rgba(0,0,0,0)",
                   font=dict(color=PALETTE["ink"], size=11),
                   margin=dict(l=10, r=10, t=10, b=10),
                   yaxis=dict(autorange="reversed"))
st.plotly_chart(hfig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== Таблица-светофор по сегментам =====
seg_turn = mon_line_breakdown(rows, "turnover", month)
seg_marg = mon_line_breakdown(rows, "marginality", month)
# База сравнения — средняя маржинальность за месяц. Если в листе её нет/0
# (месяц не закрыт) — берём среднюю по сегментам, иначе светофор «весь зелёный».
avg_marg = mon_summary_monthly(rows, "marginality", month)
_base_note = "средняя за месяц"
if math.isnan(avg_marg) or avg_marg <= 0:
    vals = [v for v in seg_marg.values() if v]
    avg_marg = sum(vals) / len(vals) if vals else 0.0
    _base_note = "средняя по сегментам (в листе средняя за месяц пустая)"
chart_card_open(f"Светофор по сегментам · {month_name}",
                "маржинальность сегмента к средней за месяц · без Other / Agent / Gold")
st.caption(
    f"🟢 ≥ средней  ·  🟡 от ½ до средней  ·  🔴 ниже ½ средней.  "
    f"База сравнения: **{avg_marg * 100:.2f}%** ({_base_note}).")
seg_rows = []
for line in MON_LINES:
    mg = seg_marg.get(line, 0.0)
    if mg >= avg_marg:
        light = "🟢"
    elif mg >= avg_marg * 0.5:
        light = "🟡"
    else:
        light = "🔴"
    seg_rows.append({"Сегмент": line, "Оборот": _k(seg_turn.get(line, 0.0)),
                     "Маржинальность": f"{mg * 100:.2f}%", "Статус": light})
st.dataframe(pd.DataFrame(seg_rows), use_container_width=True, hide_index=True, height=430)
chart_card_close()
