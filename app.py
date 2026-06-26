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
    "Финансовые и операционные метрики · обновление каждые 5 минут",
)

st.markdown("### Доступные разделы")

# Кликабельные карточки-ссылки на разделы (реальная навигация по страницам)
cards = [
    ("📈", "PL общий", "Выручка, GP, операционная и чистая прибыль · PL GLOBAL",
     "pages/1_📈_PL_общий.py", "#7B6FF0"),
    ("🎯", "План vs Факт", "Факт vs Бюджет по месяцам · PL GLOBAL",
     "pages/2_🎯_Plan_Fact.py", "#2FD9A6"),
    ("👥", "Сегменты", "Бизнес-линии: клиенты, обороты, средний чек, маржинальность",
     "pages/4_👥_Clients.py", "#F5B544"),
    ("💧", "Ликвидность", "Валютный gap T+0/T+1/T+2 · скоро (ждём доступ к файлу)",
     "pages/3_💧_Liquidity.py", "#36C5F0"),
    ("📅", "Мониторинг", "Дневная динамика по дате закрытия сделки: оборот, маржа, сделки",
     "pages/5_📅_Мониторинг.py", "#E94FA1"),
    ("📊", "Факторный анализ", "Бюджет/Факт и Период/Период — что развело план и факт",
     "pages/6_📊_Факторный_анализ.py", "#4A7DFF"),
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
