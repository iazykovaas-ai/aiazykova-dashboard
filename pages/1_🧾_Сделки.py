import sys
from pathlib import Path

import pandas as pd
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
from components.styles import (CHART_COLORS, PALETTE, apply, chart_card_close,
                               chart_card_open, col_separators, hero, row_separators,
                               style_plotly_2d, wrap_label)
from data.sheets_loader import (deals_agg, deals_month_label, deals_monthly_by_group,
                                deals_monthly_totals, deals_months, deals_period_label,
                                deals_sale_split, deals_top_clients)

st.set_page_config(page_title="Сделки", page_icon="🧾", layout="wide")
apply()
render_assistant()

hero("🧾 Сделки: каналы и продукты",
     "Посделочно из вкладки «Сделки»: помесячно, период — любой диапазон месяцев")

st.info(
    "Данные считаются **посделочно** из вкладки «Сделки» (книга RUDA) и агрегируются по выбранным "
    "месяцам. Показаны **фактические** уровни дохода: **валовая маржа** = наша комиссия + курсовая; "
    "**чистая маржа** = − комиссия агента и займы; **чистая прибыль** = − банки, субагент, PL 5470, "
    "ФОТ процессинга, внутрибанковские конвертации. Накладные (аренда, налоги и пр.) сюда **не** входят. "
    "**Ликвидность (поставщики) исключена везде** — смотрим только на клиентские сделки."
)

render_abbr_expander(PAGE_DEALS)

months_all = deals_months()
if not months_all:
    st.warning("Не удалось прочитать вкладку «Сделки».")
    st.stop()

# ===== Переключатели: разрез + период (диапазон месяцев) =====
col_v, col_p = st.columns([1, 2])
with col_v:
    if "deals_view" not in st.session_state:
        st.session_state["deals_view"] = "Продукты" if _qp_int("dv", 0) == 1 else "Каналы"
    view = st.radio("Разрез", ["Каналы", "Продукты"], horizontal=True, key="deals_view")
st.query_params["dv"] = "1" if view == "Продукты" else "0"
kind = "channels" if view == "Каналы" else "products"

last = len(months_all) - 1
with col_p:
    if len(months_all) >= 2:
        # дефолт из URL (?df=&dt=); value кортежем → слайдер работает в режиме ДИАПАЗОНА
        i0 = _qp_int("df", last); i1 = _qp_int("dt", last)
        i0 = i0 if 0 <= i0 <= last else last
        i1 = i1 if 0 <= i1 <= last else last
        default_range = (months_all[min(i0, i1)], months_all[max(i0, i1)])
        rng = st.select_slider("Период (потяните концы для диапазона)", options=months_all,
                               value=default_range, format_func=deals_month_label,
                               key="deals_range")
        m_from, m_to = rng if isinstance(rng, (list, tuple)) else (rng, rng)
    else:
        m_from = m_to = months_all[0]
        st.caption(deals_month_label(m_from))

i_from, i_to = months_all.index(m_from), months_all.index(m_to)
sel_months = months_all[i_from:i_to + 1]
st.query_params["df"] = str(i_from)
st.query_params["dt"] = str(i_to)
period = deals_period_label(sel_months)

df = deals_agg(kind, sel_months)
lvl0 = df[df["level"] == 0].copy()
total = df[df["level"] == "total"]
tot = total.iloc[0]
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
n_mon = len(sel_months)
st.caption(f"Период: **{period}** ({n_mon} мес.) · {len(lvl0)} {what} верхнего уровня · "
           f"клиенты — уникальные за период")
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
    style_plotly_2d(fig, height=max(280, 48 * len(fr)))
    fig.update_layout(
        xaxis=dict(title=xtitle, showgrid=True, zeroline=True, showticklabels=False,
                   ticksuffix="%" if pct else "", zerolinecolor="rgba(255,92,122,0.55)"),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        shapes=row_separators(len(fr)), margin=dict(l=10, r=95, t=10, b=10),
    )
    return fig


# ===== 1. Оборот =====
chart_card_open(f"💰 Оборот по {what}", f"{period} · USD")
fig = _bar_h(lvl0, "turnover", lambda v: "#36C5F0", _money_txt, "Оборот, USD",
             "Оборот: %{x:,.0f} $<br>Чистая прибыль: %{customdata[1]:,.0f} $<br>"
             "Сделок: %{customdata[3]} · клиентов: %{customdata[2]}")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
_t = lvl0.sort_values("turnover", ascending=False).iloc[0]
st.markdown(_md(
    f"🔎 **Вывод.** Больше всего оборота даёт **{_t['name']}** "
    f"({format_money(_t['turnover'])}, {_t['turnover'] / tot['turnover'] * 100:.0f}% от "
    f"{format_money(tot['turnover'])})."
))
chart_card_close()

# ===== 2. Чистая прибыль =====
chart_card_open(f"📈 Чистая прибыль по {what}", f"{period} · USD · после ФОТ и конвертаций")
fig = _bar_h(lvl0, "net_profit", _green, _money_txt, "Чистая прибыль, USD",
             "Чистая прибыль: %{x:,.0f} $<br>Оборот: %{customdata[0]:,.0f} $")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
