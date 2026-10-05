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
from config import DEALS_SIZE_GROUPS
from data.sheets_loader import (deals_period_label, deals_period_short, deals_period_yms,
                                deals_sale_split, deals_top_clients, deals_vitrina,
                                deals_vitrina_blocks, deals_vitrina_by_period)

st.set_page_config(page_title="Сделки", page_icon="🧾", layout="wide")
apply()
render_assistant()

hero("🧾 Сделки: каналы и продукты",
     "Из витрин книги RUDA: «Каналы по размеру сделки» и «Продуктовые группы»")

PV = "Прибыль после переменных расходов"
_pct = lambda v: f"{v * 100:.2f}%".replace(".", ",")
_cnt = lambda v: "—" if pd.isna(v) else f"{int(v)}"

# ===== Переключатели (в самом начале): разрез + период =====
col_v, col_p = st.columns([1, 2])
with col_v:
    if "deals_view" not in st.session_state:
        st.session_state["deals_view"] = "Продукты" if _qp_int("dv", 0) == 1 else "Каналы"
    view = st.radio("Разрез", ["Каналы", "Продукты"], horizontal=True, key="deals_view")
st.query_params["dv"] = "1" if view == "Продукты" else "0"
kind = "channels" if view == "Каналы" else "products"
src = "Каналы по размеру сделки" if kind == "channels" else "Продуктовые группы"

periods_all, _ = deals_vitrina_blocks(kind)
if not periods_all:
    st.warning(f"Не удалось прочитать витрину «{src}» в книге RUDA.")
    st.stop()

# период: у каналов — месяцы, у продуктов — кварталы и месяцы (как блоки витрины),
# поэтому у каждого разреза свои параметры URL: каналы ?df=&dt=, продукты ?pf=&pt=
qf, qt = ("df", "dt") if kind == "channels" else ("pf", "pt")
last = len(periods_all) - 1
with col_p:
    if len(periods_all) >= 2:
        i0 = _qp_int(qf, last); i1 = _qp_int(qt, last)
        i0 = i0 if 0 <= i0 <= last else last
        i1 = i1 if 0 <= i1 <= last else last
        rng = st.select_slider("Период (потяните концы для диапазона)", options=periods_all,
                               value=(periods_all[min(i0, i1)], periods_all[max(i0, i1)]),
                               key=f"deals_range_{kind}")
        p_from, p_to = rng if isinstance(rng, (list, tuple)) else (rng, rng)
    else:
        p_from = p_to = periods_all[0]
        st.caption(p_from)

i_from, i_to = periods_all.index(p_from), periods_all.index(p_to)
sel = periods_all[i_from:i_to + 1]
st.query_params[qf] = str(i_from)
st.query_params[qt] = str(i_to)
period = deals_period_label(sel)
sel_yms = sorted({ym for p in sel for ym in deals_period_yms(p)})

if kind == "channels":
    src_txt = (f"Цифры — из витрины **«{src}»** книги RUDA (помесячные блоки), как в файле. "
               "Поставщики ликвидности в каналы не входят; обменные сделки — внутри своих каналов.")
else:
    src_txt = (f"Цифры — из витрины **«{src}»** книги RUDA: блоки за 1 и 2 квартал, дальше по "
               "месяцам — как в файле. Показаны только клиентские продукты: **поставщики "
               "ликвидности исключены**, ИТОГО = ИТОГО витрины без них. **ОБМЕН** — отдельный "
               "продукт, Импорт и Экспорт — без обменных сделок.")
st.info(
    src_txt + " Уровни прибыли: **валовая маржа** = комиссия для клиента + курсовая разница; "
    "**чистая маржа** = − комиссия агента и займы; **прибыль после переменных расходов** = "
    "− комиссии банкам и субагенту, комма за пп, PL 5470, ФОТ процессинга, внутрибанковские "
    "конвертации. Постоянный расход (накладные) и переоценка сюда **не** входят. "
    "Диапазон из нескольких периодов = сумма блоков витрины; уникальных клиентов за диапазон "
    "считаем по вкладке «Сделки» теми же условиями, что в формулах витрины."
)

render_abbr_expander(PAGE_DEALS)

