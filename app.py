import streamlit as st

from components.assistant import render_assistant
from components.styles import apply, hero

st.set_page_config(
    page_title="Дэшборд ВЭД-агентства",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply()
render_assistant()

hero(
    "Дэшборд ВЭД-агентства",
    "Финансовые и операционные метрики · данные обновляются при входе (и не реже раза в час)",
)

st.markdown("### Доступные разделы")

# Кликабельные карточки-ссылки на разделы (реальная навигация по страницам)
cards = [
    ("📅", "Мониторинг", "Дневная динамика по дате закрытия сделки: оборот, маржа, сделки",
     "pages/0_📅_Мониторинг.py", "#E94FA1"),
    ("🧾", "Сделки", "Каналы и продукты по клиентским сделкам: оборот, маржа, чистая прибыль",
     "pages/1_🧾_Сделки.py", "#F5B544"),
    ("🤝", "Доходность агентов", "По каждому агенту: оборот, маржа, наша комиссия и выплаты",
     "pages/2_🤝_Агенты.py", "#36C5F0"),
    ("📈", "Финансовые результаты", "Выручка, GP, операционная и чистая прибыль · PL GLOBAL",
     "pages/3_📈_Финансовые_результаты.py", "#7B6FF0"),
    ("📊", "Анализ отклонений", "Факт vs План и vs прошлый период · разбор по факторам",
     "pages/4_📊_Анализ_отклонений.py", "#2FD9A6"),
]

cols = st.columns(2)
for i, (icon, title, desc, page, color) in enumerate(cards):
    with cols[i % 2]:
        with st.container(border=True):
            st.page_link(page, label=f"{title}", icon=icon)
            st.caption(desc)

st.markdown("")
st.caption("👆 Нажмите на раздел выше или выберите в меню слева. "
           "Источник данных: Google Sheets.")
