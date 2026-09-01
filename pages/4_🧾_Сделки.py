import sys
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.format import (bg_diverging as _bg, md_escape as _md,
                               num_spaced as _money_txt, qp_int as _qp_int,
                               usd_spaced as _mfmt)
from components.glossary import PAGE_DEALS, render_abbr_expander
from components.kpi import format_money
from components.styles import (PALETTE, apply, chart_card_close, chart_card_open,
                               col_separators, hero, row_separators, style_plotly_2d,
                               wrap_label)
from data.sheets_loader import (deals_block_df, deals_periods,
                                load_deals_channels_raw, load_deals_products_raw)

st.set_page_config(page_title="Сделки", page_icon="🧾", layout="wide")
apply()
render_assistant()

hero("🧾 Сделки: каналы и продукты",
     "Посделочная сборка: как пришёл клиент (каналы) и что за сделка (продукты)")

st.info(
    "Данные из посделочного реестра **RUDA** (книга «Каналы/Продукты»). Показаны **фактические** "
    "цифры (без гипотетических «скрытых надбавок» режима 2). Уровни дохода: **валовая маржа** = "
    "наша комиссия + курсовая; **чистая маржа** = − комиссия агента и займы; **чистая прибыль** = "
    "− банки, субагент, PL 5470, ФОТ процессинга, внутрибанковские конвертации. "
    "Накладные (аренда, налоги, топ-менеджмент и пр.) сюда **не** входят."
)

render_abbr_expander(PAGE_DEALS)

# ===== Переключатели: канал/продукт и период =====
col_v, col_p = st.columns([1, 2])
with col_v:
    if "deals_view" not in st.session_state:
        st.session_state["deals_view"] = "Продукты" if _qp_int("dv", 0) == 1 else "Каналы"
    view = st.radio("Разрез", ["Каналы", "Продукты"], horizontal=True, key="deals_view")
st.query_params["dv"] = "1" if view == "Продукты" else "0"

kind = "channels" if view == "Каналы" else "products"
rows = load_deals_channels_raw() if kind == "channels" else load_deals_products_raw()
periods = deals_periods(rows)
if not periods:
    st.warning("Не удалось прочитать периоды из источника.")
    st.stop()

with col_p:
    default_idx = len(periods) - 1                       # последний период (июль)
    if "deals_period" not in st.session_state:
        pi = _qp_int("dp", default_idx)
        st.session_state["deals_period"] = periods[pi] if 0 <= pi < len(periods) else periods[default_idx]
    elif st.session_state["deals_period"] not in periods:
        st.session_state["deals_period"] = periods[default_idx]
    period = st.selectbox("Период", periods, key="deals_period")
st.query_params["dp"] = str(periods.index(period))

df = deals_block_df(rows, kind, period)
if df.empty:
    st.warning("Нет данных за период.")
    st.stop()

lvl0 = df[df["level"] == 0].copy()                       # верхний уровень (полное разбиение)
lvl1 = df[df["level"] == 1].copy()
total = df[df["level"] == "total"]
memo = df[df["level"] == "memo"].copy()
tot = total.iloc[0] if len(total) else lvl0.sum(numeric_only=True)

what = "каналов" if kind == "channels" else "продуктов"

# ===== KPI =====
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Оборот", format_money(tot["turnover"]))
c2.metric("Сделок", f"{int(tot['deals'])}")
c3.metric("Клиентов", f"{int(tot['clients'])}")
c4.metric("Валовая маржа", format_money(tot["gross"]))
c5.metric("Чистая маржа", format_money(tot["net_margin"]))
c6.metric("Чистая прибыль", format_money(tot["net_profit"]))
c7.metric("Маржинальность (ЧП)", f"{tot['net_profit_pct'] * 100:.2f}%".replace(".", ","))
st.caption(f"Период: **{period}** · {len(lvl0)} {what} верхнего уровня")
st.markdown("")

_green = lambda v: PALETTE["success"] if v >= 0 else PALETTE["danger"]


def _bar_h(frame, valcol, colorfn, textfn, xtitle, hovertail, pct=False):
    fr = frame.sort_values(valcol, ascending=True)
    xs = fr[valcol] * (100 if pct else 1)
    fig = go.Figure(go.Bar(
        x=xs, y=[wrap_label(a, 16) for a in fr["name"]], orientation="h",
        marker=dict(color=[colorfn(v) for v in fr[valcol]], line=dict(width=0)),
        text=[textfn(v) for v in fr[valcol]], textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=11),
        customdata=fr[["turnover", "net_profit", "clients", "deals"]],
        hovertemplate="<b>%{y}</b><br>" + hovertail + "<extra></extra>",
    ))
    style_plotly_2d(fig, height=max(300, 46 * len(fr)))
    fig.update_layout(
        xaxis=dict(title=xtitle, showgrid=True, zeroline=True, showticklabels=False,
                   ticksuffix="%" if pct else "",
                   zerolinecolor="rgba(255,92,122,0.55)"),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        shapes=row_separators(len(fr)), margin=dict(l=10, r=95, t=10, b=10),
    )
    return fig