df = deals_vitrina(kind, sel)
if df.empty or not (df["role"] == "total").any():
    st.warning("Нет данных за выбранный период.")
    st.stop()
tot = df[df["role"] == "total"].iloc[0]
lvl0 = df[df["bar"]].copy()
lvl0["clients_txt"] = lvl0["clients"].map(_cnt)
what = "каналов" if kind == "channels" else "продуктов"          # родительный: «4 каналов»
what_dat = "каналам" if kind == "channels" else "продуктам"      # дательный: «по каналам»

# сверка: строки графиков вместе должны давать ИТОГО витрины (иначе витрину перестроили)
if abs(lvl0["turnover"].sum() - tot["turnover"]) > 1:
    st.warning(f"⚠ Строки {what} не складываются в ИТОГО витрины «{src}» "
               f"(разница {format_money(lvl0['turnover'].sum() - tot['turnover'])}) — "
               "похоже, в витрине поменялись строки.")

# ===== KPI =====
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Оборот", format_money(tot["turnover"]))
c2.metric("Сделок", f"{int(tot['deals'])}")
c3.metric("Клиентов", _cnt(tot["clients"]))
c4.metric("Валовая маржа", format_money(tot["gross"]))
c5.metric("Чистая маржа", format_money(tot["net_margin"]))
c6.metric(PV, format_money(tot["profit_var"]))
c7.metric("Маржинальность", _pct(tot["profit_var_pct"]))
st.caption(f"Период: **{period}** ({len(sel_yms)} мес.) · {len(lvl0)} {what} · клиенты — "
           f"уникальные за период · маржинальность = прибыль после переменных расходов ÷ оборот")
st.markdown("")

_green = lambda v: PALETTE["success"] if v >= 0 else PALETTE["danger"]


def _bar_h(frame, valcol, colorfn, textfn, xtitle, hovertail, namecol="short"):
    fr = frame.sort_values(valcol, ascending=True)
    fig = go.Figure(go.Bar(
        x=fr[valcol], y=[wrap_label(a, 16) for a in fr[namecol]], orientation="h",
        marker=dict(color=[colorfn(v) for v in fr[valcol]], line=dict(width=0)),
        text=[textfn(v) for v in fr[valcol]], textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=11),
        customdata=fr[["turnover", "profit_var", "clients_txt", "deals"]],
        hovertemplate="<b>%{y}</b><br>" + hovertail + "<extra></extra>",
    ))
    style_plotly_2d(fig, height=max(280, 48 * len(fr)))
    fig.update_layout(
        xaxis=dict(title=xtitle, showgrid=True, zeroline=True, showticklabels=False,
                   zerolinecolor="rgba(255,92,122,0.55)"),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        shapes=row_separators(len(fr)), margin=dict(l=10, r=95, t=10, b=10),
    )
    return fig


# ===== 1. Оборот =====
chart_card_open(f"💰 Оборот по {what_dat}", f"{period} · USD")
fig = _bar_h(lvl0, "turnover", lambda v: "#36C5F0", _money_txt, "Оборот, USD",
             "Оборот: %{x:,.0f} $<br>" + PV + ": %{customdata[1]:,.0f} $<br>"
             "Сделок: %{customdata[3]} · клиентов: %{customdata[2]}")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
_t = lvl0.sort_values("turnover", ascending=False).iloc[0]
st.markdown(_md(
    f"🔎 **Вывод.** Больше всего оборота даёт **{_t['short']}** "
    f"({format_money(_t['turnover'])}, {_t['turnover'] / tot['turnover'] * 100:.0f}% от "
    f"{format_money(tot['turnover'])})."
))
chart_card_close()

# ===== 2. Прибыль после переменных расходов =====
chart_card_open(f"📈 {PV} по {what_dat}",
                f"{period} · USD · до постоянного расхода (накладных) и переоценки")
fig = _bar_h(lvl0, "profit_var", _green, _money_txt, f"{PV}, USD",
             PV + ": %{x:,.0f} $<br>Оборот: %{customdata[0]:,.0f} $")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
_lead = lvl0.sort_values("profit_var", ascending=False).iloc[0]
_neg = lvl0[lvl0["profit_var"] < 0]
neg_txt = (f" В минусе: **{', '.join(_neg['short'])}** "
           f"({format_money(_neg['profit_var'].sum())})." if len(_neg) else "")
