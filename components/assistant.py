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

from components.glossary import ABBR

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
                     "plan", "fact", "квартал", "факторн", "мостик", "что развело",
                     "изменение прибыли", "вклад", "период к период"],
        "page": "pages/2_📊_Анализ_отклонений.py",
        "title": "📊 Анализ отклонений",
        "answer": "Это раздел **Анализ отклонений**: факт против плана (План vs Факт) и против "
                  "прошлого периода (Период к периоду), с разбором по факторам/сегментам и кратким выводом.",
    },
    {
        "keywords": ["клиент", "сегмент", "бизнес-лин", "бизнес лин", "business line",
                     "средний чек", "маржинальн", "импорт", "экспорт", "exchange",
                     "dealing", "sber", "доля", "кол-во сделок", "сделк"],
        "page": "pages/4_👥_Сегменты.py",
        "title": "👥 Сегменты (в работе)",
        "answer": "Это раздел **Сегменты** (пока в разработке): бизнес-линии (импорт, экспорт, "
                  "обмен и др.) — число активных клиентов, обороты, средний чек и маржинальность.",
    },
    {
        "keywords": ["мониторинг", "по дням", "дневн", "по дате", "закрыти", "ежедневн",
                     "срок оплаты", "триггерн", "переоценк", "динамика по дням", "за день",
                     "по линиям", "линиям", "бизнес-лин", "бизнес лин", "по сегмент",
                     "светофор", "тепловая карта", "теплова",
                     "bank", "direct", "sber", "сбер", "dealing", "дилинг", "partner", "партнёр",
                     "opt_import", "опт. импорт", "оборот по дням"],
        "page": "pages/0_📅_Мониторинг.py",
        "title": "📅 Мониторинг",
        "answer": "Это раздел **Мониторинг**: дневная динамика по дате закрытия сделки — "
                  "оборот, маржинальная прибыль, маржинальность, средний чек, число сделок и "
                  "активные клиенты по дням и по бизнес-линиям (Опт. банки, Прямой импорт, "
                  "Конвертация, Sber импорт/экспорт, Экспорт, Партнёры, Дилинг и др.). "
                  "Сегмент, метрику и месяц выбираете вверху; есть тепловая карта и светофор.",
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

# Подтягиваем единый словарь аббревиатур (components/glossary.ABBR) в глоссарий навигатора,
# не затирая более подробные ручные определения выше (setdefault).
_ABBR_TRIGGERS = {
    "opex": "OPEX", "gross": "GP", "валов": "GP", "pbt": "PBT", "p&l": "PL",
    "waterfall": "Waterfall", "каскад": "Waterfall", "мостик": "Waterfall",
    "treemap": "Treemap", "плитк": "Treemap", "n/m": "nm", "версус": "vs",
    "other": "OAG", "agent": "OAG", "gold": "OAG", "агентск": "OAG", "золото": "OAG",
    "fx": "FX", "g&a": "GA", "g & a": "GA", "revenue": "Revenue", "выручк": "Revenue",
    "net": "Net", "чист": "Net", "yoy": "YoY", "mom": "MoM", "ytd": "YTD",
    "turnover": "Turnover", "маржинальная приб": "MP", "марж. приб": "MP",
    "средний чек": "avgcheck", "операционная приб": "OperatingProfit",
    "п.п": "pp", "проц. пункт": "pp",
}
for _trig, _key in _ABBR_TRIGGERS.items():
    _term, _expl = ABBR[_key]
    GLOSSARY.setdefault(_trig, f"**{_term}** — {_expl}")

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

    return {"text": "Не нашёл точного раздела 🤔 Я знаю про: **Финансовые результаты**, **Анализ отклонений**, "
                   "**Сегменты** и **Мониторинг**. Попробуйте переформулировать — например, "
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
