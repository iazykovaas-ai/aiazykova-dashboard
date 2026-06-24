import streamlit as st

from components.assistant import render_assistant
from components.styles import apply, hero

st.set_page_config(
    page_title="Дашборд ВЭД-агентства",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply()
render_assistant()

hero(
    "Дашборд ВЭД-агентства",
    "Финансовые и операционные метрики · обновление каждые 5 минут",
)

st.markdown("### Доступные разделы")

cards = [
    ("📈", "PL общий", "Выручка, GP, операционная и чистая прибыль · PL GLOBAL", "#7B6FF0"),
    ("🎯", "План vs Факт", "Факт vs Бюджет по месяцам · PL GLOBAL", "#2FD9A6"),
    ("👥", "Сегменты", "Бизнес-линии: клиенты, обороты, средний чек, маржинальность", "#F5B544"),
    ("💧", "Ликвидность", "Валютный gap T+0/T+1/T+2 · скоро (ждём доступ к файлу)", "#36C5F0"),
]

cols = st.columns(2)
for i, (icon, title, desc, color) in enumerate(cards):
    with cols[i % 2]:
        st.markdown(
            f"""
            <div style="background:linear-gradient(160deg,rgba(22,28,55,0.92),rgba(16,22,44,0.92));
                        border:1px solid rgba(255,255,255,0.07);border-radius:16px;
                        padding:20px 22px;margin-bottom:14px;
                        box-shadow:0 8px 26px rgba(0,0,0,0.32),inset 0 1px 0 rgba(255,255,255,0.03);">
              <div style="display:flex;align-items:center;gap:14px;">
                <div style="font-size:28px;width:48px;height:48px;border-radius:12px;
                            background:{color}26;border:1px solid {color}55;
                            box-shadow:0 0 18px {color}33;display:flex;align-items:center;
                            justify-content:center;">{icon}</div>
                <div>
                  <div style="font-weight:600;color:#F2F3FA;font-size:1.02rem;">{title}</div>
                  <div style="color:#8A90B8;font-size:0.85rem;margin-top:2px;">{desc}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("")
st.caption("👈 Выберите раздел в боковом меню слева. Источник данных: Google Sheets (демо-режим).")