lead_share = _lead["profit_var"] / tot["profit_var"] * 100 if tot["profit_var"] else 0
st.markdown(_md(
    f"🔎 **Вывод.** Основную прибыль приносит **{_lead['short']}** "
    f"({format_money(_lead['profit_var'])}, {lead_share:.0f}% итога)." + neg_txt
))
chart_card_close()

# ===== 3. Маржинальность =====
avg = tot["profit_var_pct"]
chart_card_open(f"🎯 Маржинальность по {what_dat}",
                f"{period} · прибыль после переменных расходов ÷ оборот · пунктир — средняя {_pct(avg)}")
fr = lvl0.sort_values("profit_var_pct", ascending=True)
figm = go.Figure(go.Bar(
    x=fr["profit_var_pct"] * 100, y=[wrap_label(a, 16) for a in fr["short"]], orientation="h",
    marker=dict(color=[_green(v) for v in fr["profit_var_pct"]], line=dict(width=0)),
    text=[_pct(v) for v in fr["profit_var_pct"]],
    textposition="outside", textfont=dict(color=PALETTE["ink"], size=11),
    hovertemplate="<b>%{y}</b><br>Маржинальность: %{x:.2f}%<extra></extra>",
))
style_plotly_2d(figm, height=max(280, 48 * len(fr)))
figm.update_layout(
    xaxis=dict(title="Маржинальность, %", showgrid=True, zeroline=True, ticksuffix="%",
               showticklabels=False, zerolinecolor="rgba(255,92,122,0.55)"),
    yaxis=dict(showgrid=False, tickfont=dict(size=12)),
    shapes=row_separators(len(fr)) + [dict(
        type="line", xref="x", yref="paper", x0=avg * 100, x1=avg * 100,
        y0=0, y1=1, line=dict(color="#F5B544", width=1.5, dash="dash"))],
    margin=dict(l=10, r=95, t=10, b=10),
)
st.plotly_chart(figm, width="stretch", config={"displayModeBar": False})
_best = lvl0.loc[lvl0["profit_var_pct"].idxmax()]
_worst = lvl0.loc[lvl0["profit_var_pct"].idxmin()]
st.markdown(_md(
    f"🔎 **Вывод.** Самый прибыльный на доллар оборота — **{_best['short']}** "
    f"({_pct(_best['profit_var_pct'])}), самый слабый — **{_worst['short']}** "
    f"({_pct(_worst['profit_var_pct'])}). Средняя — {_pct(avg)}."
))
chart_card_close()

# ===== 4. Динамика по месяцам (итог клиентских сделок, выбранные — ярко) =====
# помесячные итоги — из «Каналов по размеру сделки»: итог клиентских сделок в обоих разрезах один
mt = deals_vitrina_by_period("channels")
mt = mt[mt["role"] == "total"].reset_index(drop=True)
chart_card_open("📅 Динамика по месяцам",
                "оборот (столбцы) и маржинальность (линия) · итог клиентских сделок · выделен период"
                + (" · помесячно — из «Каналов по размеру сделки»" if kind == "products" else ""))
