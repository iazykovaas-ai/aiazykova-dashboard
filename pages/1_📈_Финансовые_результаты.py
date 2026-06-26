import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.kpi import fmt_kusd, fmt_pct
from components.styles import (CHART_COLORS, PALETTE, apply, chart_card_close,
                               chart_card_open, cuboid_mesh, gauge, hero,
                               sparkline, style_plotly_2d, style_plotly_3d)
from config import (MONTH_NAMES_RU, MONTH_NAMES_SHORT, PL_TABLE_LAYOUT,
                    TARGET_MONTH, TARGET_YEAR)
from data.sheets_loader import load_pl_global_raw, pl_series, pl_value

st.set_page_config(page_title="Финансовые результаты", page_icon="📈", layout="wide")
apply()
render_assistant()

hero(f"📈 Финансовые результаты · {TARGET_YEAR}",
     "Общий отчёт о прибылях и убытках компании · по данным PL GLOBAL")

# ===== Переключатель периода =====
st.markdown("##### 📅 Период")
col_from, col_to = st.columns(2)
with col_from:
    from_m = st.selectbox(
        "С месяца", list(range(1, 13)),
        format_func=lambda x: MONTH_NAMES_RU[x - 1],
        index=0, key="period_from",
    )
with col_to:
    to_m = st.selectbox(
        "По месяц", list(range(1, 13)),
        format_func=lambda x: MONTH_NAMES_RU[x - 1],
        index=TARGET_MONTH - 1, key="period_to",
    )
if from_m > to_m:
    from_m, to_m = to_m, from_m  # тихо меняем местами, если перепутаны

# Подпись текущего периода для заголовков
if from_m == to_m:
    period_label = f"{MONTH_NAMES_RU[from_m - 1]} {TARGET_YEAR}"
else:
    period_label = f"{MONTH_NAMES_RU[from_m - 1]} — {MONTH_NAMES_RU[to_m - 1]} {TARGET_YEAR}"

month_name = period_label  # обратная совместимость со старыми f-строками

# Расшифровка аббревиатур
with st.expander("ℹ️ Расшифровка аббревиатур"):
    st.markdown(
        """
        | Сокр. | Расшифровка |
        |---|---|
        | **YoY** | Year-over-Year — изменение к тому же периоду прошлого года |
        | **MoM** | Month-over-Month — изменение к предыдущему месяцу |
        | **YTD** | Year-to-Date — накопительно с начала года |
        | **п.п.** | Процентные пункты (разница между %) |
        | **Revenue** | Выручка |
        | **GP / Gross Profit** | Валовая прибыль (Выручка − Прямые расходы) |
        | **OPEX** | Operating Expenses — операционные (текущие) расходы |
        | **G&A** | General & Administrative — общехозяйственные и административные расходы |
        | **FX** | Foreign Exchange — валютные курсовые разницы |
        | **Operating Profit** | Операционная прибыль (GP − OPEX ± FX) |
        | **PBT** | Profit Before Tax — прибыль до налогообложения |
        | **Net Profit** | Чистая прибыль (после уплаты налога) |
        | **k / M USD** | Тысячи / миллионы долларов США |
        """
    )

rows = load_pl_global_raw()


def fv(metric: str, year: int = TARGET_YEAR) -> float:
    """Сумма значений метрики за выбранный период [from_m..to_m]."""
    return sum(pl_value(rows, metric, m, "fact", year)
               for m in range(from_m, to_m + 1))


revenue = fv("revenue")
direct_costs = fv("direct_costs")
gross_profit = fv("gross_profit")
opex = fv("opex")
op_profit = fv("operating_profit")
pbt = fv("pbt")
net_profit = fv("net_profit")

revenue_prev = fv("revenue", year=2025)
gp_prev = fv("gross_profit", year=2025)
op_prev = fv("operating_profit", year=2025)
np_prev = fv("net_profit", year=2025)


def y2y(curr, prev):
    if not prev:
        return None
    return f"{(curr / prev - 1) * 100:+.1f}% YoY"


