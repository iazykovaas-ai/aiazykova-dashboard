from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from config import (CACHE_TTL_SECONDS, PL_BUDGET_2026_COLS, PL_FACT_2025_COLS,
                    PL_FACT_2026_COLS, PL_ROWS, SERVICE_ACCOUNT_FILE,
                    SHEETS, SPREADSHEET_ID)


def _get_client():
    """Подключение к Google Sheets.

    Приоритет источников ключа:
    1. st.secrets["gcp_service_account"] (для Streamlit Cloud)
    2. Локальный файл SERVICE_ACCOUNT_FILE (для запуска на компьютере)
    """
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    # Streamlit Cloud: ключ хранится в Secrets как словарь
    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE),
                                                      scopes=scopes)
    return gspread.authorize(creds)


def parse_ru_number(s: Any) -> float:
    """Парсит '41 871,8' / '-30%' / '' → float (или 0.0)."""
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip()
    if not txt or txt in {"-", "✓", "#VALUE!"}:
        return 0.0
    # Уберём % и пробелы (включая неразрывные)
    is_pct = txt.endswith("%")
    txt = txt.rstrip("%").replace(" ", "").replace(" ", "").replace(",", ".")
    # Если осталось что-то нечисловое (типа "fill in"), вернём 0
    if not re.match(r"^-?\d+(\.\d+)?$", txt):
        return 0.0
    val = float(txt)
    if is_pct:
        val = val / 100
    return val


@st.cache_resource(show_spinner=False)
def _open_sheet(sheet_key: str):
    client = _get_client()
    cfg = SHEETS[sheet_key]
    return client.open_by_key(cfg["spreadsheet_id"]).worksheet(cfg["worksheet"])


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю PL GLOBAL…")
def load_pl_global_raw() -> list[list[str]]:
    """Возвращает все ячейки PL GLOBAL как сырой список списков."""
    ws = _open_sheet("pl_global")
    return ws.get_all_values()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю Бизнес-блок…")
def load_business_block_raw() -> list[list[str]]:
    ws = _open_sheet("business_block")
    return ws.get_all_values()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю Мониторинг…")
def load_monitoring_raw() -> list[list[str]]:
    """Лист «Мониторинг по дате закрытия сделки» из таблицы Мониторинг."""
    ws = _open_sheet("monitoring")
    return ws.get_all_values()


def _cell(rows: list[list[str]], r: int, c: int) -> str:
    """1-индексированный доступ к ячейке (как в Sheets). Безопасно для outofrange."""
    if r - 1 < 0 or r - 1 >= len(rows):
        return ""
    row = rows[r - 1]
    if c - 1 < 0 or c - 1 >= len(row):
        return ""
    return row[c - 1]


def pl_value(rows: list[list[str]], metric: str, month: int, source: str = "fact",
             year: int = 2026) -> float:
    """Получить значение метрики P&L за конкретный месяц.

    metric  — ключ из PL_ROWS ('revenue', 'gross_profit', 'net_profit', ...)
    month   — 1..12
    source  — 'fact' | 'budget'
    year    — 2025 | 2026 (для факта)
    """
    row = PL_ROWS[metric]
    if source == "budget":
        col = PL_BUDGET_2026_COLS[month]
    elif source == "fact" and year == 2026:
        col = PL_FACT_2026_COLS[month]
    elif source == "fact" and year == 2025:
        col = PL_FACT_2025_COLS[month]
    else:
        raise ValueError(f"Unknown source/year: {source}/{year}")
    return parse_ru_number(_cell(rows, row, col))


def pl_series(rows: list[list[str]], metric: str, source: str = "fact",
              year: int = 2026, months: int = 12) -> list[float]:
    """Серия значений за 1..months месяцев."""
    return [pl_value(rows, metric, m, source, year) for m in range(1, months + 1)]


# ============= БИЗНЕС-БЛОК =============
# Структура листа: каждая таблица начинается со строки с тегом ("Активные клиенты", "Оборот", "Кол-во сделок", "Средний чек", "Маржинальная прибыль", "Маржинальность"),
# затем шапка месяцев (Jan25 ... Dec26), затем строки по Business Line, заканчивая Total и Прирост.