xs = [deals_period_short(p) for p in mt["period"]]
sel_set = set(sel_yms)
on = [deals_period_yms(p)[0] in sel_set for p in mt["period"]]
figd = make_subplots(specs=[[{"secondary_y": True}]])
figd.add_trace(go.Bar(
    x=xs, y=mt["turnover"], name="Оборот",
    marker_color=["#36C5F0" if o else "rgba(54,197,240,0.28)" for o in on],
    text=[format_money(v) for v in mt["turnover"]], textposition="outside",
    textfont=dict(color="#8A90B8", size=10),
    customdata=mt["profit_var"],
    hovertemplate="<b>%{x}</b><br>Оборот: %{y:,.0f} $<br>" + PV + ": %{customdata:,.0f} $<extra></extra>",
), secondary_y=False)
figd.add_trace(go.Scatter(
    x=xs, y=mt["profit_var_pct"] * 100, name="Маржинальность", mode="lines+markers+text",
    line=dict(color="#F5B544", width=3), marker=dict(size=8, color="#F5B544"),
    text=[_pct(v) for v in mt["profit_var_pct"]],
    textposition="top center", textfont=dict(color="#F5B544", size=10),
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
if len(mt) >= 2:
    t1, t0 = mt["turnover"].iloc[-1], mt["turnover"].iloc[-2]
    d_turn = (t1 / t0 - 1) * 100 if t0 else 0
    d_marg = (mt["profit_var_pct"].iloc[-1] - mt["profit_var_pct"].iloc[-2]) * 100
    dir_t = "вырос" if d_turn >= 0 else "снизился"
    d_marg_txt = f"{d_marg:+.2f}".replace(".", ",")
    st.markdown(_md(
        f"🔎 **Вывод.** В последнем месяце ({xs[-1]}) оборот {dir_t} на **{abs(d_turn):.0f}%** "
        f"к предыдущему, маржинальность **{d_marg_txt} п.п.** "
        f"({_pct(mt['profit_var_pct'].iloc[-1])})."
    ))
chart_card_close()

# ===== 4b. Динамика оборота с разбивкой по каналам/продуктам (стек) =====
bp = deals_vitrina_by_period(kind)
bp = bp[bp["bar"]]
groups = list(dict.fromkeys(bp["short"]))
per = list(dict.fromkeys(bp["period"]))
xg = [deals_period_short(p) for p in per]
chart_card_open(f"📊 Динамика оборота по {what_dat}",
                "вклад каждого по месяцам · стек, USD" if kind == "channels" else
                "по блокам витрины: 1 и 2 квартал (3 месяца), дальше месяцы · стек, USD")
figg = go.Figure()
for gi, gname in enumerate(groups):
    vals = [bp[(bp["period"] == p) & (bp["short"] == gname)]["turnover"].sum() for p in per]
    figg.add_trace(go.Bar(
        x=xg, y=vals, name=gname, marker_color=CHART_COLORS[gi % len(CHART_COLORS)],
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
    _sum_g = {g: bp[bp["short"] == g]["turnover"].sum() for g in groups}
    _lead_g = max(_sum_g, key=_sum_g.get)
    _tot_g = sum(_sum_g.values())
    st.markdown(_md(
        f"🔎 **Вывод.** За все периоды витрины наибольший вклад в оборот даёт **{_lead_g}** "
        f"({format_money(_sum_g[_lead_g])}, {_sum_g[_lead_g] / _tot_g * 100:.0f}% суммарного "
        f"оборота по {what_dat})."
    ))
chart_card_close()

# ===== 5. Сводная таблица (строки витрины; Группа/Подгруппа/Детализация — сортировка не ломает иерархию) =====
chart_card_open(f"📋 Сводка по {what_dat}",
                f"{period} · строки как в витрине «{src}» · заливка — прибыль после перем. расходов · "
                "клик по шапке сортирует")
lines = df[(df["size"] == "") & df["role"].isin(["line", "total"])]
tbl = pd.DataFrame({
    "Группа": lines["group"],
    "Подгруппа": lines["sub"],
    "Детализация": lines["detail"],
    "Клиентов": lines["clients"], "Сделок": lines["deals"].astype(int),
    "Оборот": lines["turnover"], "Средний чек": lines["avg_check"],
    "Комиссия для клиента": lines["our_comm"],
    "Валовая маржа": lines["gross"], "Чистая маржа": lines["net_margin"],
    "Прибыль после перем. расходов": lines["profit_var"],
    "Маржинальность": lines["profit_var_pct"],
})
styler = (
    tbl.style
    .format({"Клиентов": "{:.0f}", "Сделок": "{:.0f}", "Оборот": _mfmt,
             "Средний чек": _mfmt, "Комиссия для клиента": _mfmt, "Валовая маржа": _mfmt,
             "Чистая маржа": _mfmt, "Прибыль после перем. расходов": _mfmt,
             "Маржинальность": _pct}, na_rep="—")
    .apply(_bg, subset=["Прибыль после перем. расходов", "Маржинальность"])
)
st.dataframe(styler, width="stretch", hide_index=True,
             height=min(620, 44 + 35 * len(tbl)))
st.caption("ℹ️ Строка без подгруппы — итог группы; с подгруппой/детализацией — строки внутри "
           "неё, как в витрине. Клиентов по строке — уникальные внутри строки, сумма по строкам "
           "может превышать ИТОГО (клиент бывает в нескольких строках). Клик по заголовку сортирует.")

# первичные vs повторные продажи (посделочно из «Сделок» за месяцы периода, как в витрине)
sp = deals_sale_split(sel_yms)
prim = sp[sp["sale"] == "первичная"]
rep = sp[sp["sale"] == "повторная"]
if len(prim) and len(rep) and prim.iloc[0]["turnover"] > 0:
    pr, rp = prim.iloc[0], rep.iloc[0]
    chk = "мельче" if pr["avg_check"] < rp["avg_check"] else "крупнее"
    st.markdown(_md(
        f"🔎 **Первичные vs повторные.** Первичные продажи (самая первая сделка клиента) дали "
        f"**{format_money(pr['turnover'])}** оборота "
        f"({_pct(pr['turnover'] / tot['turnover'])}) при маржинальности "
        f"{_pct(pr['profit_var_pct'])}; повторные — **{format_money(rp['turnover'])}** "
        f"при {_pct(rp['profit_var_pct'])}. Первая сделка в этом периоде {chk} повторной "
        f"(средний чек {format_money(pr['avg_check'])} против {format_money(rp['avg_check'])})."
    ))
chart_card_close()

# ===== 6. По размеру сделки (только каналы: группы размера есть в витрине каналов) =====
if kind == "channels":
    chart_card_open("📦 По размеру сделки",
                    f"{period} · группы по обороту сделки, USD · верхняя граница в группу не входит")
    line_rows = lines.to_dict("records")
    keys = [(r["group"], r["sub"], r["detail"]) for r in line_rows]
    names = {(r["group"], r["sub"], r["detail"]): ("ИТОГО" if r["role"] == "total" else
             " · ".join(x for x in (r["sub"] or r["group"], r["detail"]) if x)) for r in line_rows}
    tot_key = next(k for k, r in zip(keys, line_rows) if r["role"] == "total")
    pick = st.selectbox("Строка витрины", [tot_key] + [k for k in keys if k != tot_key],
                        format_func=lambda k: names[k], key="deals_size_line")
    sz = df[(df["size"] != "") & (df["group"] == pick[0]) & (df["sub"] == pick[1])
            & (df["detail"] == pick[2])].copy()
    sz["_o"] = sz["size"].map({s: i for i, s in enumerate(DEALS_SIZE_GROUPS)})
    sz = sz.sort_values("_o")
    if sz.empty or not sz["deals"].sum():
        st.caption("Нет сделок в этой строке за период.")
    else:
        figs = make_subplots(specs=[[{"secondary_y": True}]])
        figs.add_trace(go.Bar(
            x=sz["size"], y=sz["profit_var"], name=PV,
            marker=dict(color=[_green(v) for v in sz["profit_var"]], line=dict(width=0)),
            text=[_money_txt(v) for v in sz["profit_var"]], textposition="outside",
            textfont=dict(color=PALETTE["ink"], size=11),
            customdata=sz[["turnover", "deals"]].assign(cl=sz["clients"].map(_cnt)),
            hovertemplate="<b>%{x}</b><br>" + PV + ": %{y:,.0f} $<br>Оборот: %{customdata[0]:,.0f} $"
                          "<br>Сделок: %{customdata[1]} · клиентов: %{customdata[2]}<extra></extra>",
        ), secondary_y=False)
        figs.add_trace(go.Scatter(
            x=sz["size"], y=sz["profit_var_pct"] * 100, name="Маржинальность",
            mode="lines+markers+text", line=dict(color="#F5B544", width=3),
            marker=dict(size=8, color="#F5B544"), text=[_pct(v) for v in sz["profit_var_pct"]],
            textposition="top center", textfont=dict(color="#F5B544", size=10),
            hovertemplate="<b>%{x}</b><br>Маржинальность: %{y:.2f}%<extra></extra>",
        ), secondary_y=True)
        style_plotly_2d(figs, height=380)
        figs.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title=f"{PV}, USD", showgrid=True, showticklabels=False,
                       zeroline=True, zerolinecolor="rgba(255,92,122,0.55)"),
            yaxis2=dict(title="Маржинальность, %", showgrid=False, ticksuffix="%"),
            shapes=col_separators(len(sz)),
        )
        st.plotly_chart(figs, width="stretch", config={"displayModeBar": False})
        n_all, t_all = sz["deals"].sum(), sz["turnover"].sum()
        small = sz[sz["size"].isin(DEALS_SIZE_GROUPS[:2])]
        neg = sz[sz["profit_var"] < 0]
        neg_s = (f" В минусе: **{', '.join(neg['size'])}** ({format_money(neg['profit_var'].sum())})."
                 if len(neg) else " Все группы в плюсе.")
        st.markdown(_md(
            f"🔎 **Вывод.** Сделки до 50 тыс — **{small['deals'].sum() / n_all * 100:.0f}%** "
            f"числа сделок и {small['turnover'].sum() / t_all * 100:.0f}% оборота, прибыль после "
            f"переменных расходов {format_money(small['profit_var'].sum())}." + neg_s
        ))
        tbs = pd.DataFrame({
            "Размер сделки": sz["size"], "Клиентов": sz["clients"],
            "Сделок": sz["deals"].astype(int), "Оборот": sz["turnover"],
            "Средний чек": sz["avg_check"], "Валовая маржа": sz["gross"],
            "Чистая маржа": sz["net_margin"], "Прибыль после перем. расходов": sz["profit_var"],
            "Маржинальность": sz["profit_var_pct"],
        })
        st.dataframe(
            tbs.style.format({"Клиентов": "{:.0f}", "Сделок": "{:.0f}", "Оборот": _mfmt,
                              "Средний чек": _mfmt, "Валовая маржа": _mfmt, "Чистая маржа": _mfmt,
                              "Прибыль после перем. расходов": _mfmt, "Маржинальность": _pct},
                             na_rep="—")
            .apply(_bg, subset=["Прибыль после перем. расходов", "Маржинальность"]),
            width="stretch", hide_index=True)
    chart_card_close()

# ===== 7. Топ-15 клиентов (посделочно из «Сделок») =====
chart_card_open("🏆 Топ-15 клиентов",
                f"{period} · сортировка по прибыли после переменных расходов · клиентские сделки")
top = deals_top_clients(sel_yms, 15, by="profit_var")
if top.empty:
    st.caption("Нет данных за выбранный период.")
else:
    top["short"] = top["name"]
    top["clients_txt"] = ""
    fig = _bar_h(top, "profit_var", _green, _money_txt, f"{PV}, USD",
                 PV + ": %{x:,.0f} $<br>Оборот: %{customdata[0]:,.0f} $<br>"
                 "Сделок: %{customdata[3]}")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    lead_np = top.iloc[0]
    lead_ob = deals_top_clients(sel_yms, 1, by="turnover").iloc[0]
    top_share = top["profit_var"].sum() / tot["profit_var"] * 100 if tot["profit_var"] else 0
    st.markdown(_md(
        f"🔎 **Вывод.** Больше всех прибыли приносит **{lead_np['name']}** "
        f"({format_money(lead_np['profit_var'])} при обороте "
        f"{format_money(lead_np['turnover'])}). По обороту лидирует **{lead_ob['name']}** "
        f"({format_money(lead_ob['turnover'])}). Топ-15 клиентов дают "
        f"{top_share:.0f}% всей прибыли после переменных расходов."
    ))

    tbl_c = pd.DataFrame({
        "Клиент": top["name"], "Сделок": top["deals"].astype(int),
        "Оборот": top["turnover"], "Средний чек": top["avg_check"],
        "Валовая маржа": top["gross"], "Прибыль после перем. расходов": top["profit_var"],
        "Маржинальность": top["profit_var_pct"],
    })
    styler_c = (
        tbl_c.style
        .format({"Сделок": "{:.0f}", "Оборот": _mfmt, "Средний чек": _mfmt,
                 "Валовая маржа": _mfmt, "Прибыль после перем. расходов": _mfmt,
                 "Маржинальность": _pct})
        .apply(_bg, subset=["Прибыль после перем. расходов", "Маржинальность"])
    )
    st.dataframe(styler_c, width="stretch", hide_index=True,
                 height=min(600, 44 + 35 * len(tbl_c)))
chart_card_close()
