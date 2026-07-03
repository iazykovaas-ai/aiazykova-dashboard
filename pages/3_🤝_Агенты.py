import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.glossary import PAGE_AGENTS, render_abbr_expander
from components.kpi import format_money
from components.styles import (PALETTE, apply, chart_card_close, chart_card_open,
                               col_separators, hero, row_separators,
                               style_plotly_2d, wrap_label)
from config import MONTH_NAMES_RU, TARGET_YEAR
from data.sheets_loader import (agent_clients_dataframe, agent_monthly_series,
                                agents_available_months, agents_dataframe,
                                load_agents_svod_raw)

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
    "Маржа": ("margin", "money", "#2FD9A6"),
    "Оборот": ("turnover", "money", "#36C5F0"),
    "Наша комиссия": ("our_fee", "money", "#8B7BF0"),
    "Выплачено агенту": ("payout", "money", "#F5B544"),
    "Кол-во сделок": ("deals", "int", "#E94FA1"),
}
chart_card_open("🏆 Рейтинг агентов", "отсортировано по выбранной метрике · USD (кроме сделок)")
metric_name = st.radio("Метрика", list(METRIC_CHOICES), horizontal=True,
                       key="agents_rank_metric", label_visibility="collapsed")
col_key, fmt, base_color = METRIC_CHOICES[metric_name]

top = df[df[col_key] != 0].sort_values(col_key, ascending=True)
if top.empty:
    st.caption("Нет данных за период.")
