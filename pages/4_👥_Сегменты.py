import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.format import (bg_diverging as _bg_marg, md_escape as _md,
                               num_spaced as _money_txt, qp_int as _qp_int,
                               usd_spaced as _mfmt)
from components.glossary import PAGE_SEG, render_abbr_expander
from components.kpi import format_money
from components.styles import (PALETTE, apply, chart_card_close, chart_card_open,
                               col_separators, hero, row_separators, style_plotly_2d,
                               wrap_label)
from config import MONTH_NAMES_RU
from data.sheets_loader import (bb_available_months, bb_monthly_totals,
                                bb_segment_df, load_business_block_raw)

st.set_page_config(page_title="Сегменты", page_icon="👥", layout="wide")
apply()
render_assistant()

hero("👥 Сегменты", "Бизнес-линии: оборот, маржа, маржинальность, клиенты · лист «Бизнес-блок»")

st.info("Данные помесячные из листа **«Бизнес-блок»**. Исключены **Other / Agent / Gold**. "
        "Оборот и средний чек в источнике — в тыс. USD; здесь показаны в долларах. "
        "Маржинальность = Маржинальная прибыль ÷ Оборот.")

render_abbr_expander(PAGE_SEG)

rows = load_business_block_raw()

# ===== Год и месяц (запоминаем в URL ?sy=&sm=) =====
col_y, col_m = st.columns([1, 2])
with col_y:
    if "seg_year" not in st.session_state:
        _y = _qp_int("sy", 2026)
        st.session_state["seg_year"] = _y if _y in (2025, 2026) else 2026
    year = st.radio("Год", [2025, 2026], horizontal=True, key="seg_year")
st.query_params["sy"] = str(year)

months = bb_available_months(rows, year)
if not months:
    st.warning("Нет данных за выбранный год.")
    st.stop()

# Дефолт — последний ЗАВЕРШЁННЫЙ месяц (текущий календарный месяц ещё идёт → берём предыдущий)
today = dt.date.today()
closed = [m for m in months if not (year == today.year and m >= today.month)]
default_month = closed[-1] if closed else months[-1]
with col_m:
    if "seg_month" not in st.session_state:
        _m = _qp_int("sm", default_month)
        st.session_state["seg_month"] = _m if _m in months else default_month
    elif st.session_state["seg_month"] not in months:
        st.session_state["seg_month"] = default_month
    month = st.selectbox("Месяц", months, format_func=lambda m: MONTH_NAMES_RU[m - 1],
                         key="seg_month")
st.query_params["sm"] = str(month)

period_label = f"{MONTH_NAMES_RU[month - 1]} {year}"
is_partial = (year == today.year and month == today.month)
if is_partial:
    st.caption(f"⚠️ **{MONTH_NAMES_RU[month - 1]}** ещё не завершён — данные неполные.")

# ===== Данные за месяц =====
df = bb_segment_df(rows, year, month)
df = df[(df["turnover"] != 0) | (df["clients"] != 0) | (df["deals"] != 0)].copy()
df["turnover_usd"] = df["turnover"] * 1000            # оборот в USD
df["marg_per_client"] = [(mp / c if c else 0.0) for mp, c in zip(df["marg_profit"], df["clients"])]
df = df.sort_values("turnover_usd", ascending=False).reset_index(drop=True)

t_turn = df["turnover_usd"].sum()
t_marg = df["marg_profit"].sum()
t_clients = int(df["clients"].sum())
t_deals = int(df["deals"].sum())
t_margness = t_marg / t_turn if t_turn else 0.0
t_check = t_turn / t_deals if t_deals else 0.0

# ===== KPI =====
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Активные клиенты", f"{t_clients}")
c2.metric("Оборот", format_money(t_turn))
c3.metric("Маржинальная прибыль", format_money(t_marg))
c4.metric("Маржинальность", f"{t_margness * 100:.2f}%".replace(".", ","))
c5.metric("Сделок", f"{t_deals}")
c6.metric("Средний чек", format_money(t_check))
st.caption(f"Период: **{period_label}** · {len(df)} бизнес-линий с активностью")
st.markdown("")