# короткие подписи для мостиков/выводов
def _clean(name):
    return (name.replace(" (клиентский) всего, в т.ч.:", "").replace(" (клиентский)", "")
                .replace(", всего, в т. ч.:", "").replace(" итого, в том числе", ""))


lvl0["short"] = lvl0["name"].map(_clean)

# ===== 1. Оборот по разрезу =====
chart_card_open(f"💰 Оборот по {what}", f"{period} · USD")
fig = _bar_h(lvl0, "turnover", lambda v: "#36C5F0", _money_txt, "Оборот, USD",
             "Оборот: %{x:,.0f} $<br>Чистая прибыль: %{customdata[1]:,.0f} $<br>"
             "Сделок: %{customdata[3]} · клиентов: %{customdata[2]}")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
_t = lvl0.sort_values("turnover", ascending=False).iloc[0]
st.markdown(_md(
    f"🔎 **Вывод.** Больше всего оборота даёт **{_clean(_t['name'])}** "
    f"({format_money(_t['turnover'])}, {_t['turnover'] / tot['turnover'] * 100:.0f}% от общего "
    f"{format_money(tot['turnover'])})."
))
chart_card_close()

# ===== 2. Чистая прибыль по разрезу =====
chart_card_open(f"📈 Чистая прибыль по {what}", f"{period} · USD · после ФОТ и конвертаций")
fig = _bar_h(lvl0, "net_profit", _green, _money_txt, "Чистая прибыль, USD",
             "Чистая прибыль: %{x:,.0f} $<br>Оборот: %{customdata[0]:,.0f} $")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
_p = lvl0.sort_values("net_profit", ascending=False)
_lead = _p.iloc[0]
_neg = lvl0[lvl0["net_profit"] < 0]
neg_txt = (f" В минусе: **{', '.join(_neg['short'])}** "
           f"({format_money(_neg['net_profit'].sum())})." if len(_neg) else "")
st.markdown(_md(
    f"🔎 **Вывод.** Основную прибыль приносит **{_clean(_lead['name'])}** "
    f"({format_money(_lead['net_profit'])}, {_lead['net_profit'] / tot['net_profit'] * 100:.0f}% "
    f"итога)." + neg_txt
))
chart_card_close()

# ===== 3. Маржинальность (ЧП%) по разрезу =====
avg = tot["net_profit_pct"]
chart_card_open(f"🎯 Маржинальность по {what}",
                f"{period} · чистая прибыль ÷ оборот · пунктир — средняя {avg * 100:.2f}%")
fr = lvl0.sort_values("net_profit_pct", ascending=True)
figm = go.Figure(go.Bar(
    x=fr["net_profit_pct"] * 100, y=[wrap_label(a, 16) for a in fr["name"]], orientation="h",
    marker=dict(color=[_green(v) for v in fr["net_profit_pct"]], line=dict(width=0)),
    text=[f"{v * 100:.2f}%".replace(".", ",") for v in fr["net_profit_pct"]],
    textposition="outside", textfont=dict(color=PALETTE["ink"], size=11),
    hovertemplate="<b>%{y}</b><br>Маржинальность (ЧП): %{x:.2f}%<extra></extra>",
))
style_plotly_2d(figm, height=max(300, 46 * len(fr)))
figm.update_layout(
    xaxis=dict(title="Маржинальность (ЧП), %", showgrid=True, zeroline=True, ticksuffix="%",
               showticklabels=False, zerolinecolor="rgba(255,92,122,0.55)"),
    yaxis=dict(showgrid=False, tickfont=dict(size=12)),
    shapes=row_separators(len(fr)) + [dict(
        type="line", xref="x", yref="paper", x0=avg * 100, x1=avg * 100,
        y0=0, y1=1, line=dict(color="#F5B544", width=1.5, dash="dash"))],
    margin=dict(l=10, r=95, t=10, b=10),
)
st.plotly_chart(figm, width="stretch", config={"displayModeBar": False})
_best = lvl0.loc[lvl0["net_profit_pct"].idxmax()]
_worst = lvl0.loc[lvl0["net_profit_pct"].idxmin()]
st.markdown(_md(
    f"🔎 **Вывод.** Самый прибыльный на доллар оборота — **{_clean(_best['name'])}** "
    f"({_best['net_profit_pct'] * 100:.2f}%), самый слабый — **{_clean(_worst['name'])}** "
    f"({_worst['net_profit_pct'] * 100:.2f}%). Средняя по компании — {avg * 100:.2f}%."
))
chart_card_close()

# ===== 4. Динамика по периодам (итоги) =====
chart_card_open("📅 Динамика по периодам", "оборот (столбцы) и маржинальность ЧП (линия)")
per_turn, per_pct, per_np = [], [], []
for p in periods:
    tdf = deals_block_df(rows, kind, p)
    tt = tdf[tdf["level"] == "total"]
    tr = tt.iloc[0] if len(tt) else tdf[tdf["level"] == 0].sum(numeric_only=True)
    per_turn.append(tr["turnover"])
    per_np.append(tr["net_profit"])
    per_pct.append(tr["net_profit_pct"] * 100)