_lead = lvl0.sort_values("net_profit", ascending=False).iloc[0]
_neg = lvl0[lvl0["net_profit"] < 0]
neg_txt = (f" В минусе: **{', '.join(_neg['name'])}** "
           f"({format_money(_neg['net_profit'].sum())})." if len(_neg) else "")
lead_share = _lead["net_profit"] / tot["net_profit"] * 100 if tot["net_profit"] else 0
st.markdown(_md(
    f"🔎 **Вывод.** Основную прибыль приносит **{_lead['name']}** "
    f"({format_money(_lead['net_profit'])}, {lead_share:.0f}% итога)." + neg_txt
))
chart_card_close()

# ===== 3. Маржинальность (ЧП%) =====
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
style_plotly_2d(figm, height=max(280, 48 * len(fr)))
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
    f"🔎 **Вывод.** Самый прибыльный на доллар оборота — **{_best['name']}** "
    f"({_best['net_profit_pct'] * 100:.2f}%), самый слабый — **{_worst['name']}** "
    f"({_worst['net_profit_pct'] * 100:.2f}%). Средняя по компании — {avg * 100:.2f}%."
))
chart_card_close()

# ===== 4. Динамика по месяцам (весь год, выбранные — ярко) =====
chart_card_open("📅 Динамика по месяцам", "оборот (столбцы) и маржинальность ЧП (линия) · выделен период")
mt = deals_monthly_totals(kind, months_all)
xs = [deals_month_label(m).replace(" 2026", "").replace(" 2025", "") for m in mt["month"]]
sel_set = set(sel_months)
bar_colors = ["#36C5F0" if m in sel_set else "rgba(54,197,240,0.28)" for m in mt["month"]]
figd = make_subplots(specs=[[{"secondary_y": True}]])
figd.add_trace(go.Bar(
    x=xs, y=mt["turnover"], name="Оборот", marker_color=bar_colors,
    text=[format_money(v) for v in mt["turnover"]], textposition="outside",
    textfont=dict(color="#8A90B8", size=10),
    customdata=mt["net_profit"],
    hovertemplate="<b>%{x}</b><br>Оборот: %{y:,.0f} $<br>ЧП: %{customdata:,.0f} $<extra></extra>",
), secondary_y=False)
figd.add_trace(go.Scatter(
    x=xs, y=mt["net_profit_pct"] * 100, name="Маржинальность ЧП", mode="lines+markers+text",
    line=dict(color="#F5B544", width=3), marker=dict(size=8, color="#F5B544"),
    text=[f"{v * 100:.2f}%".replace(".", ",") for v in mt["net_profit_pct"]],
    textposition="top center", textfont=dict(color="#F5B544", size=10),
    hovertemplate="<b>%{x}</b><br>Маржинальность ЧП: %{y:.2f}%<extra></extra>",
), secondary_y=True)
style_plotly_2d(figd, height=380)
figd.update_layout(
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="Оборот, USD", showgrid=True, showticklabels=False),
    yaxis2=dict(title="ЧП, %", showgrid=False, ticksuffix="%"),
    shapes=col_separators(len(xs)),
)
st.plotly_chart(figd, width="stretch", config={"displayModeBar": False})
if len(mt) >= 2:
    d_turn = (mt["turnover"].iloc[-1] / mt["turnover"].iloc[-2] - 1) * 100 if mt["turnover"].iloc[-2] else 0
    d_marg = (mt["net_profit_pct"].iloc[-1] - mt["net_profit_pct"].iloc[-2]) * 100
    dir_t = "вырос" if d_turn >= 0 else "снизился"
    st.markdown(_md(
        f"🔎 **Вывод.** В последнем месяце ({xs[-1]}) оборот {dir_t} на **{abs(d_turn):.0f}%** "
        f"к предыдущему, маржинальность ЧП **{d_marg:+.2f} п.п.** "
        f"({mt['net_profit_pct'].iloc[-1] * 100:.2f}%)."
    ))
chart_card_close()

# ===== 4b. Динамика оборота с разбивкой по каналам/продуктам (стек) =====
chart_card_open(f"📊 Динамика оборота по {what}", "вклад каждого по месяцам · весь год · стек, USD")
byg, groups = deals_monthly_by_group(kind, months_all)
xg = [deals_month_label(m).replace(" 2026", "").replace(" 2025", "") for m in byg["month"]]
figg = go.Figure()
for gi, gname in enumerate(groups):
    figg.add_trace(go.Bar(
        x=xg, y=byg[gname], name=gname, marker_color=CHART_COLORS[gi % len(CHART_COLORS)],
        hovertemplate="<b>%{x}</b><br>" + _md(gname) + ": %{y:,.0f} $<extra></extra>",
    ))
