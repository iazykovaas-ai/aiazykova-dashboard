import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.styles import (PALETTE, apply, chart_card_close,
                               chart_card_open, cuboid_mesh, hero,
                               style_plotly_2d, style_plotly_3d)
from data.sheets_loader import load

st.set_page_config(page_title="Потребность в ликвидности", page_icon="💧", layout="wide")
apply()
render_assistant()

hero("💧 Потребность в ликвидности", "Валютный gap по срокам T+0 / T+1 / T+2 (USD)")


def fmt_usd(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f} M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.0f} K"
    return f"${v:.0f}"


df = load("liquidity", use_stub=True)
df["Gap"] = df["Доступно, USD"] - df["Потребность, USD"]

total_need = df["Потребность, USD"].sum()
total_avail = df["Доступно, USD"].sum()
total_gap = total_avail - total_need

c1, c2, c3, c4 = st.columns(4)
c1.metric("Общая потребность", fmt_usd(total_need))
c2.metric("Доступно", fmt_usd(total_avail))
c3.metric("Gap", fmt_usd(total_gap), f"{total_gap / total_need * 100:+.1f}%" if total_need else "—")
c4.metric("Самый дефицитный срок",
          df.loc[df["Gap"].idxmin(), "Срок"],
          fmt_usd(df["Gap"].min()))

st.markdown("")

# 3D-стек: Потребность vs Доступно по T+
chart_card_open("Потребность vs Доступно по срокам", "3D · USD")
fig = go.Figure()
for i, (_, row) in enumerate(df.iterrows()):
    need_m = row["Потребность, USD"] / 1_000_000
    avail_m = row["Доступно, USD"] / 1_000_000
    fig.add_trace(cuboid_mesh(
        x0=i - 0.40, x1=i - 0.05,
        y0=-0.30, y1=0.30,
        z0=0, z1=need_m,
        color="#EFA9C0",
        name=f"{row['Срок']} · Потребность: {fmt_usd(row['Потребность, USD'])}",
    ))
    fig.add_trace(cuboid_mesh(
        x0=i + 0.05, x1=i + 0.40,
        y0=-0.30, y1=0.30,
        z0=0, z1=avail_m,
        color="#9DD8BE",
        name=f"{row['Срок']} · Доступно: {fmt_usd(row['Доступно, USD'])}",
    ))
fig.update_layout(
    scene=dict(
        xaxis=dict(tickmode="array", tickvals=list(range(len(df))),
                   ticktext=df["Срок"].tolist(), title=""),
        yaxis=dict(showticklabels=False, title=""),
        zaxis=dict(title="млн $"),
    ),
    showlegend=False,
)
style_plotly_3d(fig, height=460)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
st.markdown(
    """
    <div style="display:flex;gap:24px;justify-content:center;margin-top:-8px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:14px;height:14px;background:#EFA9C0;border-radius:4px;"></span>
        <span style="color:#B6BCE4;font-size:0.88rem;">Потребность</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:14px;height:14px;background:#9DD8BE;border-radius:4px;"></span>
        <span style="color:#B6BCE4;font-size:0.88rem;">Доступно</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
chart_card_close()

# Gap waterfall
chart_card_open("Gap по срокам", "Доступно − Потребность")
colors = ["#9DD8BE" if g >= 0 else "#EFA9C0" for g in df["Gap"]]
fig = go.Figure(go.Bar(
    x=df["Срок"], y=df["Gap"] / 1_000_000,
    marker=dict(color=colors, line=dict(width=0)),
    text=[fmt_usd(v) for v in df["Gap"]],
    textposition="outside",
    textfont=dict(color=PALETTE["ink"], size=13),
    hovertemplate="<b>%{x}</b><br>Gap: %{text}<extra></extra>",
    width=0.5,
))
fig.add_hline(y=0, line=dict(color=PALETTE["muted"], width=1))
style_plotly_2d(fig, height=320)
fig.update_layout(yaxis=dict(title="млн $"), xaxis=dict(showgrid=False))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# Таблица
chart_card_open("Детализация", "")
display = df.copy()
for col in ("Потребность, USD", "Доступно, USD", "Gap"):
    display[col] = display[col].apply(fmt_usd)
st.dataframe(display, use_container_width=True, hide_index=True)
chart_card_close()
