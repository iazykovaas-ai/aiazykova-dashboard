import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.kpi import format_money
from components.styles import (CHART_COLORS, PALETTE, apply,
                               chart_card_close, chart_card_open, cuboid_mesh,
                               hero, style_plotly_2d, style_plotly_3d)
from data.sheets_loader import load

st.set_page_config(page_title="План vs Факт", page_icon="🎯", layout="wide")
apply()

hero("🎯 План vs Факт", "Квартальный план (Бюджет M1 + Бюджет M2 + Ребюджет M3) vs факт")

df = load("plan_fact", use_stub=True)

total_plan = df["План"].sum()
total_fact = df["Факт"].sum()
delta_abs = total_fact - total_plan
delta_pct = (total_fact / total_plan - 1) * 100 if total_plan else 0
done_pct = total_fact / total_plan * 100 if total_plan else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("План квартала", format_money(total_plan))
c2.metric("Факт", format_money(total_fact), f"{delta_pct:+.1f}%")
c3.metric("Отклонение", format_money(delta_abs))
c4.metric("Выполнение", f"{done_pct:.1f}%")

st.markdown("")

# 3D-стек: план и факт по месяцам
chart_card_open("План vs Факт по месяцам", "3D · млн ₽")
fig = go.Figure()
for i, (_, row) in enumerate(df.iterrows()):
    plan_mln = row["План"] / 1_000_000
    fact_mln = row["Факт"] / 1_000_000
    # план — слева, факт — справа
    fig.add_trace(cuboid_mesh(
        x0=i - 0.40, x1=i - 0.05,
        y0=-0.30, y1=0.30,
        z0=0, z1=plan_mln,
        color="#B8A3DC",
        name=f"{row['Месяц']} · План: {plan_mln:.1f} М ₽",
    ))
    fig.add_trace(cuboid_mesh(
        x0=i + 0.05, x1=i + 0.40,
        y0=-0.30, y1=0.30,
        z0=0, z1=fact_mln,
        color="#9DD8BE" if fact_mln >= plan_mln else "#EFA9C0",
        name=f"{row['Месяц']} · Факт: {fact_mln:.1f} М ₽",
    ))
fig.update_layout(
    scene=dict(
        xaxis=dict(tickmode="array", tickvals=list(range(len(df))),
                   ticktext=df["Месяц"].tolist(), title=""),
        yaxis=dict(showticklabels=False, title=""),
        zaxis=dict(title="млн ₽"),
    ),
    showlegend=False,
)
style_plotly_3d(fig, height=460)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# Легенда вручную
st.markdown(
    """
    <div style="display:flex;gap:24px;justify-content:center;margin-top:-8px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:14px;height:14px;background:#B8A3DC;border-radius:4px;"></span>
        <span style="color:#4A4566;font-size:0.88rem;">План</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:14px;height:14px;background:#9DD8BE;border-radius:4px;"></span>
        <span style="color:#4A4566;font-size:0.88rem;">Факт (выполнен)</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:14px;height:14px;background:#EFA9C0;border-radius:4px;"></span>
        <span style="color:#4A4566;font-size:0.88rem;">Факт (недовыполнен)</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
chart_card_close()

# % выполнения
chart_card_open("Процент выполнения по месяцам", "Факт / План, %")
df_done = df.assign(**{
    "Выполнение %": (df["Факт"] / df["План"] * 100).round(1),
})
fig = go.Figure(go.Bar(
    x=df_done["Месяц"],
    y=df_done["Выполнение %"],
    marker=dict(
        color=["#9DD8BE" if v >= 100 else "#EFA9C0" if v < 90 else "#F0DBA0"
               for v in df_done["Выполнение %"]],
        line=dict(width=0),
    ),
    text=[f"{v:.1f}%" for v in df_done["Выполнение %"]],
    textposition="outside",
    textfont=dict(color=PALETTE["ink"], size=13),
    hovertemplate="<b>%{x}</b><br>Выполнение: %{y:.1f}%<extra></extra>",
    width=0.5,
))
# Линия 100%
fig.add_hline(y=100, line=dict(color=PALETTE["muted"], width=1, dash="dash"),
              annotation_text="100%", annotation_position="right",
              annotation_font_color=PALETTE["muted"])
style_plotly_2d(fig, height=320)
fig.update_layout(yaxis=dict(ticksuffix="%", showgrid=True),
                  xaxis=dict(showgrid=False))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# Таблица
chart_card_open("Детализация", "")
display = df.copy()
display["Отклонение"] = display["Факт"] - display["План"]
display["Выполнение, %"] = (display["Факт"] / display["План"] * 100).round(1).astype(str) + "%"
for col in ("План", "Факт", "Отклонение"):
    display[col] = display[col].apply(lambda v: format_money(v))
st.dataframe(display, use_container_width=True, hide_index=True)
chart_card_close()
