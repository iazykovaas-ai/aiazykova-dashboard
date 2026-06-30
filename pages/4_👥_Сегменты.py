import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.glossary import PAGE_SEG, render_abbr_expander
from components.kpi import format_money
from components.styles import (CHART_COLORS, PALETTE, apply,
                               chart_card_close, chart_card_open, cuboid_mesh,
                               hero, style_plotly_2d, style_plotly_3d)
from data.sheets_loader import load

st.set_page_config(page_title="Клиенты по типам", page_icon="👥", layout="wide")
apply()
render_assistant()

hero("👥 Клиенты по типам", "14 типов клиентов · обороты и количество")

render_abbr_expander(PAGE_SEG)

df = load("clients", use_stub=True)
df["Оборот, $"] = df["Оборот, млн $"] * 1_000_000

total_clients = df["Кол-во"].sum()
total_turnover = df["Оборот, $"].sum()
avg_check = total_turnover / total_clients if total_clients else 0
top_type = df.loc[df["Оборот, млн $"].idxmax(), "Тип"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Всего клиентов", f"{total_clients}")
c2.metric("Типов клиентов", f"{len(df)}")
c3.metric("Средний оборот / клиент", format_money(avg_check))
c4.metric("Топ-тип по обороту", top_type)

st.markdown("")

# 3D bar: оборот по типам клиентов
chart_card_open("Оборот по типам клиентов", "3D · млн $")
df_sorted = df.sort_values("Оборот, млн $", ascending=False).reset_index(drop=True)
fig = go.Figure()
for i, (_, row) in enumerate(df_sorted.iterrows()):
    color = CHART_COLORS[i % len(CHART_COLORS)]
    fig.add_trace(cuboid_mesh(
        x0=i - 0.35, x1=i + 0.35,
        y0=-0.35, y1=0.35,
        z0=0, z1=row["Оборот, млн $"],
        color=color,
        name=f"{row['Тип']}: {row['Оборот, млн $']:.1f} млн $ · {row['Кол-во']} клиентов",
    ))
fig.update_layout(
    scene=dict(
        xaxis=dict(tickmode="array", tickvals=list(range(len(df_sorted))),
                   ticktext=df_sorted["Тип"].tolist(), title=""),
        yaxis=dict(showticklabels=False, title=""),
        zaxis=dict(title="млн $"),
    ),
    showlegend=False,
)
style_plotly_3d(fig, height=480)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
chart_card_close()

# Количество и средний чек
left, right = st.columns([1, 1])

with left:
    chart_card_open("Количество клиентов по типам", "клиентов")
    df_cnt = df.sort_values("Кол-во", ascending=True)
    fig = go.Figure(go.Bar(
        x=df_cnt["Кол-во"], y=df_cnt["Тип"], orientation="h",
        marker=dict(
            color=df_cnt["Кол-во"],
            colorscale=[[0, "#1B3A6B"], [1, "#36C5F0"]],
            line=dict(width=0),
        ),
        text=df_cnt["Кол-во"],
        textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        hovertemplate="<b>%{y}</b><br>%{x} клиентов<extra></extra>",
    ))
    style_plotly_2d(fig, height=400)
    fig.update_layout(xaxis=dict(showgrid=True, showticklabels=False),
                      yaxis=dict(showgrid=False))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()

with right:
    chart_card_open("Средний оборот на клиента", "млн $ / клиент")
    df_avg = df.assign(**{
        "Средний": (df["Оборот, млн $"] / df["Кол-во"]).round(2),
    }).sort_values("Средний", ascending=True)
    fig = go.Figure(go.Bar(
        x=df_avg["Средний"], y=df_avg["Тип"], orientation="h",
        marker=dict(
            color=df_avg["Средний"],
            colorscale=[[0, "#16513E"], [1, "#2FD9A6"]],
            line=dict(width=0),
        ),
        text=[f"{v:.2f}" for v in df_avg["Средний"]],
        textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=12),
        hovertemplate="<b>%{y}</b><br>%{x:.2f} млн $ / клиент<extra></extra>",
    ))
    style_plotly_2d(fig, height=400)
    fig.update_layout(xaxis=dict(showgrid=True, showticklabels=False),
                      yaxis=dict(showgrid=False))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()

# Таблица
chart_card_open("Детализация", "")
display = df.sort_values("Оборот, млн $", ascending=False).copy()
display["Средний оборот"] = (display["Оборот, $"] / display["Кол-во"]).apply(format_money)
display["Оборот"] = display["Оборот, $"].apply(format_money)
display = display[["Тип", "Кол-во", "Оборот", "Средний оборот"]]
st.dataframe(display, use_container_width=True, hide_index=True)
chart_card_close()
