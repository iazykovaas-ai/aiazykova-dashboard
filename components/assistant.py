"""Правиловый ИИ-навигатор по дашборду.

Без внешнего ИИ: понимает вопрос по ключевым словам и
— ведёт на нужный раздел (st.page_link),
— объясняет метрику из встроенного глоссария,
— подсказывает, что вообще можно спросить.

Подключается на каждой странице вызовом render_assistant() — рисуется в сайдбаре.
"""
from __future__ import annotations

import re

import streamlit as st

# ---- Карта тем: (ключевые слова) -> раздел дашборда + короткий ответ ----
# page — путь относительно главного скрипта app.py (для st.page_link / switch_page)
TOPICS = [
    {
        "keywords": ["выручк", "revenue", "оборот", "turnover", "валов", "gp", "gross",
                     "opex", "расход", "прибыл", "net", "чист", "операционн", "pbt",
                     "налог", "переоценк", "fx", "waterfall", "ebit", "p&l", "pl",
                     "доход", "себестоимост", "маржинальност по месяц"],
        "page": "pages/1_📈_Финансовые_результаты.py",
        "title": "📈 Финансовые результаты",
        "answer": "Это в разделе **Финансовые результаты** — там выручка, валовая / операционная / чистая "
                  "прибыль, структура OPEX, waterfall от выручки до прибыли и маржинальность "
                  "по месяцам. Период можно выбрать вверху страницы.",
    },
    {
        "keywords": ["план", "факт", "бюджет", "ребюджет", "выполнен", "отклонен",
                     "plan", "fact", "квартал"],
        "page": "pages/2_🎯_Plan_Fact.py",
        "title": "🎯 План vs Факт",
        "answer": "Смотри раздел **План vs Факт**: факт против бюджета по месяцам, "
                  "процент выполнения и отклонение. План квартала = Бюджет(M1) + Бюджет(M2) + Ребюджет(M3).",
    },
    {
        "keywords": ["клиент", "сегмент", "бизнес-лин", "бизнес лин", "business line",
                     "средний чек", "маржинальн", "импорт", "экспорт", "exchange",
                     "dealing", "sber", "доля", "кол-во сделок", "сделк"],
        "page": "pages/4_👥_Clients.py",
        "title": "👥 Сегменты",
        "answer": "Это раздел **Сегменты**: бизнес-линии (импорт, экспорт, обмен и др.) — "
                  "число активных клиентов, обороты, средний чек и маржинальность по каждой линии.",
    },
    {
        "keywords": ["ликвидн", "gap", "гэп", "валютн", "t+0", "t+1", "t+2", "дефицит",
                     "потребност", "доступно", "usd"],
        "page": "pages/3_💧_Liquidity.py",
        "title": "💧 Ликвидность",
        "answer": "Это раздел **Ликвидность**: валютный gap по срокам T+0 / T+1 / T+2 — "
                  "сколько валюты нужно под заявки и сколько доступно.",
    },
    {
        "keywords": ["факторн", "бюджет факт", "план факт", "отклонен", "мостик",
                     "что развело", "изменение прибыли", "вклад", "период к период"],
        "page": "pages/6_📊_План_-_Факт.py",
        "title": "📊 План - Факт",
        "answer": "Это раздел **План - Факт**: два мостика — «Бюджет → Факт» (что развело "
                  "план и факт по статьям/сегментам) и «Прошлый → Текущий период» (что изменилось). "
                  "Видно вклад каждого фактора в отклонение.",
    },
    {
        "keywords": ["мониторинг", "по дням", "дневн", "по дате", "закрыти", "ежедневн",
                     "срок оплаты", "триггерн", "переоценк", "динамика по дням", "за день"],
        "page": "pages/5_📅_Мониторинг.py",
        "title": "📅 Мониторинг",
        "answer": "Это раздел **Мониторинг**: дневная динамика по дате закрытия сделки — "
                  "оборот, маржинальная прибыль, маржинальность, средний чек, число сделок и "
                  "активные клиенты по дням и по бизнес-линиям. Метрику и месяц выбираете вверху.",
    },
]

