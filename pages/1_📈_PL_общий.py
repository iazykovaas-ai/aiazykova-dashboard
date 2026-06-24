import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.kpi import fmt_kusd, fmt_pct
from components.styles import (PALETTE, apply, chart_card_close,
                               chart_card_open, cuboid_mesh, hero,
                               style_plotly_2d, style_plotly_3d)
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


c1, c2, c3, c4 = st.columns(4)
c1.metric("Выручка (Revenue)", fmt_kusd(revenue), y2y(revenue, revenue_prev))
c2.metric("Валовая прибыль (GP)", fmt_kusd(gross_profit), y2y(gross_profit, gp_prev))
c3.metric("Операционная прибыль", fmt_kusd(op_profit), y2y(op_profit, op_prev))
c4.metric("Чистая прибыль (Net)", fmt_kusd(net_profit), y2y(net_profit, np_prev))

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

tab_wf, tab_alt = st.tabs(["📊 Waterfall", "🍩 Структура расходов + маржинальность"])

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
        increasing=dict(marker=dict(color="#9DD8BE")),
        decreasing=dict(marker=dict(color="#EFA9C0")),
        totals=dict(marker=dict(color="#B8A3DC")),
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
        cost_pal = ["#B8DCC8",  # Прямые расходы — шалфей
                    "#B8A3DC",  # Software & IT — лаванда
                    "#9DD8BE",  # Marketing — мята
                    "#F0C8A0",  # Personnel — персик
                    "#EFA9C0",  # G&A — роза
                    "#A9C9EE",  # Consulting — небо
                    "#F0DBA0",  # Legal — ваниль
                    "#C5B2EC",  # Other Operating — сирень
                    "#D4D0E2"]  # Налог — серо-лавандовый
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
        for name, vals, color in [("GP / Оборот", gp_pct, "#B8A3DC"),
                                  ("GP+FX / Оборот", gp_fx_pct, "#A9C9EE"),
                                  ("OP / Оборот", op_pct, "#9DD8BE"),
                                  ("Net / Оборот", np_pct, "#F0C8A0")]:
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

st.markdown("---")

# ===== OPEX breakdown =====
chart_card_open(f"Структура OPEX · {month_name} {TARGET_YEAR}",
                "3D · по группам расходов, тыс. USD")
opex_groups = [
    ("opex_software_it",  "Software & IT",      "Расходы на ПО и ИТ",          "#B8A3DC"),
    ("opex_marketing",    "Marketing",          "Маркетинг и реклама",         "#9DD8BE"),
    ("opex_personnel",    "Personnel",          "Расходы на персонал",         "#F0C8A0"),
    ("opex_ga",           "G&A",                "Общехоз. и админ. расходы",   "#EFA9C0"),
    ("opex_consulting",   "Consulting & Audit", "Консалтинг и аудит",          "#A9C9EE"),
    ("opex_legal",        "Legal & Compliance", "Юридические и комплаенс",     "#F0DBA0"),
    ("opex_other",        "Other Operating",    "Прочие операционные расходы", "#C5B2EC"),
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
            color="#B8A3DC",
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
        color = "#9DD8BE" if v >= 0 else "#EFA9C0"
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