else:
    is_money = fmt == "money"
    xvals = top[col_key]
    if is_money:
        texts = [f"{v:,.0f}".replace(",", " ") for v in top[col_key]]
        hover = "<b>%{y}</b><br>" + metric_name + ": %{x:,.0f} $<extra></extra>"
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
        xaxis=dict(showgrid=True, showticklabels=not is_money, zeroline=True,
                   tickfont=dict(size=11)),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        shapes=row_separators(len(top)),
        margin=dict(l=10, r=90, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== Маржинальность по агентам =====
chart_card_open("💹 Маржинальность по клиентам агентов",
                "за период · зелёный — прибыльно, красный — убыточно; оборот и маржа — в подсказке")
sc = df[df["turnover"] > 0].copy().sort_values("marginality", ascending=True)
if sc.empty:
    st.caption("Нет данных за период.")
else:
    xv = sc["marginality"] * 100
    colors = [PALETTE["success"] if v >= 0 else PALETTE["danger"] for v in xv]
    fig = go.Figure(go.Bar(
        x=xv, y=[wrap_label(a, 16) for a in sc["Агент"]], orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:.2f}%".replace(".", ",") for v in xv],
        textposition="outside", textfont=dict(color=PALETTE["ink"], size=11),
        customdata=sc[["turnover", "margin", "deals"]],
        hovertemplate=("<b>%{y}</b><br>Маржинальность: %{x:.2f}%<br>"
                       "Оборот: %{customdata[0]:,.0f} $<br>"
                       "Маржа: %{customdata[1]:,.0f} $<br>"
                       "Сделок: %{customdata[2]}<extra></extra>"),
    ))
    style_plotly_2d(fig, height=max(360, 26 * len(sc)))
    fig.update_layout(
        xaxis=dict(title="Маржинальность, %", showgrid=True, zeroline=True,
                   ticksuffix="%", zerolinecolor="rgba(255,92,122,0.55)", zerolinewidth=1),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        shapes=row_separators(len(sc)),
        margin=dict(l=10, r=70, t=10, b=30),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== Детальная таблица (с «тепловой» заливкой) =====
def _pct(v):
    return f"{v*100:.2f}%".replace(".", ",")


def _eff(v):
    return "—" if pd.isna(v) else f"{v:.1f}×".replace(".", ",")


def _bg_diverging(s):
    """Заливка ячеек столбца: зелёный (плюс) / красный (минус), яркость ∝ величине."""
    m = s.abs().max() or 1
    out = []
    for v in s:
        if pd.isna(v) or v == 0:
            out.append("color:#8A90B8;")
        elif v > 0:
            a = 0.14 + 0.34 * min(v / m, 1)
            out.append(f"background-color: rgba(47,217,166,{a:.2f}); color:#EAFBF4;")
        else:
            a = 0.14 + 0.34 * min(abs(v) / m, 1)
            out.append(f"background-color: rgba(255,92,122,{a:.2f}); color:#FFECEF;")
    return out


def _detail_styler(frame, name_col):
    """Стилизованная таблица (Оборот…Эффективность) с тепловой заливкой.

    frame должен содержать колонки metric-ключей + payout и колонку name_col.
    """
    t = frame.copy()
    t["efficiency"] = [(m / p) if p > 0 else float("nan")
                       for m, p in zip(t["margin"], t["payout"])]
    t = t[[name_col, "turnover", "deals", "margin", "marginality", "client_rate",
           "our_fee", "agent_fee_pct", "agent_fee", "efficiency"]]
    t.columns = [name_col, "Оборот", "Сделок", "Маржа", "Маржинальность", "Тариф клиента",
                 "Наша комиссия", "Комиссия агента, %", "Комиссия агенту", "Эффективность"]
    return (
        t.style
        .format({
            "Оборот": _m, "Маржа": _m, "Наша комиссия": _m, "Комиссия агенту": _m,
            "Сделок": "{:.0f}",
            "Маржинальность": _pct, "Тариф клиента": _pct, "Комиссия агента, %": _pct,
            "Эффективность": _eff,
        })
        .apply(_bg_diverging, subset=["Маржа", "Маржинальность", "Эффективность"])
    )


def _render_detail(frame, name_col, base_key):
    """Описание + кнопка сброса сортировки/фильтров + таблица с заливкой.

    Сброс работает сменой key таблицы (интерактивная сортировка/фильтры st.dataframe
    сбрасываются при ремоунте виджета)."""
    st.markdown(
        "🧮 **Эффективность = Маржа ÷ выплата агенту** (выплата = «Комиссия агенту» по модулю) — "
        "сколько $ маржи приносит каждый $1, выплаченный агенту (напр. «5,1×»). "
        "«—» — если выплаты агенту не было. "
        "Заливка ячеек: зелёная — плюс, красная — минус, ярче — сильнее."
    )
    nkey = f"{base_key}_nonce"
    st.session_state.setdefault(nkey, 0)
    if st.button("↺ Сбросить сортировку и фильтры", key=f"{base_key}_reset"):
        st.session_state[nkey] += 1
    st.dataframe(_detail_styler(frame, name_col), use_container_width=True, hide_index=True,
                 height=min(600, 44 + 35 * len(frame)),
                 key=f"{base_key}_tbl_{st.session_state[nkey]}")


chart_card_open("📋 Детализация по агентам", period_label)
_render_detail(df, "Агент", "agents_detail")
chart_card_close()

# ===== Разбор по одному агенту =====
st.markdown("### 👤 Разбор по агенту")
agent_names = sorted(df["Агент"].tolist(), key=str.lower)
if not agent_names:
    st.caption("Нет активных агентов за период.")
else:
    who = st.selectbox("Агент", agent_names, key="agents_dyn_who")
    xs = [MONTH_NAMES_RU[m - 1] for m in months]

    # ряды по месяцам (проценты храним в долях; комиссию агента берём по модулю)
    marg_s = agent_monthly_series(rows, who, "margin")
    fee_s = agent_monthly_series(rows, who, "agent_fee")
    margness_s = agent_monthly_series(rows, who, "marginality")
    feepct_s = agent_monthly_series(rows, who, "agent_fee_pct")
    turn_s = agent_monthly_series(rows, who, "turnover")

    marg_v = [marg_s[m - 1] for m in months]                # маржа, USD
    pay_v = [-fee_s[m - 1] for m in months]                 # выплата агенту, USD (+)
    margness = [margness_s[m - 1] * 100 for m in months]     # маржинальность, %
    feepct = [-feepct_s[m - 1] * 100 for m in months]        # комиссия агента, % (+)
    # доля комиссии агента в марже (только где маржа > 0)
    share_m = [(pay_v[i] / marg_v[i] * 100) if marg_v[i] > 0 else 0.0
               for i in range(len(months))]

    # KPI агента за период
    row_a = df[df["Агент"] == who].iloc[0]
    a_margness = row_a["marginality"] * 100
    a_feepct = -row_a["agent_fee_pct"] * 100
    a_margin, a_pay = row_a["margin"], row_a["payout"]
    a_share = (a_pay / a_margin * 100) if a_margin > 0 else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Маржинальность (период)", f"{a_margness:.2f}%".replace(".", ","))
    k2.metric("Комиссия агента (период)", f"{a_feepct:.2f}%".replace(".", ","))
    k3.metric("Выплачено агенту (период)", format_money(a_pay))
    k4.metric("Доля комиссии в марже",
              f"{a_share:.1f}%".replace(".", ",") if a_share is not None else "n/m",
              help="Сколько из нашей маржи ушло на выплату агенту. n/m — маржа ≤ 0.")

    # --- График 1: маржинальность % vs комиссия агента % (как на исходном листе, но чище) ---
    chart_card_open("Маржинальность и комиссия агента, %", f"{who} · сравнение по месяцам")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=xs, y=margness, name="Маржинальность, %", marker_color="#36C5F0",
        text=[f"{v:.2f}%".replace(".", ",") for v in margness],
        textposition="outside", textfont=dict(color="#36C5F0", size=11),
        hovertemplate="<b>%{x}</b><br>Маржинальность: %{y:.2f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=xs, y=feepct, name="Комиссия агента, %", marker_color="#F5B544",
        text=[f"{v:.2f}%".replace(".", ",") for v in feepct],
        textposition="outside", textfont=dict(color="#F5B544", size=11),
        hovertemplate="<b>%{x}</b><br>Комиссия агента: %{y:.2f}%<extra></extra>",
    ))
    style_plotly_2d(fig, height=380)
    fig.update_layout(
        barmode="group", bargap=0.28, bargroupgap=0.12,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="% от оборота", showgrid=True, ticksuffix="%", zeroline=True),
        xaxis=dict(tickfont=dict(size=12)),
        shapes=col_separators(len(xs)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()

    # --- График 2: маржа vs выплата агенту, USD (полные суммы) ---
    chart_card_open("Маржа и выплата агенту, USD", f"{who} · USD по месяцам")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=xs, y=marg_v, name="Маржа", marker_color="#2FD9A6",
        text=[f"{v:,.0f}".replace(",", " ") for v in marg_v],
        textposition="outside", textfont=dict(color="#2FD9A6", size=11),
        hovertemplate="<b>%{x}</b><br>Маржа: %{y:,.0f} $<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=xs, y=pay_v, name="Выплата агенту", marker_color="#F5B544",
        text=[f"{v:,.0f}".replace(",", " ") for v in pay_v],
        textposition="outside", textfont=dict(color="#F5B544", size=11),
        hovertemplate="<b>%{x}</b><br>Выплата агенту: %{y:,.0f} $<extra></extra>",
    ))
    style_plotly_2d(fig, height=380)
    fig.update_layout(
        barmode="group", bargap=0.28, bargroupgap=0.12,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="USD", showgrid=True, zeroline=True, showticklabels=False,
                   zerolinecolor="rgba(255,92,122,0.5)"),
        xaxis=dict(tickfont=dict(size=12)),
        shapes=col_separators(len(xs)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()

    # --- График 3 (новое): доля комиссии агента в марже ---
    chart_card_open("Доля комиссии агента в марже, %",
                    "какая часть нашей маржи уходит агенту (месяцы с маржой ≤ 0 — 0)")
    bar_colors = ["#F5B544" if s <= 60 else PALETTE["danger"] for s in share_m]
    fig = go.Figure(go.Bar(
        x=xs, y=share_m, marker=dict(color=bar_colors, line=dict(width=0)),
        text=[f"{v:.0f}%" for v in share_m], textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        hovertemplate="<b>%{x}</b><br>Агенту уходит %{y:.1f}% маржи<extra></extra>",
    ))
    style_plotly_2d(fig, height=320)
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(title="% маржи", showgrid=True, ticksuffix="%"),
        xaxis=dict(tickfont=dict(size=12)),
        shapes=col_separators(len(xs)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()

    # --- Клиенты выбранного агента (ленивая загрузка листа агента) ---
    cdf = agent_clients_dataframe(who, period)
    cmask = (cdf["turnover"] != 0) | (cdf["margin"] != 0) | (cdf["deals"] != 0)
    cdf = cdf[cmask].copy()
    cdf["payout"] = -cdf["agent_fee"]
    cdf = cdf.sort_values("margin", ascending=False).reset_index(drop=True)

    # сверка: сумма по клиентам ≈ итог агента (из свода)
    c_turn, c_marg = cdf["turnover"].sum(), cdf["margin"].sum()
    a_turn, a_marg = row_a["turnover"], row_a["margin"]
    check = "✅ сходится с итогом агента"
    if abs(c_turn - a_turn) > max(1.0, 0.005 * abs(a_turn)) or \
       abs(c_marg - a_marg) > max(1.0, 0.02 * abs(a_marg) + 1):
        check = "⚠️ расхождение с итогом агента"

    chart_card_open(f"Клиенты агента · {who}",
                    f"{period_label} · {len(cdf)} активных клиентов · {check}")
    if cdf.empty:
        st.caption("У агента нет активных клиентов за период.")
    else:
        # Вертикальные группы: маржа + вознаграждение агента по клиентам
        cb = cdf.sort_values("margin", ascending=False)
        xnames = [wrap_label(a, 12) for a in cb["Клиент"]]
        figc = go.Figure()
        figc.add_trace(go.Bar(
            x=xnames, y=cb["margin"], name="Маржа", marker_color="#2FD9A6",
            text=[f"{v:,.0f}".replace(",", " ") for v in cb["margin"]],
            textposition="outside", textfont=dict(color="#2FD9A6", size=11),
            customdata=cb[["turnover", "marginality", "deals"]],
            hovertemplate=("<b>%{x}</b><br>Маржа: %{y:,.0f} $<br>"
                           "Оборот: %{customdata[0]:,.0f} $<br>"
                           "Маржинальность: %{customdata[1]:.2%}<br>"
                           "Сделок: %{customdata[2]}<extra></extra>"),
        ))
        figc.add_trace(go.Bar(
            x=xnames, y=cb["payout"], name="Вознаграждение агента", marker_color="#F5B544",
            text=[f"{v:,.0f}".replace(",", " ") for v in cb["payout"]],
            textposition="outside", textfont=dict(color="#F5B544", size=11),
            hovertemplate="<b>%{x}</b><br>Вознаграждение агента: %{y:,.0f} $<extra></extra>",
        ))
        style_plotly_2d(figc, height=420)
        figc.update_layout(
            barmode="group", bargap=0.30, bargroupgap=0.12,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="USD", showgrid=True, zeroline=True, showticklabels=False,
                       zerolinecolor="rgba(255,92,122,0.5)"),
            xaxis=dict(tickfont=dict(size=11)),
            shapes=col_separators(len(cb)),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.caption("🔍 Потяни рамкой область, чтобы приблизить мелкие столбцы · "
                   "колесо мыши — зум · двойной клик — сброс")
        st.plotly_chart(figc, use_container_width=True, config={
            "displayModeBar": True, "displaylogo": False, "scrollZoom": True,
            "modeBarButtonsToRemove": ["select2d", "lasso2d"],
        })

        # Таблица клиентов — те же столбцы, заливка и сброс, что в детализации агентов
        _render_detail(cdf, "Клиент", f"clients_{who}")
    chart_card_close()