figd = make_subplots(specs=[[{"secondary_y": True}]])
figd.add_trace(go.Bar(
    x=periods, y=per_turn, name="Оборот", marker_color="#36C5F0",
    text=[format_money(v) for v in per_turn], textposition="outside",
    textfont=dict(color="#36C5F0", size=11),
    customdata=per_np,
    hovertemplate="<b>%{x}</b><br>Оборот: %{y:,.0f} $<br>ЧП: %{customdata:,.0f} $<extra></extra>",
), secondary_y=False)
figd.add_trace(go.Scatter(
    x=periods, y=per_pct, name="Маржинальность ЧП", mode="lines+markers+text",
    line=dict(color="#F5B544", width=3), marker=dict(size=8, color="#F5B544"),
    text=[f"{v:.2f}%".replace(".", ",") for v in per_pct], textposition="top center",
    textfont=dict(color="#F5B544", size=11),
    hovertemplate="<b>%{x}</b><br>Маржинальность ЧП: %{y:.2f}%<extra></extra>",
), secondary_y=True)
style_plotly_2d(figd, height=360)
figd.update_layout(
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="Оборот, USD", showgrid=True, showticklabels=False),
    yaxis2=dict(title="ЧП, %", showgrid=False, ticksuffix="%"),
    shapes=col_separators(len(periods)),
)
st.plotly_chart(figd, width="stretch", config={"displayModeBar": False})
st.caption("⚠️ Кварталы и месяц (июль) — разного масштаба: сравнивайте маржинальность (линию), "
           "а не высоту столбцов.")
chart_card_close()

# ===== 5. Сводная таблица с иерархией =====
chart_card_open(f"📋 Сводка по {what}", f"{period} · вложенные строки — с отступом · заливка ЧП%")
order = []
if kind == "channels":
    for _, r0 in lvl0.iterrows():
        order.append((r0["name"], r0, 0))
        if r0["name"].startswith("Банковский"):
            for _, r1 in lvl1.iterrows():
                order.append(("    " + r1["name"], r1, 1))
else:
    # продукты: level-1 подтипы идут сразу после своего level-0 (порядок листа сохранён в df)
    seq = df[df["level"].isin([0, 1])]
    for _, r in seq.iterrows():
        nm = r["name"] if r["level"] == 0 else "    " + r["name"]
        order.append((nm, r, r["level"]))

import pandas as pd
tbl = pd.DataFrame([{
    "Строка": nm,
    "Клиентов": int(r["clients"]),
    "Сделок": int(r["deals"]),
    "Оборот": r["turnover"],
    "Средний чек": r["avg_check"],
    "Наша комиссия": r["our_comm"],
    "Валовая маржа": r["gross"],
    "Чистая маржа": r["net_margin"],
    "Чистая прибыль": r["net_profit"],
    "ЧП, %": r["net_profit_pct"],
} for nm, r, _ in order])

st.session_state.setdefault("deals_tbl_nonce", 0)
if st.button("↺ Сбросить сортировку и фильтры", key="deals_tbl_reset"):
    st.session_state["deals_tbl_nonce"] += 1
styler = (
    tbl.style
    .format({"Клиентов": "{:.0f}", "Сделок": "{:.0f}", "Оборот": _mfmt,
             "Средний чек": _mfmt, "Наша комиссия": _mfmt, "Валовая маржа": _mfmt,
             "Чистая маржа": _mfmt, "Чистая прибыль": _mfmt,
             "ЧП, %": lambda v: f"{v * 100:.2f}%".replace(".", ",")})
    .apply(_bg, subset=["Чистая прибыль", "ЧП, %"])
)
st.dataframe(styler, width="stretch", hide_index=True,
             height=min(560, 44 + 35 * len(tbl)),
             key=f"deals_tbl_{st.session_state['deals_tbl_nonce']}")

# первичные/повторные (только для каналов)
if kind == "channels" and len(memo) >= 2:
    prim = memo[memo["name"].str.lower().str.startswith("первич")]
    rep = memo[memo["name"].str.lower().str.startswith("повтор")]
    if len(prim) and len(rep):
        pr, rp = prim.iloc[0], rep.iloc[0]
        st.markdown(_md(
            f"🔎 **Первичные vs повторные.** Новые клиенты (первая сделка) дали "
            f"**{format_money(pr['turnover'])}** оборота ({pr['turnover'] / tot['turnover'] * 100:.1f}%) "
            f"при маржинальности {pr['net_profit_pct'] * 100:.2f}%; повторные — "
            f"**{format_money(rp['turnover'])}** при {rp['net_profit_pct'] * 100:.2f}%. "
            f"Первая сделка обычно мельче (средний чек {format_money(pr['avg_check'])} против "
            f"{format_money(rp['avg_check'])}) — она тестовая."
        ))
chart_card_close()
