import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.glossary import PAGE_AGENTS, render_abbr_expander
from components.kpi import format_money
from components.styles import (PALETTE, apply, chart_card_close, chart_card_open,
                               hero, mom_colors, row_separators, style_plotly_2d,
                               wrap_label)
from config import MONTH_NAMES_RU, TARGET_YEAR
from data.sheets_loader import (agent_monthly_series, agents_available_months,
                                agents_dataframe, load_agents_svod_raw)

st.set_page_config(page_title="Доходность агентов", page_icon="🤝", layout="wide")
apply()
render_assistant()

hero(f"🤝 Доходность агентов · {TARGET_YEAR}",
     "Обороты, маржа и комиссии по каждому агенту · лист «Свод по агентам»")

st.info(
    "Здесь сведены сделки в разрезе **агентов** (те, кто приводит клиентов). "
    "**Наша комиссия** — что агентство берёт с клиента; **Комиссия агента** — что мы "
    "выплачиваем агенту (расход, со знаком «−»). **Маржа** — маржинальная прибыль по "
    "сделкам агента, **Маржинальность** = Маржа ÷ Оборот. Проценты за «Весь период» "
    "пересчитаны из сумм за месяцы."
)

render_abbr_expander(PAGE_AGENTS)

rows = load_agents_svod_raw()
months = agents_available_months(rows)          # напр. [1..6]

# ===== Переключатель периода (запоминаем в URL ?am=) =====
# 0 = «Весь период (YTD)», иначе номер месяца.
OPTIONS = [0] + months


def _fmt_period(v: int) -> str:
    return "Весь период (YTD)" if v == 0 else MONTH_NAMES_RU[v - 1]


def _qp_int(key, default):
    try:
        return int(st.query_params.get(key, default))
    except (TypeError, ValueError):
        return default


st.markdown("##### 🗓️ Период")
if "agents_period" not in st.session_state:
    _saved = _qp_int("am", months[-1] if months else 0)
    st.session_state["agents_period"] = _saved if _saved in OPTIONS else (months[-1] if months else 0)
period = st.selectbox("Период", OPTIONS, format_func=_fmt_period,
                      key="agents_period", label_visibility="collapsed")
st.query_params["am"] = str(period)
period_label = _fmt_period(period)

# ===== Данные за период =====
df = agents_dataframe(rows, period)
# «Активные» — где был оборот, маржа или сделки
mask = (df["turnover"] != 0) | (df["margin"] != 0) | (df["deals"] != 0)
df = df[mask].copy()
df["payout"] = -df["agent_fee"]          # выплата агенту (положительная)
df = df.sort_values("margin", ascending=False).reset_index(drop=True)


def _m(v: float) -> str:
    """USD с пробелами-разрядами (для таблицы; $ безопасен в dataframe)."""
    return f"$ {v:,.0f}".replace(",", " ")


# ===== KPI =====
tot_turn = df["turnover"].sum()
tot_marg = df["margin"].sum()
tot_our = df["our_fee"].sum()
tot_pay = df["payout"].sum()
tot_deals = int(df["deals"].sum())
n_agents = len(df)
avg_margness = tot_marg / tot_turn if tot_turn else 0.0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Оборот", format_money(tot_turn))
c2.metric("Маржа", format_money(tot_marg), delta=f"{avg_margness * 100:.2f}% маржинальность")
c3.metric("Наша комиссия", format_money(tot_our))
c4.metric("Выплачено агентам", format_money(tot_pay))
c5.metric("Активных агентов", f"{n_agents}")
c6.metric("Сделок", f"{tot_deals}")

st.caption(f"Период: **{period_label}**. Показаны агенты с активностью в периоде.")
st.markdown("")

# ===== Топ агентов по выбранной метрике =====
METRIC_CHOICES = {
    "Маржа, USD": ("margin", "money", "#2FD9A6"),
    "Оборот, USD": ("turnover", "money", "#36C5F0"),
    "Наша комиссия, USD": ("our_fee", "money", "#8B7BF0"),
    "Выплачено агенту, USD": ("payout", "money", "#F5B544"),
    "Кол-во сделок": ("deals", "int", "#E94FA1"),
}
chart_card_open("🏆 Рейтинг агентов", "отсортировано по выбранной метрике · тыс. USD, кроме сделок")
metric_name = st.radio("Метрика", list(METRIC_CHOICES), horizontal=True,
                       key="agents_rank_metric", label_visibility="collapsed")
col_key, fmt, base_color = METRIC_CHOICES[metric_name]

top = df[df[col_key] != 0].sort_values(col_key, ascending=True)
if top.empty:
    st.caption("Нет данных за период.")
