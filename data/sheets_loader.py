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


def pl_rows_value(rows: list[list[str]], row_list, month: int,
                  source: str = "fact", year: int = 2026) -> float:
    """Сумма значений по нескольким строкам PL за месяц (для статей из 2 частей)."""
    if source == "budget":
        col = PL_BUDGET_2026_COLS[month]
    elif year == 2026:
        col = PL_FACT_2026_COLS[month]
    else:
        col = PL_FACT_2025_COLS[month]
    return sum(parse_ru_number(_cell(rows, r, col)) for r in row_list)


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


# ============= МОНИТОРИНГ (по дате закрытия сделки) =============
import datetime as _dt

from config import (MON_DAILY_START_COL, MON_LINE_BLOCKS, MON_LINES,  # noqa: E402
                    MON_MONTH_TOTAL_COLS, MON_SUMMARY_ROWS)


def _find_row(rows: list[list[str]], expected: int, label: str, window: int = 4) -> int:
    """Находит строку с меткой `label` в колонке C около ожидаемой строки (устойчиво к сдвигам)."""
    if _cell(rows, expected, 3).strip() == label:
        return expected
    for r in range(max(1, expected - window), expected + window + 1):
        if _cell(rows, r, 3).strip() == label:
            return r
    return expected  # не нашли — вернём ожидаемую (лучше, чем падать)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def mon_daily_columns(rows: list[list[str]]) -> list[tuple[int, _dt.date]]:
    """Список (номер_колонки_1индекс, дата) для всех дневных колонок (с H)."""
    out: list[tuple[int, _dt.date]] = []
    header = rows[0] if rows else []
    for c in range(MON_DAILY_START_COL, len(header) + 1):
        raw = _cell(rows, 1, c).strip()
        try:
            d = _dt.datetime.strptime(raw, "%d/%m/%Y").date()
            out.append((c, d))
        except ValueError:
            continue
    return out


def mon_months_available(rows: list[list[str]]) -> list[int]:
    """Месяцы, по которым есть дневные данные (по датам в шапке)."""
    months = sorted({d.month for _, d in mon_daily_columns(rows)})
    return months


def mon_summary_daily(rows: list[list[str]], metric: str, month: int) -> list[tuple[_dt.date, float]]:
    """Дневной ряд сводной метрики за выбранный месяц: [(дата, значение), ...]."""
    meta = MON_SUMMARY_ROWS[metric]
    row = _find_row(rows, meta["row"], meta["label"])
    return [(d, parse_ru_number(_cell(rows, row, c)))
            for c, d in mon_daily_columns(rows) if d.month == month]


def mon_summary_monthly(rows: list[list[str]], metric: str, month: int) -> float:
    """Месячный итог сводной метрики строго из колонок D–G листа.

    Возвращает NaN, если итога нет (нет колонки итога — напр. июль; или ячейка пуста —
    напр. «Активные клиенты» за март–май). Не выдумываем сумму/среднее по дням.
    """
    meta = MON_SUMMARY_ROWS[metric]
    row = _find_row(rows, meta["row"], meta["label"])
    col = MON_MONTH_TOTAL_COLS.get(month)
    if col is None:
        return float("nan")
    raw = _cell(rows, row, col).strip()
    if raw == "" or raw.startswith("#"):   # пусто или ошибка формулы (#DIV/0! и т.п.)
        return float("nan")
    return parse_ru_number(raw)


def mon_line_breakdown(rows: list[list[str]], metric: str, month: int) -> dict[str, float]:
    """Разбивка метрики по 11 бизнес-линиям за месяц (месячный итог D–G)."""
    if metric not in MON_LINE_BLOCKS:
        return {}
    block = MON_LINE_BLOCKS[metric]
    header = _find_row(rows, block["header"], block["label"])
    col = MON_MONTH_TOTAL_COLS.get(month)
    out: dict[str, float] = {}
    # линии идут в строках ниже заголовка; ищем каждую по имени в колонке C
    for line in MON_LINES:
        target = None
        for r in range(header + 1, header + len(MON_LINES) + 3):
            if _cell(rows, r, 3).strip() == line:
                target = r
                break
        if target is None:
            out[line] = 0.0
            continue
        if col is not None:
            out[line] = parse_ru_number(_cell(rows, target, col))
        else:
            # июль: суммируем дневные значения линии
            out[line] = sum(parse_ru_number(_cell(rows, target, c))
                            for c, d in mon_daily_columns(rows) if d.month == month)
    return out


def mon_line_daily(rows: list[list[str]], metric: str, line: str,
                   month: int) -> list[tuple[_dt.date, float]]:
    """Дневной ряд метрики для ОДНОЙ бизнес-линии за месяц: [(дата, значение), ...]."""
    if metric not in MON_LINE_BLOCKS:
        return []
    block = MON_LINE_BLOCKS[metric]
    header = _find_row(rows, block["header"], block["label"])
    target = None
    for r in range(header + 1, header + len(MON_LINES) + 3):
        if _cell(rows, r, 3).strip() == line:
            target = r
            break
    cols = [(c, d) for c, d in mon_daily_columns(rows) if d.month == month]
    if target is None:
        return [(d, 0.0) for _, d in cols]
    return [(d, parse_ru_number(_cell(rows, target, c))) for c, d in cols]


# ============= СЕГМЕНТЫ: бюджет (2026 Ребюджет) / факт (Факт - прогноз) =============
from config import (SEG_BUDGET_COL, SEG_FACT_COL, SEG_MARGIN_ROWS,  # noqa: E402
                    SEG_MARGIN_TOTAL_ROW)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю Ребюджет…")
def load_rebudget_raw() -> list[list[str]]:
    return _open_sheet("rebudget").get_all_values()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю Факт-прогноз…")
def load_fact_forecast_raw() -> list[list[str]]:
    return _open_sheet("fact_forecast").get_all_values()


def seg_margin_budget(month: int) -> dict:
    """Бюджет маржи по сегментам за месяц (лист «2026 Ребюджет», N..Y)."""
    raw = load_rebudget_raw()
    col = SEG_BUDGET_COL[month]
    return {label: parse_ru_number(_cell(raw, r, col)) for r, label in SEG_MARGIN_ROWS}


def seg_margin_fact(month: int) -> dict:
    """Факт маржи по сегментам за месяц (лист «Факт - прогноз», W..AB)."""
    col = SEG_FACT_COL.get(month)
    if col is None:
        return {}
    raw = load_fact_forecast_raw()
    return {label: parse_ru_number(_cell(raw, r, col)) for r, label in SEG_MARGIN_ROWS}


def seg_margin_total(month: int, source: str) -> float:
    """Итог маржи (строка 5) за месяц: source='budget' | 'fact'."""
    if source == "budget":
        raw, col = load_rebudget_raw(), SEG_BUDGET_COL.get(month)
    else:
        raw, col = load_fact_forecast_raw(), SEG_FACT_COL.get(month)
    if col is None:
        return 0.0
    return parse_ru_number(_cell(raw, SEG_MARGIN_TOTAL_ROW, col))


def seg_fact_months() -> list:
    """Месяцы (1..6), где в Факт-прогнозе есть фактический итог маржи."""
    raw = load_fact_forecast_raw()
    return [m for m, col in SEG_FACT_COL.items()
            if parse_ru_number(_cell(raw, SEG_MARGIN_TOTAL_ROW, col)) != 0]


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
            "Оборот, млн $": [58, 42, 14, 22, 28],
        })
    return pd.DataFrame()


def load(key: str, use_stub: bool = True) -> pd.DataFrame:
    if use_stub:
        return load_stub(key)
    return load_stub(key)