def _bar_h(frame, valcol, colorfn, textfn, xtitle, hovertail):
    """Горизонтальные бары по сегментам (общий помощник)."""
    fr = frame.sort_values(valcol, ascending=True)
    fig = go.Figure(go.Bar(
        x=fr[valcol], y=[wrap_label(a, 14) for a in fr["line_ru"]], orientation="h",
        marker=dict(color=[colorfn(v) for v in fr[valcol]], line=dict(width=0)),
        text=[textfn(v) for v in fr[valcol]], textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=11),
        customdata=fr[["turnover_usd", "marg_profit", "clients"]],
        hovertemplate="<b>%{y}</b><br>" + hovertail + "<extra></extra>",
    ))
    style_plotly_2d(fig, height=max(340, 30 * len(fr)))
    fig.update_layout(
        xaxis=dict(title=xtitle, showgrid=True, zeroline=True, showticklabels=False,
                   zerolinecolor="rgba(255,92,122,0.55)"),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        shapes=row_separators(len(fr)), margin=dict(l=10, r=90, t=10, b=10),
    )
    return fig


_green = lambda v: PALETTE["success"] if v >= 0 else PALETTE["danger"]

# ===== 1. Оборот по сегментам =====
chart_card_open("💰 Оборот по сегментам", f"{period_label} · USD")
fig = _bar_h(df, "turnover_usd", lambda v: "#36C5F0", _money_txt, "Оборот, USD",
             "Оборот: %{x:,.0f} $<br>Маржа: %{customdata[1]:,.0f} $<br>Клиентов: %{customdata[2]}")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
# мини-вывод
_top = df.iloc[0]
_top3_share = df["turnover_usd"].head(3).sum() / t_turn * 100 if t_turn else 0
st.markdown(_md(
    f"🔎 **Вывод.** Лидер по обороту — **{_top['line_ru']}** "
    f"({format_money(_top['turnover_usd'])}, {_top['turnover_usd']/t_turn*100:.0f}% оборота). "
    f"Топ-3 линии дают **{_top3_share:.0f}%** всего оборота."
))
chart_card_close()

# ===== 2. Маржинальная прибыль по сегментам =====
chart_card_open("📈 Маржинальная прибыль по сегментам", f"{period_label} · USD")
fig = _bar_h(df, "marg_profit", _green, _money_txt, "Маржинальная прибыль, USD",
             "Маржа: %{x:,.0f} $<br>Оборот: %{customdata[0]:,.0f} $<br>Клиентов: %{customdata[2]}")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
_prof = df[df["marg_profit"] > 0].sort_values("marg_profit", ascending=False)
_loss = df[df["marg_profit"] < 0].sort_values("marg_profit")
_leader = _prof.iloc[0] if len(_prof) else None
loss_txt = (f" В минусе: **{', '.join(_loss['line_ru'])}** "
            f"(суммарно {format_money(_loss['marg_profit'].sum())})." if len(_loss) else
            " Убыточных линий нет.")
st.markdown(_md(
    (f"🔎 **Вывод.** Больше всего маржи приносит **{_leader['line_ru']}** "
     f"({format_money(_leader['marg_profit'])})." if _leader is not None else
     "🔎 **Вывод.** Прибыльных линий нет.") + loss_txt
))
chart_card_close()

# ===== 3. Маржинальность по сегментам =====
chart_card_open("🎯 Маржинальность по сегментам",
                f"{period_label} · % от оборота · пунктир — средняя по компании")
fr = df.sort_values("marginality", ascending=True)
figm = go.Figure(go.Bar(
    x=fr["marginality"] * 100, y=[wrap_label(a, 14) for a in fr["line_ru"]], orientation="h",
    marker=dict(color=[_green(v) for v in fr["marginality"]], line=dict(width=0)),
    text=[f"{v*100:.2f}%".replace(".", ",") for v in fr["marginality"]],
    textposition="outside", textfont=dict(color=PALETTE["ink"], size=11),
    hovertemplate="<b>%{y}</b><br>Маржинальность: %{x:.2f}%<extra></extra>",
))
style_plotly_2d(figm, height=max(340, 30 * len(fr)))
figm.update_layout(
    xaxis=dict(title="Маржинальность, %", showgrid=True, zeroline=True, ticksuffix="%",
               zerolinecolor="rgba(255,92,122,0.55)"),
    yaxis=dict(showgrid=False, tickfont=dict(size=12)),
    shapes=row_separators(len(fr)) + [dict(
        type="line", xref="x", yref="paper", x0=t_margness * 100, x1=t_margness * 100,
        y0=0, y1=1, line=dict(color="#F5B544", width=1.5, dash="dash"))],
    margin=dict(l=10, r=70, t=10, b=30),
)
st.plotly_chart(figm, width="stretch", config={"displayModeBar": False})
_best = df.loc[df["marginality"].idxmax()]
_worst = df.loc[df["marginality"].idxmin()]
st.markdown(_md(
    f"🔎 **Вывод.** Средняя по компании — **{t_margness*100:.2f}%**. "
    f"Выше всех **{_best['line_ru']}** ({_best['marginality']*100:.2f}%), "
    f"ниже всех **{_worst['line_ru']}** ({_worst['marginality']*100:.2f}%)."
))
chart_card_close()