# KPI + спарклайн тренда по месяцам под каждым числом
_rev_series = pl_series(rows, "revenue", "fact", 2026)
_last_m = max([i for i, v in enumerate(_rev_series, 1) if v != 0], default=0)
_last_name = MONTH_NAMES_RU[_last_m - 1].lower() if _last_m else ""
kpi_defs = [
    ("Выручка (Revenue)",     revenue,      revenue_prev, "revenue",          "#36C5F0", "выручки"),
    ("Валовая прибыль (GP)",  gross_profit, gp_prev,      "gross_profit",     "#2FD9A6", "маржи"),
    ("Операционная прибыль",  op_profit,    op_prev,      "operating_profit", "#8B7BF0", "опер. прибыли"),
    ("Чистая прибыль (Net)",  net_profit,   np_prev,      "net_profit",       "#F5B544", "чистой прибыли"),
]
for col, (label, val, prev, key, color, short) in zip(st.columns(4), kpi_defs):
    with col:
        st.metric(label, fmt_kusd(val), y2y(val, prev))
        st.caption(f"Тренд {short} · январь — {_last_name}")
        st.plotly_chart(sparkline(pl_series(rows, key, "fact", 2026), color),
                        use_container_width=True, config={"displayModeBar": False})

# ===== Гейджи: выполнение бюджета за выбранный период =====
# Бюджет и маржи (GP), и чистой прибыли — помесячный: суммируем за выбранный период.
gp_budget = sum(pl_value(rows, "gross_profit", m, "budget") for m in range(from_m, to_m + 1))
gp_done = gross_profit / gp_budget * 100 if gp_budget else 0

np_budget = sum(pl_value(rows, "net_profit", m, "budget") for m in range(from_m, to_m + 1))
np_done = net_profit / np_budget * 100 if np_budget else 0

chart_card_open(f"Выполнение бюджета · {period_label}",
                "Факт / Бюджет за выбранный период, % (цель — 100%)")
gc1, gc2 = st.columns(2)


def _render_gauge(col, pct, budget, title, color):
    # Если бюджет за период <= 0 (напр. плановый убыток) — % выполнения не определён.
    if budget <= 0:
        col.markdown(
            f"<div style='text-align:center;padding:48px 10px;'>"
            f"<div style='color:#C7CCEC;font-weight:600;margin-bottom:10px;'>{title}</div>"
            f"<div style='color:#8A90B8;font-size:0.9rem;'>Бюджет за период &le; 0<br>"
            f"% выполнения не считается</div></div>",
            unsafe_allow_html=True,
        )
    else:
        col.plotly_chart(gauge(pct, title, vmax=max(150, abs(pct) * 1.15),
                               target=100, color=color),
                         use_container_width=True, config={"displayModeBar": False})


_render_gauge(gc1, gp_done, gp_budget, "Маржинальная прибыль", "#2FD9A6")
_render_gauge(gc2, np_done, np_budget, "Чистая прибыль", "#F5B544")
chart_card_close()

st.markdown("")

# ===== Waterfall =====
# В PL GLOBAL расходы хранятся со знаком «минус», доходы — со знаком «плюс».
revaluation_val = fv("revaluation")
realized_fx_val = fv("realized_fx")
other_income_val = fv("other_income")
financial_val = fv("financial_inc_exp")
tax = fv("income_tax")

# Шаги waterfall: (название, значение, тип). Нулевые «relative»-строки скрываем.
wf_steps = [
    ("Выручка",                              revenue,          "absolute"),
    ("Прямые расходы",                       direct_costs,     "relative"),
    ("Валовая прибыль",                      gross_profit,     "total"),
    ("Переоценка",                           revaluation_val,  "relative"),
    ("Внутрибанковские конвертации",         realized_fx_val,  "relative"),
    ("OPEX",                                 opex,             "relative"),
    ("Операционная прибыль",                 op_profit,        "total"),
    ("Прочие доходы/расходы",                other_income_val, "relative"),
    ("Финансовые доходы/расходы",            financial_val,    "relative"),
    ("PBT",                                  pbt,              "total"),
    ("Налог",                                tax,              "relative"),
    ("Чистая прибыль",                       net_profit,       "total"),
]
wf_filtered = [(lbl, val, m) for lbl, val, m in wf_steps
               if not (m == "relative" and val == 0)]

tab_wf, tab_alt, tab_funnel = st.tabs(
    ["📊 Waterfall", "🍩 Структура расходов + маржинальность", "🔻 Воронка прибыли"])