BB_TABLES = {
    "active_clients": {"label": "Активные клиенты", "row_start": 4},   # шапка на строке 4, данные с 5
    "turnover": {"label": "Оборот", "row_start": 41},                  # шапка на 41, данные с 42
    "deals_count": {"label": "Кол-во сделок", "row_start": 84},
    "avg_check": {"label": "Средний чек", "row_start": 102},
    "marginal_profit": {"label": "Маржинальная прибыль", "row_start": 125},
    "marginality": {"label": "Маржинальность", "row_start": 144},
}

# Business Lines (порядок такой же, как в листе)
BUSINESS_LINES = ["Bank opt_import", "Direct opt_import", "Bank import", "Direct import",
                  "Exchange", "Export", "Partner", "Special", "Dealing", "Sber", "Sberexp"]

# В шапке таблицы колонки: A=Business Line, B..M = Jan25..Dec25, N..Y = Jan26..Dec26
# 1-индекс: B=2 ... M=13 (2025), N=14 ... Y=25 (2026)
BB_COL_2025 = {m: 1 + m for m in range(1, 13)}    # Jan25=2, Dec25=13
BB_COL_2026 = {m: 13 + m for m in range(1, 13)}   # Jan26=14, Dec26=25


def bb_value(rows: list[list[str]], table: str, line: str, month: int, year: int) -> float:
    """Значение из таблицы Бизнес-блок для конкретной бизнес-линии, месяца, года."""
    header_row = BB_TABLES[table]["row_start"]
    # Найдём строку с нужной линией ниже шапки (в пределах следующих 20 строк)
    target_row = None
    for r in range(header_row + 1, header_row + 25):
        if _cell(rows, r, 1).strip() == line:
            target_row = r
            break
    if target_row is None:
        return 0.0
    col = (BB_COL_2025 if year == 2025 else BB_COL_2026)[month]
    return parse_ru_number(_cell(rows, target_row, col))


def bb_dataframe(rows: list[list[str]], table: str, year: int = 2026) -> pd.DataFrame:
    """Полная таблица: строки=бизнес-линии, колонки=месяцы."""
    cols = BB_COL_2025 if year == 2025 else BB_COL_2026
    out: dict[str, list[float]] = {}
    for line in BUSINESS_LINES:
        out[line] = [bb_value(rows, table, line, m, year) for m in range(1, 13)]
    df = pd.DataFrame(out, index=list(range(1, 13))).T
    df.index.name = "Business Line"
    return df


# ============= СТАБ (на случай отсутствия доступа) =============
def load_stub(key: str) -> pd.DataFrame:
    """Минимальные демо-данные."""
    if key == "pl":
        return pd.DataFrame({
            "Направление": ["Import", "Export", "Conversion", "Exchange", "Special"],
            "Выручка": [58e6, 42e6, 28e6, 14e6, 6e6],
            "Себестоимость": [38e6, 28e6, 18e6, 9e6, 4e6],
            "Маржа": [20e6, 14e6, 10e6, 5e6, 2e6],
        })
    if key == "plan_fact":
        return pd.DataFrame({
            "Месяц": ["Январь", "Февраль", "Март", "Апрель"],
            "План": [45e6, 48e6, 50e6, 52e6],
            "Факт": [47.5e6, 46e6, 51e6, 0],
        })
    if key == "liquidity":
        return pd.DataFrame({
            "Срок": ["T+0", "T+1", "T+2"],
            "Потребность, USD": [1.2e6, 0.8e6, 0.45e6],
            "Доступно, USD": [0.9e6, 0.75e6, 0.6e6],
        })
    if key == "clients":
        return pd.DataFrame({
            "Тип": ["Import", "Export", "Exchange", "Special", "Conversion"],
            "Кол-во": [28, 19, 12, 9, 7],
            "Оборот, М ₽": [58, 42, 14, 22, 28],
        })
    return pd.DataFrame()


def load(key: str, use_stub: bool = True) -> pd.DataFrame:
    if use_stub:
        return load_stub(key)
    return load_stub(key)
