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

st.set_page_config(page_title="PL общий", page_icon="📈", layout="wide")
apply()
render_assistant()

hero(f"📈 PL общий · {TARGET_YEAR}",
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

tab_wf, tab_alt, tab_sankey = st.tabs(
    ["📊 Waterfall", "🍩 Структура расходов + маржинальность", "🔀 Поток (Sankey)"])

with tab_wf:
    chart_card_open(f"От выручки до чистой прибыли · {month_name} {TARGET_YEAR}",
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

with tab_sankey:
    chart_card_open(f"Поток P&L · {period_label}",
                    "Sankey · от выручки до чистой прибыли, тыс. USD")
    s_nodes = ["Выручка", "Прямые расходы", "Валовая прибыль", "OPEX",
               "Операционная прибыль", "Налог", "Чистая прибыль"]
    s_node_colors = ["#36C5F0", "#FF5C7A", "#2FD9A6", "#F5B544",
                     "#8B7BF0", "#E94FA1", "#2FD9A6"]
    s_src = [0, 0, 2, 2, 4, 4]
    s_tgt = [1, 2, 3, 4, 5, 6]
    s_real = [direct_costs, gross_profit, opex, op_profit, tax, net_profit]
    s_val = [max(abs(v), 1) for v in s_real]
    s_link_colors = ["rgba(255,92,122,0.35)", "rgba(47,217,166,0.30)",
                     "rgba(245,181,68,0.35)", "rgba(139,123,240,0.30)",
                     "rgba(233,79,161,0.35)", "rgba(47,217,166,0.40)"]
    sankey = go.Figure(go.Sankey(
        node=dict(label=s_nodes, color=s_node_colors, pad=20, thickness=18,
                  line=dict(width=0)),
        link=dict(source=s_src, target=s_tgt, value=s_val, color=s_link_colors,
                  customdata=[fmt_kusd(v) for v in s_real],
                  hovertemplate="%{customdata}<extra></extra>"),
    ))
    sankey.update_layout(height=480, paper_bgcolor="rgba(0,0,0,0)",
                         font=dict(color=PALETTE["ink"], size=13),
                         margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(sankey, use_container_width=True, config={"displayModeBar": False})
    st.caption("Ширина потока — модуль суммы; наведите для точного значения. "
               "FX/переоценка и прочие статьи для наглядности не показаны.")
    chart_card_close()


st.markdown("---")

# ===== OPEX breakdown =====
chart_card_open(f"Структура OPEX · {month_name} {TARGET_YEAR}",
                "3D · по группам расходов, тыс. USD")
opex_groups = [
    ("opex_software_it",  "Software & IT",      "Расходы на ПО и ИТ",          "#8B7BF0"),
    ("opex_marketing",    "Marketing",          "Маркетинг и реклама",         "#2FD9A6"),
    ("opex_personnel",    "Personnel",          "Расходы на персонал",         "#F5B544"),
    ("opex_ga",           "G&A",                "Общехоз. и админ. расходы",   "#E94FA1"),
    ("opex_consulting",   "Consulting & Audit", "Консалтинг и аудит",          "#4A7DFF"),
    ("opex_legal",        "Legal & Compliance", "Юридические и комплаенс",     "#3FE0C5"),
    ("opex_other",        "Other Operating",    "Прочие операционные расходы", "#FF8AC4"),
]
fig = go.Figure()
labels = []
for i, (key, label_en, label_ru, color) in enumerate(opex_groups):
    val = fv(key)
    labels.append(label_en)
    height = abs(val)  # расходы отрицательные — берём модуль для высоты бара
    fig.add_trace(cuboid_mesh(
        x0=i - 0.35, x1=i + 0.35,
        y0=-0.35, y1=0.35,
        z0=0, z1=height,
        color=color,
        name=f"<b>{label_en}</b><br>{label_ru}<br><b>{fmt_kusd(val)}</b>",
    ))
fig.update_layout(
    scene=dict(
        xaxis=dict(tickmode="array", tickvals=list(range(len(labels))),
                   ticktext=labels, title=""),
        yaxis=dict(showticklabels=False, title=""),
        zaxis=dict(title="тыс. USD"),
    ),
    showlegend=False,
)
style_plotly_3d(fig, height=540)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "scrollZoom": True})
chart_card_close()

# ===== 3D-бары: динамика =====
left, right = st.columns([1, 1])

with left:
    chart_card_open("Динамика выручки 2026", "3D · по месяцам, тыс. USD")
    rev_series = pl_series(rows, "revenue", "fact", 2026)
    valid = [(i, v) for i, v in enumerate(rev_series, 1) if v > 0]
    fig = go.Figure()
    for idx, (m, v) in enumerate(valid):
        fig.add_trace(cuboid_mesh(
            x0=idx - 0.35, x1=idx + 0.35,
            y0=-0.35, y1=0.35,
            z0=0, z1=v,
            color="#8B7BF0",
            name=f"{MONTH_NAMES_SHORT[m - 1]}: {fmt_kusd(v)}",
        ))
    fig.update_layout(
        scene=dict(
            xaxis=dict(tickmode="array", tickvals=list(range(len(valid))),
                       ticktext=[MONTH_NAMES_SHORT[m - 1] for m, _ in valid],
                       title=""),
            yaxis=dict(showticklabels=False, title=""),
            zaxis=dict(title="тыс. USD"),
        ),
        showlegend=False,
    )
    style_plotly_3d(fig, height=440)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "scrollZoom": True})
    chart_card_close()

with right:
    chart_card_open("Динамика чистой прибыли 2026", "3D · по месяцам, тыс. USD")
    np_series = pl_series(rows, "net_profit", "fact", 2026)
    valid = [(i, v) for i, v in enumerate(np_series, 1) if v != 0]
    fig = go.Figure()
    for idx, (m, v) in enumerate(valid):
        color = "#2FD9A6" if v >= 0 else "#FF5C7A"
        z0, z1 = (0, v) if v >= 0 else (v, 0)
        fig.add_trace(cuboid_mesh(
            x0=idx - 0.35, x1=idx + 0.35,
            y0=-0.35, y1=0.35,
            z0=z0, z1=z1,
            color=color,
            name=f"{MONTH_NAMES_SHORT[m - 1]}: {fmt_kusd(v)}",
        ))
    fig.update_layout(
        scene=dict(
            xaxis=dict(tickmode="array", tickvals=list(range(len(valid))),
                       ticktext=[MONTH_NAMES_SHORT[m - 1] for m, _ in valid],
                       title=""),
            yaxis=dict(showticklabels=False, title=""),
            zaxis=dict(title="тыс. USD"),
        ),
        showlegend=False,
    )
    style_plotly_3d(fig, height=440)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "scrollZoom": True})
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