style_plotly_2d(figg, height=400)
figg.update_layout(
    barmode="stack", margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    yaxis=dict(title="Оборот, USD", showgrid=True, showticklabels=False),
    xaxis=dict(showgrid=False),
    shapes=col_separators(len(xg)),
)
st.plotly_chart(figg, width="stretch", config={"displayModeBar": False})
if groups:
    _sum_g = {g: byg[g].sum() for g in groups}
    _lead_g = max(_sum_g, key=_sum_g.get)
    _tot_g = sum(_sum_g.values())
    st.markdown(_md(
        f"🔎 **Вывод.** За весь период наибольший вклад в оборот даёт **{_lead_g}** "
        f"({format_money(_sum_g[_lead_g])}, {_sum_g[_lead_g] / _tot_g * 100:.0f}% суммарного "
        f"оборота по {what})."
    ))
chart_card_close()

# ===== 5. Сводная таблица с иерархией =====
chart_card_open(f"📋 Сводка по {what}", f"{period} · вложенные строки — с отступом · заливка ЧП%")
rows_tbl = []
for _, r in df[df["level"].isin([0, 1])].iterrows():
    nm = r["name"] if r["level"] == 0 else "    " + r["name"]
    rows_tbl.append({
        "Строка": nm, "Клиентов": int(r["clients"]), "Сделок": int(r["deals"]),
        "Оборот": r["turnover"], "Средний чек": r["avg_check"], "Наша комиссия": r["our_comm"],
        "Валовая маржа": r["gross"], "Чистая маржа": r["net_margin"],
        "Чистая прибыль": r["net_profit"], "ЧП, %": r["net_profit_pct"],
    })
tbl = pd.DataFrame(rows_tbl)

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
st.caption("ℹ️ Клиентов по строкам — уникальные внутри строки; сумма по строкам может превышать "
           "ИТОГО (один клиент бывает в нескольких каналах/продуктах).")

# первичные vs повторные клиентские сделки
sp = deals_sale_split(sel_months)
prim = sp[sp["sale"] == "первичная"]
rep = sp[sp["sale"] == "повторная"]
if len(prim) and len(rep) and prim.iloc[0]["turnover"] > 0:
    pr, rp = prim.iloc[0], rep.iloc[0]
    st.markdown(_md(
        f"🔎 **Первичные vs повторные.** Новые клиенты (первая сделка в периоде) дали "
        f"**{format_money(pr['turnover'])}** оборота "
        f"({pr['turnover'] / tot['turnover'] * 100:.1f}%) при маржинальности "
        f"{pr['net_profit_pct'] * 100:.2f}%; повторные — **{format_money(rp['turnover'])}** "
        f"при {rp['net_profit_pct'] * 100:.2f}%. Первая сделка обычно мельче "
        f"(средний чек {format_money(pr['avg_check'])} против {format_money(rp['avg_check'])})."
    ))
chart_card_close()

# ===== 6. Топ-15 клиентов (кто выше всех) =====
chart_card_open("🏆 Топ-15 клиентов", f"{period} · сортировка по чистой прибыли · клиентские сделки")
top = deals_top_clients(sel_months, 15, by="net_profit")
if top.empty:
    st.caption("Нет данных за выбранный период.")
else:
    fig = _bar_h(top, "net_profit", _green, _money_txt, "Чистая прибыль, USD",
                 "ЧП: %{x:,.0f} $<br>Оборот: %{customdata[0]:,.0f} $<br>"
                 "Сделок: %{customdata[3]}")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    lead_np = top.iloc[0]
    lead_ob = deals_top_clients(sel_months, 1, by="turnover").iloc[0]
    top_np_share = top["net_profit"].sum() / tot["net_profit"] * 100 if tot["net_profit"] else 0
    st.markdown(_md(
        f"🔎 **Вывод.** Больше всех прибыли приносит **{lead_np['name']}** "
        f"({format_money(lead_np['net_profit'])} ЧП при обороте "
        f"{format_money(lead_np['turnover'])}). По обороту лидирует **{lead_ob['name']}** "
        f"({format_money(lead_ob['turnover'])}). Топ-15 клиентов дают "
        f"{top_np_share:.0f}% всей чистой прибыли."
    ))

    tbl_c = pd.DataFrame({
        "Клиент": top["name"], "Сделок": top["deals"].astype(int),
        "Оборот": top["turnover"], "Средний чек": top["avg_check"],
        "Валовая маржа": top["gross"], "Чистая прибыль": top["net_profit"],
        "ЧП, %": top["net_profit_pct"],
    })
    styler_c = (
        tbl_c.style
        .format({"Сделок": "{:.0f}", "Оборот": _mfmt, "Средний чек": _mfmt,
                 "Валовая маржа": _mfmt, "Чистая прибыль": _mfmt,
                 "ЧП, %": lambda v: f"{v * 100:.2f}%".replace(".", ",")})
        .apply(_bg, subset=["Чистая прибыль", "ЧП, %"])
    )
    st.dataframe(styler_c, width="stretch", hide_index=True,
                 height=min(600, 44 + 35 * len(tbl_c)))
chart_card_close()