else:
    is_money = fmt == "money"
    xvals = top[col_key] / 1000 if is_money else top[col_key]
    if is_money:
        texts = [f"{v/1000:,.0f}".replace(",", " ") for v in top[col_key]]
        hover = "<b>%{y}</b><br>" + metric_name + ": %{customdata:,.0f}<extra></extra>"
    else:
        texts = [f"{int(v)}" for v in top[col_key]]
        hover = "<b>%{y}</b><br>" + metric_name + ": %{x}<extra></extra>"
    colors = [base_color if v >= 0 else PALETTE["danger"] for v in top[col_key]]
    fig = go.Figure(go.Bar(
        x=xvals, y=[wrap_label(a, 16) for a in top["Агент"]], orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=texts, textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        customdata=top[col_key],
        hovertemplate=hover,
    ))
    style_plotly_2d(fig, height=max(360, 26 * len(top)))
    fig.update_layout(
        xaxis=dict(showgrid=True, showticklabels=True, zeroline=True,
                   tickfont=dict(size=11)),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        shapes=row_separators(len(top)),
        margin=dict(l=10, r=60, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== Оборот × Маржинальность (пузыри) =====
chart_card_open("💹 Оборот и маржинальность",
                "размер пузыря = |Маржа|; выше нуля — прибыльно, ниже — убыточно")
sc = df[df["turnover"] > 0].copy()
if sc.empty:
    st.caption("Нет данных за период.")
else:
    sizeref = 2.0 * sc["margin"].abs().max() / (44.0 ** 2) if sc["margin"].abs().max() else 1
    pt_colors = [PALETTE["success"] if v >= 0 else PALETTE["danger"] for v in sc["marginality"]]
    # подписи — крупнейшим по обороту, чтобы не загромождать
    thr = sc["turnover"].quantile(0.6)
    labels = [a if t >= thr else "" for a, t in zip(sc["Агент"], sc["turnover"])]
    fig = go.Figure(go.Scatter(
        x=sc["turnover"], y=sc["marginality"] * 100,
        mode="markers+text",
        text=labels, textposition="top center",
        textfont=dict(color=PALETTE["muted"], size=10),
        marker=dict(size=sc["margin"].abs(), sizemode="area", sizeref=sizeref,
                    sizemin=6, color=pt_colors, line=dict(width=1, color="rgba(255,255,255,0.35)"),
                    opacity=0.85),
        customdata=sc[["margin", "deals"]],
        hovertemplate=("<b>%{text}</b><br>Оборот: %{x:,.0f} $<br>"
                       "Маржинальность: %{y:.2f}%<br>Маржа: %{customdata[0]:,.0f} $<br>"
                       "Сделок: %{customdata[1]}<extra></extra>"),
    ))
    style_plotly_2d(fig, height=440)
    fig.update_layout(
        xaxis=dict(title="Оборот, USD (лог. шкала)", type="log", showgrid=True),
        yaxis=dict(title="Маржинальность, %", zeroline=True,
                   zerolinecolor="rgba(255,92,122,0.55)", zerolinewidth=1),
        margin=dict(l=10, r=20, t=10, b=40),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== Детальная таблица =====
chart_card_open("📋 Детализация по агентам", period_label)
tbl = df[["Агент", "turnover", "deals", "margin", "marginality", "client_rate",
          "our_fee", "agent_fee_pct", "agent_fee"]].copy()
tbl.columns = ["Агент", "Оборот", "Сделок", "Маржа", "Маржинальность",
               "Тариф клиента", "Наша комиссия", "Комиссия агента, %", "Комиссия агенту"]


def _color_val(v):
    if v > 0:
        return "color: #2FD9A6;"
    if v < 0:
        return "color: #FF5C7A;"
    return "color: #8A90B8;"


styler = (
    tbl.style
    .format({
        "Оборот": _m, "Маржа": _m, "Наша комиссия": _m, "Комиссия агенту": _m,
        "Сделок": "{:.0f}",
        "Маржинальность": lambda v: f"{v*100:.2f}%",
        "Тариф клиента": lambda v: f"{v*100:.2f}%",
        "Комиссия агента, %": lambda v: f"{v*100:.2f}%",
    })
    .map(_color_val, subset=["Маржа", "Маржинальность"])
)
st.dataframe(styler, use_container_width=True, hide_index=True,
             height=min(560, 44 + 35 * len(tbl)))
chart_card_close()

# ===== Динамика по месяцам для одного агента =====
chart_card_open("📈 Динамика агента по месяцам", "оборот (столбцы) и маржа (линия) · тыс. USD")
agent_names = df["Агент"].tolist()
if agent_names:
    who = st.selectbox("Агент", agent_names, key="agents_dyn_who")
    turn_s = agent_monthly_series(rows, who, "turnover")
    marg_s = agent_monthly_series(rows, who, "margin")
    xs = [MONTH_NAMES_RU[m - 1] for m in months]
    turn_k = [turn_s[m - 1] / 1000 for m in months]
    marg_k = [marg_s[m - 1] / 1000 for m in months]
    bar_colors, _ = mom_colors(turn_k, base_color="#36C5F0")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=xs, y=turn_k, name="Оборот",
        marker=dict(color=bar_colors, line=dict(width=0)),
        text=[f"{v:,.0f}".replace(",", " ") for v in turn_k],
        textposition="inside", insidetextanchor="middle",
        textfont=dict(color="#0A0E20", size=11), textangle=0,
        hovertemplate="<b>%{x}</b><br>Оборот: %{y:,.0f} тыс. $<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=xs, y=marg_k, name="Маржа", mode="lines+markers+text",
        line=dict(color="#F5B544", width=3), marker=dict(size=8, color="#F5B544"),
        text=[f"{v:,.0f}".replace(",", " ") for v in marg_k],
        textposition="top center", textfont=dict(color="#F5B544", size=11),
        hovertemplate="<b>%{x}</b><br>Маржа: %{y:,.0f} тыс. $<extra></extra>",
    ), secondary_y=True)
    style_plotly_2d(fig, height=380)
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Оборот, тыс. $", showgrid=True),
        yaxis2=dict(title="Маржа, тыс. $", showgrid=False, zeroline=True,
                    zerolinecolor="rgba(255,92,122,0.5)"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()