with tab_wf:
    chart_card_open(f"От выручки до чистой прибыли · {period_label}",
                    "Waterfall, тыс. USD")
    wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=[m for _, _, m in wf_filtered],
        x=[lbl for lbl, _, _ in wf_filtered],
        y=[val for _, val, _ in wf_filtered],
        text=[fmt_kusd(val) for _, val, _ in wf_filtered],
        textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        connector=dict(line=dict(color=PALETTE["line"], width=1)),
        increasing=dict(marker=dict(color="#2FD9A6")),
        decreasing=dict(marker=dict(color="#FF5C7A")),
        totals=dict(marker=dict(color="#8B7BF0")),
    ))
    style_plotly_2d(wf, height=440)
    wf.update_layout(yaxis=dict(title="тыс. USD"), xaxis=dict(showgrid=False))
    st.plotly_chart(wf, use_container_width=True,
                    config={"displayModeBar": True, "displaylogo": False, "scrollZoom": True})
    chart_card_close()

with tab_alt:
    col_a, col_b = st.columns(2)
    with col_a:
        chart_card_open("Структура расходов", "Donut · от чего складываются расходы")
        # Цвета синхронизированы с 3D OPEX-графиком ниже:
        # Software & IT = лаванда, Marketing = мята, Personnel = персик,
        # G&A = роза, Consulting = небо, Legal = ваниль, Other = сирень.
        # Прямые расходы и Налог — отдельные цвета (их нет на OPEX-графике).
        cost_labels = ["Прямые расходы", "Software & IT", "Marketing", "Personnel",
                       "G&A", "Consulting", "Legal", "Other Operating", "Налог"]
        cost_values = [abs(direct_costs),
                       abs(fv("opex_software_it")),
                       abs(fv("opex_marketing")),
                       abs(fv("opex_personnel")),
                       abs(fv("opex_ga")),
                       abs(fv("opex_consulting")),
                       abs(fv("opex_legal")),
                       abs(fv("opex_other")),
                       abs(tax)]
        cost_pal = ["#36C5F0",  # Прямые расходы — шалфей
                    "#8B7BF0",  # Software & IT — лаванда
                    "#2FD9A6",  # Marketing — мята
                    "#F5B544",  # Personnel — персик
                    "#E94FA1",  # G&A — магента
                    "#4A7DFF",  # Consulting — небо
                    "#3FE0C5",  # Legal — ваниль
                    "#FF8AC4",  # Other Operating — сирень
                    "#8A90B8"]  # Налог — серо-лавандовый
        fig = go.Figure(go.Pie(
            labels=cost_labels, values=cost_values, hole=0.6,
            marker=dict(colors=cost_pal, line=dict(color="white", width=2)),
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} k$<br>%{percent}<extra></extra>",
        ))
        style_plotly_2d(fig, height=440)
        fig.update_layout(showlegend=True,
                          legend=dict(orientation="v", y=0.5, x=1.02,
                                      font=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
        chart_card_close()

    with col_b:
        chart_card_open("Маржинальность по месяцам",
                        "GP / Оборот · GP+FX / Оборот · OP / Оборот · Net / Оборот")
        months_axis = []
        gp_pct, gp_fx_pct, op_pct, np_pct = [], [], [], []
        for m in range(1, 13):
            turnover_m = pl_value(rows, "turnover", m, "fact", TARGET_YEAR)
            if turnover_m <= 0:
                continue
            months_axis.append(MONTH_NAMES_SHORT[m - 1])
            gp_m = pl_value(rows, "gross_profit", m, "fact", TARGET_YEAR)
            revaluation_m = pl_value(rows, "revaluation", m, "fact", TARGET_YEAR)
            realized_fx_m = pl_value(rows, "realized_fx", m, "fact", TARGET_YEAR)
            gp_pct.append(gp_m / turnover_m * 100)
            gp_fx_pct.append((gp_m + revaluation_m + realized_fx_m) / turnover_m * 100)
            op_pct.append(pl_value(rows, "operating_profit", m, "fact", TARGET_YEAR) / turnover_m * 100)
            np_pct.append(pl_value(rows, "net_profit", m, "fact", TARGET_YEAR) / turnover_m * 100)
        fig = go.Figure()
        for name, vals, color in [("GP / Оборот", gp_pct, "#8B7BF0"),
                                  ("GP+FX / Оборот", gp_fx_pct, "#4A7DFF"),
                                  ("OP / Оборот", op_pct, "#2FD9A6"),
                                  ("Net / Оборот", np_pct, "#F5B544")]:
            fig.add_trace(go.Scatter(
                x=months_axis, y=vals, mode="lines+markers",
                name=name,
                line=dict(color=color, width=3),
                marker=dict(size=10),
                hovertemplate=f"<b>{name}</b> %{{y:.2f}}%<extra></extra>",
            ))
        style_plotly_2d(fig, height=440)
        fig.update_layout(yaxis=dict(ticksuffix="%"),
                          legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
        chart_card_close()

with tab_funnel:
    chart_card_open(f"Воронка прибыли · {period_label}",
                    "от выручки до чистой прибыли · тыс. USD и % от выручки")
    f_labels = ["Выручка", "Валовая прибыль", "Операционная прибыль", "Чистая прибыль"]
    f_vals = [revenue, gross_profit, op_profit, net_profit]
    f_colors = ["#36C5F0", "#8B7BF0", "#2FD9A6", "#F5B544"]
    funnel = go.Figure(go.Funnel(
        y=f_labels, x=f_vals,
        textposition="inside", textfont=dict(color="#0A0E20", size=14),
        texttemplate="%{value:,.0f} тыс. $ · %{percentInitial:.0%}",
        marker=dict(color=f_colors, line=dict(color="#0A0E20", width=2)),
        connector=dict(line=dict(color=PALETTE["line"], width=1, dash="dot")),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} тыс. $<br>%{percentInitial:.1%} от выручки<extra></extra>",
    ))
    style_plotly_2d(funnel, height=460)
    funnel.update_layout(separators=". ", yaxis=dict(showgrid=False),
                         xaxis=dict(visible=False))
    st.plotly_chart(funnel, use_container_width=True, config={"displayModeBar": False})
    st.caption("Каждый уровень — сколько от выручки остаётся после расходов: "
               "Валовая (− прямые расходы) → Операционная (− OPEX ± FX) → Чистая (− налог).")
    chart_card_close()


st.markdown("---")

# --- Структура OPEX (бары / treemap) ---
opex_groups = [
    ("opex_software_it",  "Software & IT",      "Расходы на ПО и ИТ",          "#8B7BF0"),
    ("opex_marketing",    "Marketing",          "Маркетинг и реклама",         "#2FD9A6"),
    ("opex_personnel",    "Personnel",          "Расходы на персонал",         "#F5B544"),
    ("opex_ga",           "G&A",                "Общехоз. и админ. расходы",   "#E94FA1"),
    ("opex_consulting",   "Consulting & Audit", "Консалтинг и аудит",          "#4A7DFF"),
    ("opex_legal",        "Legal & Compliance", "Юридические и комплаенс",     "#3FE0C5"),
    ("opex_other",        "Other Operating",    "Прочие операционные расходы", "#FF8AC4"),
]
ovals = [(le, lr, abs(fv(k)), c) for k, le, lr, c in opex_groups]
opex_view = st.radio("Вид структуры OPEX", ["Бары", "Treemap"], horizontal=True, key="opex_view")
chart_card_open(f"Структура OPEX · {period_label}", "по группам расходов, тыс. USD")
if opex_view == "Бары":
    order = sorted(ovals, key=lambda t: t[2])
    fig = go.Figure(go.Bar(
        x=[t[2] for t in order], y=[t[0] for t in order], orientation="h",
        marker=dict(color=[t[3] for t in order], line=dict(width=0)),
        text=[fmt_kusd(t[2]) for t in order], textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        customdata=[t[1] for t in order],
        hovertemplate="<b>%{y}</b><br>%{customdata}<br>%{text}<extra></extra>"))
    style_plotly_2d(fig, height=430)
    fig.update_layout(xaxis=dict(showticklabels=False, showgrid=True),
                      yaxis=dict(showgrid=False))
else:
    fig = go.Figure(go.Treemap(
        labels=[t[0] for t in ovals], parents=[""] * len(ovals),
        values=[t[2] for t in ovals],
        marker=dict(colors=[t[3] for t in ovals], line=dict(color="#0A0E20", width=2)),
        customdata=[f"{t[1]} · {fmt_kusd(t[2])}" for t in ovals],
        texttemplate="<b>%{label}</b><br>%{value:.0f} тыс. $<br>%{percentRoot}",
        textfont=dict(size=14, color="#0A0E20"),
        hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>"))
    fig.update_layout(height=440, margin=dict(l=6, r=6, t=6, b=6),
                      paper_bgcolor="rgba(0,0,0,0)", separators=". ")
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# --- Динамика по месяцам (площадь / бары, выбор метрики) ---
DYN_METRICS = [("revenue", "Выручка", "#8B7BF0"),
               ("gross_profit", "Валовая прибыль", "#36C5F0"),
               ("operating_profit", "Операционная прибыль", "#2FD9A6"),
               ("net_profit", "Чистая прибыль", "#F5B544")]
dmap = {k: (l, c) for k, l, c in DYN_METRICS}
dc1, dc2 = st.columns([2, 1])
with dc1:
    dsel = st.selectbox("Метрика динамики", [k for k, _, _ in DYN_METRICS],
                        format_func=lambda k: dmap[k][0], key="pl_dyn_metric")
with dc2:
    dyn_view = st.radio("Тип", ["Площадь", "Бары"], horizontal=True, key="pl_dyn_view")
dlabel, dcolor = dmap[dsel]
chart_card_open(f"Динамика · {dlabel} · {TARGET_YEAR}", "по месяцам, тыс. USD")
series = pl_series(rows, dsel, "fact", 2026)
valid = [(i, v) for i, v in enumerate(series, 1) if v != 0]
xs = [MONTH_NAMES_SHORT[m - 1] for m, _ in valid]
ys = [v for _, v in valid]
if dyn_view == "Площадь":
    _r, _g, _b = int(dcolor[1:3], 16), int(dcolor[3:5], 16), int(dcolor[5:7], 16)
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="lines+markers+text",
        line=dict(color=dcolor, width=3, shape="spline"),
        marker=dict(size=9, color=dcolor, line=dict(color="#0A0E20", width=1)),
        fill="tozeroy", fillcolor=f"rgba({_r},{_g},{_b},0.18)",
        text=[fmt_kusd(v) for v in ys], textposition="top center",
        textfont=dict(color=PALETTE["ink"], size=11),
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>"))
else:
    fig = go.Figure(go.Bar(
        x=xs, y=ys,
        marker=dict(color=[dcolor if v >= 0 else "#FF5C7A" for v in ys], line=dict(width=0)),
        text=[fmt_kusd(v) for v in ys], textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=11),
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>"))
style_plotly_2d(fig, height=420)
fig.update_layout(xaxis=dict(showgrid=False))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# ===== Полная P&L таблица =====
chart_card_open(f"Полный P&L · {period_label}",
                f"Все статьи · факт за {period_label}")


def fmt_cell(val: float, is_ratio: bool = False) -> str:
    if val == 0:
        return "—"
    if is_ratio:
        return fmt_pct(val)
    return fmt_kusd(val)


# Для коэффициента маржи к обороту считаем GP / Turnover за период
turnover_total = fv("turnover")
gp_total = fv("gross_profit")
turnover_ratio_period = gp_total / turnover_total if turnover_total else 0

table_rows = []
for key, label, kind in PL_TABLE_LAYOUT:
    is_ratio = key == "turnover_ratio"
    val = turnover_ratio_period if is_ratio else fv(key)
    table_rows.append({
        "Статья": label,
        f"{period_label} (факт)": fmt_cell(val, is_ratio),
        "_kind": kind,
    })
table_df = pd.DataFrame(table_rows)


def style_pl_row(kind: str, n_cols: int):
    if kind == "total":
        return ["font-weight: 700; background-color: #241E48; color: #FFFFFF;"] * n_cols
    if kind == "subitem":
        return ["color: #AEB4D8; padding-left: 18px;"] * n_cols
    return ["color: #E8EAF6;"] * n_cols


display_df = table_df.drop(columns=["_kind"])
styled = display_df.style.apply(
    lambda row: style_pl_row(table_df.iloc[row.name]["_kind"], len(row)), axis=1
)
st.dataframe(styled, use_container_width=True, hide_index=True, height=820)
chart_card_close()