# ---- Глоссарий метрик ----
GLOSSARY = {
    "opex": "**OPEX** (Operating Expenses) — операционные (текущие) расходы: ПО и ИТ, маркетинг, "
            "персонал, аренда, консалтинг, юристы и пр.",
    "gp": "**GP / Gross Profit** — валовая прибыль = Выручка − Прямые расходы.",
    "валов": "**Валовая прибыль (GP)** = Выручка − Прямые расходы.",
    "маржинальност": "**Маржинальность** — отношение прибыли к обороту, в %. Показывает, "
                     "сколько компания зарабатывает с каждого доллара оборота.",
    "средний чек": "**Средний чек** — средний оборот на одну сделку (или на клиента) за период.",
    "чист": "**Чистая прибыль (Net Profit)** — прибыль после уплаты налога; нижняя строка P&L.",
    "операционн": "**Операционная прибыль** = Валовая прибыль − OPEX (± валютные переоценки).",
    "pbt": "**PBT (Profit Before Tax)** — прибыль до налогообложения.",
    "gap": "**Gap (валютный)** — нехватка валюты под оплату заявок: Доступно − Потребность по сроку.",
    "t+0": "**T+0 / T+1 / T+2** — срок от заявки клиента до оплаты: сегодня, +1, +2 дня.",
    "yoy": "**YoY (Year-over-Year)** — изменение к тому же периоду прошлого года.",
    "mom": "**MoM (Month-over-Month)** — изменение к предыдущему месяцу.",
    "ytd": "**YTD (Year-to-Date)** — накопительно с начала года.",
    "ребюджет": "**Ребюджет** — пересмотренный бюджет на 3-й месяц квартала (M3) с учётом факта первых месяцев.",
    "переоценк": "**Переоценка** — изменение стоимости валютных активов/пассивов из-за курса (нереализованный FX).",
}

QUICK = [
    "Где посмотреть чистую прибыль?",
    "Что такое OPEX?",
    "Как смотреть план и факт?",
    "Где данные по клиентам?",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def answer_query(query: str) -> dict:
    """Возвращает {'text': str, 'page': str|None, 'title': str|None}."""
    q = _norm(query)
    if not q:
        return {"text": "Спросите, например: «где выручка?» или «что такое маржинальность?»",
                "page": None, "title": None}

    # Приветствие
    if re.fullmatch(r"(привет|здравствуй\w*|хай|hello|hi|добрый день|доброе утро|здаров\w*)[!. ]*", q):
        return {"text": "Привет! Я помогу найти нужный раздел дашборда. "
                        "Спросите про выручку, прибыль, план/факт, клиентов или ликвидность.",
                "page": None, "title": None}

    # Сначала — определения («что такое…», «что значит…»)
    if any(p in q for p in ["что такое", "что значит", "объясни", "расшифр", "что это"]):
        for key, definition in GLOSSARY.items():
            if key in q:
                return {"text": definition, "page": None, "title": None}

    # Навигация: ищем тему с максимумом совпадений ключевых слов
    best, best_hits = None, 0
    for topic in TOPICS:
        hits = sum(1 for kw in topic["keywords"] if kw in q)
        if hits > best_hits:
            best, best_hits = topic, hits
    if best:
        return {"text": best["answer"], "page": best["page"], "title": best["title"]}

    # Определение без явного «что такое»
    for key, definition in GLOSSARY.items():
        if key in q:
            return {"text": definition, "page": None, "title": None}

    return {"text": "Не нашёл точного раздела 🤔 Я знаю про: **PL общий**, **План vs Факт**, "
                   "**Сегменты** и **Ликвидность**. Попробуйте переформулировать — например, "
                   "«где оборот по клиентам?»",
            "page": None, "title": None}


def _handle(query: str) -> None:
    st.session_state.assistant_history.append(("user", query))
    res = answer_query(query)
    st.session_state.assistant_history.append(("bot", res))


def render_assistant() -> None:
    """Рисует ИИ-навигатор в сайдбаре. Вызывать на каждой странице."""
    if "assistant_history" not in st.session_state:
        st.session_state.assistant_history = [
            ("bot", {"text": "👋 Я ИИ-навигатор по дашборду. Спросите, где что посмотреть, "
                            "или что означает метрика.", "page": None, "title": None}),
        ]

    with st.sidebar:
        st.markdown("---")
        st.markdown(
            "<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;'>"
            "<span style='font-size:20px;'>🤖</span>"
            "<span style='font-weight:600;color:#F2F3FA;'>ИИ-навигатор</span></div>",
            unsafe_allow_html=True,
        )

        # Быстрые кнопки-подсказки
        for i, q in enumerate(QUICK):
            if st.button(q, key=f"quick_{i}", use_container_width=True):
                _handle(q)
                st.rerun()

        # История диалога
        for role, payload in st.session_state.assistant_history[-6:]:
            if role == "user":
                st.markdown(
                    f"<div style='background:rgba(123,111,240,0.18);border:1px solid "
                    f"rgba(123,111,240,0.35);border-radius:12px 12px 2px 12px;padding:8px 12px;"
                    f"margin:6px 0 6px 28px;color:#E8EAF6;font-size:0.86rem;'>{payload}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='background:rgba(20,26,51,0.85);border:1px solid "
                    f"rgba(255,255,255,0.07);border-radius:12px 12px 12px 2px;padding:8px 12px;"
                    f"margin:6px 28px 6px 0;color:#C7CCEC;font-size:0.86rem;'>{payload['text']}</div>",
                    unsafe_allow_html=True,
                )
                if payload.get("page"):
                    st.page_link(payload["page"], label=f"Перейти → {payload['title']}",
                                 use_container_width=True)

        # Поле ввода
        q = st.chat_input("Спросите навигатора…", key="assistant_input")
        if q:
            _handle(q)
            st.rerun()