# ===== 4. Динамика по месяцам (оборот + маржинальность) =====
chart_card_open("📅 Динамика по месяцам", f"{year} · оборот (столбцы) и маржинальность (линия)")
tot = bb_monthly_totals(rows, year, months)
xs = [MONTH_NAMES_RU[m - 1] for m in months]
turn_m = [t * 1000 for t in tot["turnover"]]
marg_m = [v * 100 for v in tot["marginality"]]
figd = make_subplots(specs=[[{"secondary_y": True}]])
figd.add_trace(go.Bar(
    x=xs, y=turn_m, name="Оборот", marker_color="#36C5F0",
    text=[format_money(v) for v in turn_m], textposition="outside",
    textfont=dict(color="#36C5F0", size=11),
    hovertemplate="<b>%{x}</b><br>Оборот: %{y:,.0f} $<extra></extra>",
), secondary_y=False)
figd.add_trace(go.Scatter(
    x=xs, y=marg_m, name="Маржинальность", mode="lines+markers+text",
    line=dict(color="#F5B544", width=3), marker=dict(size=8, color="#F5B544"),
    text=[f"{v:.2f}%".replace(".", ",") for v in marg_m], textposition="top center",
    textfont=dict(color="#F5B544", size=11),
    hovertemplate="<b>%{x}</b><br>Маржинальность: %{y:.2f}%<extra></extra>",
), secondary_y=True)
style_plotly_2d(figd, height=380)
figd.update_layout(
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="Оборот, USD", showgrid=True, showticklabels=False),
    yaxis2=dict(title="Маржинальность, %", showgrid=False, ticksuffix="%"),
    shapes=col_separators(len(xs)),
)
st.plotly_chart(figd, width="stretch", config={"displayModeBar": False})
if len(months) >= 2:
    _d_turn = (turn_m[-1] / turn_m[-2] - 1) * 100 if turn_m[-2] else 0
    _d_marg = (marg_m[-1] - marg_m[-2])
    _dir_t = "выросла" if _d_turn >= 0 else "снизилась"
    st.markdown(_md(
        f"🔎 **Вывод.** За последний месяц ({xs[-1]}) выручка {_dir_t} на **{abs(_d_turn):.0f}%** "
        f"к предыдущему, маржинальность **{_d_marg:+.2f} п.п.** ({marg_m[-1]:.2f}%)."
    ))
chart_card_close()

# ===== 5. Сводная таблица по сегментам =====
chart_card_open("📋 Сводка по сегментам", f"{period_label} · заливка маржинальности")
tbl = df[["line_ru", "clients", "deals", "turnover_usd", "avg_check", "marg_profit",
          "marginality", "marg_per_client"]].copy()
tbl["avg_check"] = tbl["avg_check"] * 1000            # тыс USD → USD
tbl.columns = ["Сегмент", "Клиентов", "Сделок", "Оборот", "Средний чек",
               "Маржа", "Маржинальность", "Маржа / клиент"]


st.session_state.setdefault("seg_tbl_nonce", 0)
if st.button("↺ Сбросить сортировку и фильтры", key="seg_tbl_reset"):
    st.session_state["seg_tbl_nonce"] += 1
styler = (
    tbl.style
    .format({"Клиентов": "{:.0f}", "Сделок": "{:.0f}", "Оборот": _mfmt,
             "Средний чек": _mfmt, "Маржа": _mfmt, "Маржа / клиент": _mfmt,
             "Маржинальность": lambda v: f"{v*100:.2f}%".replace(".", ",")})
    .apply(_bg_marg, subset=["Маржа", "Маржинальность"])
)
st.dataframe(styler, width="stretch", hide_index=True,
             height=min(500, 44 + 35 * len(tbl)),
             key=f"seg_tbl_{st.session_state['seg_tbl_nonce']}")
_mpc = df.loc[df["marg_per_client"].idxmax()]
st.markdown(_md(
    f"🔎 **Вывод.** Больше всего маржи на одного клиента приносит **{_mpc['line_ru']}** "
    f"({format_money(_mpc['marg_per_client'])} / клиент). "
    f"Всего активных клиентов — **{t_clients}**, средний чек по компании — {format_money(t_check)}."
))
chart_card_close()
