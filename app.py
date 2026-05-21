import streamlit as st

from components.styles import apply, hero

st.set_page_config(
    page_title="Дашборд ВЭД-агентства",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply()

hero(
    "Дашборд ВЭД-агентства",
    "Финансовые и операционные метрики · обновление каждые 5 минут",
)

st.markdown("### Доступные разделы")

cards = [
    ("📈", "PL общий", "Выручка, GP, операционная и чистая прибыль · PL GLOBAL", "#9B86C7"),
    ("🎯", "План vs Факт", "Факт vs Бюджет по месяцам · PL GLOBAL", "#7FC9A8"),
    ("👥", "Сегменты", "Бизнес-линии: клиенты, обороты, средний чек, маржинальность", "#E8B989"),
    ("💧", "Ликвидность", "Валютный gap T+0/T+1/T+2 · скоро (ждём доступ к файлу)", "#A9C9EE"),
]

cols = st.columns(2)
for i, (icon, title, desc, color) in enumerate(cards):
    with cols[i % 2]:
        st.markdown(
            f"""
            <div style="background:white;border:1px solid #E5E7EB;border-radius:16px;
                        padding:20px 22px;margin-bottom:14px;
                        box-shadow:0 1px 3px rgba(16,24,40,0.04);">
              <div style="display:flex;align-items:center;gap:14px;">
                <div style="font-size:28px;width:48px;height:48px;border-radius:12px;
                            background:{color}15;display:flex;align-items:center;
                            justify-content:center;">{icon}</div>
                <div>
                  <div style="font-weight:600;color:#1A1F36;font-size:1.02rem;">{title}</div>
                  <div style="color:#6B7280;font-size:0.85rem;margin-top:2px;">{desc}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("")
st.caption("👈 Выберите раздел в боковом меню слева. Источник данных: Google Sheets (демо-режим).")
