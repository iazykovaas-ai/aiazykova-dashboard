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


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def pl_month_maps() -> dict:
    """Карты {месяц: колонка} блоков PL GLOBAL — определяются ПО ШАПКЕ (маркеры «-MM-» в
    строке 2), а не хардкодом. Лист периодически «пакуют» (у закрытых месяцев убирают
    M2M-колонки), из-за чего фиксированные номера съезжают и факт/бюджет читаются не из тех
    столбцов. Возвращает {'fact2025','fact2026','budget2026': {month: col}}.

    Логика: актуалы (Jan-2025…Dec-2026) идут одним непрерывным рядом (годы разделяем по сбросу
    номера месяца 12→1, допускаем одиночные M2M-колонки как разрыв ≤2); бюджет — отдельный
    12-месячный ряд. Что не распозналось — берётся из config (fallback в _pl_col)."""
    rows = load_pl_global_raw()
    r2 = rows[1] if len(rows) > 1 else []
    cols = []
    for c in range(len(r2)):
        m = re.match(r"-(\d{2})-", str(r2[c]).strip())
        if m:
            cols.append((c + 1, int(m.group(1))))       # (1-индекс колонки, номер месяца)
    runs, cur = [], []
    for col, mm in cols:
        if cur and col - cur[-1][0] > 2:                 # разрыв >2 → новый блок
            runs.append(cur); cur = []
        cur.append((col, mm))
    if cur:
        runs.append(cur)
    maps: dict[str, dict[int, int]] = {}
    if runs:
        actuals = max(runs, key=len)                     # самый длинный ряд = актуалы
        years, seg = [], []
        for col, mm in actuals:
            if seg and mm < seg[-1][1]:                  # 12 → 1: начался новый год
                years.append(seg); seg = []
            seg.append((col, mm))
        if seg:
            years.append(seg)
        if years:
            maps["fact2026"] = {mm: col for col, mm in years[-1]}
        if len(years) >= 2:
            maps["fact2025"] = {mm: col for col, mm in years[-2]}
        for run in runs:                                 # бюджет — 12-мес. ряд не из актуалов
            if run is not actuals and len({mm for _, mm in run}) == 12:
                maps["budget2026"] = {mm: col for col, mm in run}
                break
    return maps


def _pl_col(source: str, month: int, year: int) -> int:
    """Колонка блока с фолбэком на config, если авто-разбор шапки не сработал."""
    maps = pl_month_maps()
    if source == "budget":
        return maps.get("budget2026", {}).get(month) or PL_BUDGET_2026_COLS[month]
    if source == "fact" and year == 2026:
        return maps.get("fact2026", {}).get(month) or PL_FACT_2026_COLS[month]
    if source == "fact" and year == 2025:
        return maps.get("fact2025", {}).get(month) or PL_FACT_2025_COLS[month]
    raise ValueError(f"Unknown source/year: {source}/{year}")


def pl_value(rows: list[list[str]], metric: str, month: int, source: str = "fact",
             year: int = 2026) -> float:
    """Получить значение метрики P&L за конкретный месяц.

    metric  — ключ из PL_ROWS ('revenue', 'gross_profit', 'net_profit', ...)
    month   — 1..12 · source — 'fact' | 'budget' · year — 2025 | 2026 (для факта)
    Колонка определяется по шапке листа (pl_month_maps), устойчиво к перестройке.
    """
    return parse_ru_number(_cell(rows, PL_ROWS[metric], _pl_col(source, month, year)))


def pl_rows_value(rows: list[list[str]], row_list, month: int,
                  source: str = "fact", year: int = 2026) -> float:
    """Сумма значений по нескольким строкам PL за месяц (для статей из 2 частей)."""
    col = _pl_col(source, month, year)
    return sum(parse_ru_number(_cell(rows, r, col)) for r in row_list)


def pl_series(rows: list[list[str]], metric: str, source: str = "fact",
              year: int = 2026, months: int = 12) -> list[float]:
    """Серия значений за 1..months месяцев."""
    return [pl_value(rows, metric, m, source, year) for m in range(1, months + 1)]


def pl_last_fact_month(rows: list[list[str]], year: int = 2026) -> int:
    """Последний месяц с фактическими данными (по обороту, строка Turnover)."""
    last = 1
    for m in range(1, 13):
        if pl_value(rows, "turnover", m, "fact", year) != 0:
            last = m
    return last


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
    """Месяцы с данными: по датам дневных колонок ИЛИ по непустому месячному итогу оборота.

    Устойчиво к правкам листа: если у месяца убрали дневные колонки, но есть месячный
    итог (или наоборот) — месяц всё равно доступен в выборе.
    """
    months = {d.month for _, d in mon_daily_columns(rows)}
    meta = MON_SUMMARY_ROWS["turnover"]
    trow = _find_row(rows, meta["row"], meta["label"])
    for m, c in MON_MONTH_TOTAL_COLS.items():
        raw = _cell(rows, trow, c).strip()
        if raw and not raw.startswith("#") and parse_ru_number(raw) != 0:
            months.add(m)
    return sorted(months)


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


# ============= СЕГМЕНТЫ (устойчивый ридер «Бизнес-блока») =============
from config import BB_LINE_LABELS_RU, BB_SECTIONS  # noqa: E402

_BB_MON3 = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def _bb_header(rows: list[list[str]], key: str):
    """Строка-шапка «Business Line» таблицы key (ищем по подстроке заголовка секции)."""
    sub = BB_SECTIONS[key].lower()
    for r in range(1, len(rows) + 1):
        if sub in _cell(rows, r, 1).strip().lower():
            for rr in range(r, r + 6):
                if _cell(rows, rr, 1).strip() == "Business Line":
                    return rr
    return None


def _bb_cols(rows: list[list[str]], hdr, year: int) -> dict:
    """month→колонка для нужного года. 2025 — с суффиксом «25», 2026 — bare «Jan»."""
    out: dict[int, int] = {}
    if hdr is None:
        return out
    width = len(rows[hdr - 1]) if hdr - 1 < len(rows) else 0
    for c in range(2, width + 1):
        v = _cell(rows, hdr, c).strip().lower()
        m = _BB_MON3.get(v[:3])
        if not m:
            continue
        yr = 2025 if "25" in v else 2026
        if yr == year:
            out[m] = c
    return out


def _bb_lines(rows: list[list[str]], hdr) -> list[tuple[int, str]]:
    """(строка, имя линии) от шапки до Total/пустой."""
    out: list[tuple[int, str]] = []
    if hdr is None:
        return out
    r = hdr + 1
    while r <= len(rows):
        a = _cell(rows, r, 1).strip()
        if a in ("", "Total", "Прирост"):
            break
        out.append((r, a))
        r += 1
    return out


def bb_available_months(rows: list[list[str]], year: int = 2026) -> list[int]:
    """Месяцы, где по обороту есть данные."""
    hdr = _bb_header(rows, "turnover")
    cols = _bb_cols(rows, hdr, year)
    lines = _bb_lines(rows, hdr)
    ms = []
    for m in sorted(cols):
        tot = sum(parse_ru_number(_cell(rows, r, cols[m])) for r, _ in lines)
        if tot != 0:
            ms.append(m)
    return ms


def bb_segment_df(rows: list[list[str]], year: int, month: int) -> pd.DataFrame:
    """Метрики по бизнес-линиям за (year, month): оборот(тыс USD), маржприбыль(USD),
    маржинальность, активные клиенты, сделки, средний чек(тыс USD)."""
    raw = {}
    for key in ("turnover", "marginal_profit", "active_clients", "deals", "avg_check"):
        hdr = _bb_header(rows, key)
        col = _bb_cols(rows, hdr, year).get(month)
        vals = {}
        if hdr and col:
            for r, name in _bb_lines(rows, hdr):
                vals[name] = parse_ru_number(_cell(rows, r, col))
        raw[key] = vals
    recs = []
    for ln in raw["turnover"]:
        turn = raw["turnover"].get(ln, 0.0)          # тыс USD
        mp = raw["marginal_profit"].get(ln, 0.0)     # USD
        recs.append({
            "line": ln, "line_ru": BB_LINE_LABELS_RU.get(ln, ln),
            "turnover": turn, "marg_profit": mp,
            "marginality": mp / (turn * 1000) if turn else 0.0,
            "clients": raw["active_clients"].get(ln, 0.0),
            "deals": raw["deals"].get(ln, 0.0),
            "avg_check": raw["avg_check"].get(ln, 0.0),
        })
    return pd.DataFrame(recs)


def bb_monthly_totals(rows: list[list[str]], year: int, months: list[int]) -> dict:
    """Итоги по месяцам: оборот(тыс USD), маржприбыль(USD), маржинальность."""
    ht = _bb_header(rows, "turnover"); ct = _bb_cols(rows, ht, year); lt = _bb_lines(rows, ht)
    hm = _bb_header(rows, "marginal_profit"); cm = _bb_cols(rows, hm, year); lm = _bb_lines(rows, hm)
    turn = [sum(parse_ru_number(_cell(rows, r, ct[m])) for r, _ in lt) if m in ct else 0.0
            for m in months]
    mp = [sum(parse_ru_number(_cell(rows, r, cm[m])) for r, _ in lm) if m in cm else 0.0
          for m in months]
    marg = [(mp[i] / (turn[i] * 1000) if turn[i] else 0.0) for i in range(len(months))]
    return {"turnover": turn, "marg_profit": mp, "marginality": marg}


# ============= АГЕНТЫ (лист «Свод по агентам» + листы отдельных агентов) =============
from config import (AGENT_CLIENTS_START_ROW, AGENT_METRICS,  # noqa: E402
                    AGENTS_DATA_START_ROW, AGENTS_EXCLUDE, AGENTS_FIRST_MONTH_COL,
                    AGENTS_MONTH_BLOCK, AGENTS_SPREADSHEET_ID)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю Свод по агентам…")
def load_agents_svod_raw() -> list[list[str]]:
    return _open_sheet("agents_svod").get_all_values()


@st.cache_resource(show_spinner=False)
def _open_agent_tab(agent_name: str):
    """Лист отдельного агента (имя листа = имя агента). Открывается лениво по выбору."""
    return _get_client().open_by_key(AGENTS_SPREADSHEET_ID).worksheet(agent_name)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю лист агента…")
def load_agent_tab_raw(agent_name: str) -> list[list[str]]:
    return _open_agent_tab(agent_name).get_all_values()


def _agent_col(month: int, offset: int) -> int:
    """1-индекс колонки метрики (offset 0..7) для месяца month (1..12)."""
    return AGENTS_FIRST_MONTH_COL + (month - 1) * AGENTS_MONTH_BLOCK + offset


def _scan_names(rows: list[list[str]], start_row: int) -> list[tuple[int, str]]:
    """(номер_строки, имя) — от start_row до первой пустой ячейки в колонке A."""
    out: list[tuple[int, str]] = []
    r = start_row
    while True:
        name = _cell(rows, r, 1).strip()
        if not name:
            break
        out.append((r, name))
        r += 1
    return out


def agents_list(rows: list[list[str]]) -> list[tuple[int, str]]:
    """(номер_строки, имя агента) на листе «Свод по агентам» (без технических строк)."""
    return [(r, n) for r, n in _scan_names(rows, AGENTS_DATA_START_ROW)
            if n not in AGENTS_EXCLUDE]


def _aggregate_svod(rows: list[list[str]], entries: list[tuple[int, str]],
                    month: int, label: str) -> pd.DataFrame:
    """Агрегация одинаковой раскладки (8 метрик×12 мес) по набору строк.

    month 1..12 — конкретный месяц, month=0 — YTD (сумма всех месяцев).
    Денежные/целые суммируются; проценты пересчитываются из абсолютных.
    """
    months = list(range(1, 13)) if month == 0 else [month]
    recs = []
    for r, name in entries:
        agg = {key: 0.0 for key, *_ in AGENT_METRICS}
        for m in months:
            for key, off, _lbl, fmt in AGENT_METRICS:
                if fmt in ("money", "int"):
                    agg[key] += parse_ru_number(_cell(rows, r, _agent_col(m, off)))
        turn = agg["turnover"]
        agg["marginality"] = agg["margin"] / turn if turn else 0.0
        agg["client_rate"] = agg["our_fee"] / turn if turn else 0.0
        agg["agent_fee_pct"] = agg["agent_fee"] / turn if turn else 0.0
        rec = {label: name}
        rec.update(agg)
        recs.append(rec)
    return pd.DataFrame(recs)


def agents_available_months(rows: list[list[str]]) -> list[int]:
    """Месяцы (1..12), где есть хоть какой-то оборот у агентов."""
    ms = []
    agents = agents_list(rows)
    for m in range(1, 13):
        tot = sum(parse_ru_number(_cell(rows, r, _agent_col(m, 0))) for r, _ in agents)
        if tot != 0:
            ms.append(m)
    return ms


def agents_dataframe(rows: list[list[str]], month: int) -> pd.DataFrame:
    """Таблица по агентам за месяц (1..12) либо YTD (month=0)."""
    return _aggregate_svod(rows, agents_list(rows), month, "Агент")


def agent_clients_dataframe(agent_name: str, month: int) -> pd.DataFrame:
    """Таблица по клиентам одного агента (лист агента, клиенты с строки 7).

    Ленивая загрузка: читается только лист выбранного агента.
    """
    craw = load_agent_tab_raw(agent_name)
    entries = _scan_names(craw, AGENT_CLIENTS_START_ROW)
    return _aggregate_svod(craw, entries, month, "Клиент")


def agent_monthly_series(rows: list[list[str]], name: str, key: str) -> list[float]:
    """Помесячный ряд (1..12) одной метрики для одного агента."""
    off = next(o for k, o, *_ in AGENT_METRICS if k == key)
    target = next((r for r, n in agents_list(rows) if n == name), None)
    if target is None:
        return [0.0] * 12
    return [parse_ru_number(_cell(rows, target, _agent_col(m, off))) for m in range(1, 13)]


# ============= СДЕЛКИ: посделочная вкладка «Сделки» (книга RUDA) =============
from config import (DEALS_CH_BANK, DEALS_CH_ORDER, DEALS_COL,  # noqa: E402
                    DEALS_DATA_START, DEALS_GROSS_ADD, DEALS_LIQUIDITY_CHANNEL,
                    DEALS_LIQUIDITY_PRODUCT, DEALS_MONEY, DEALS_NET_MARGIN_ADD,
                    DEALS_NET_PROFIT_ADD, DEALS_PR_ORDER)

_MONTH_RU_SHORT = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "июн": 6,
                   "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}
_MONTH_RU_FULL = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю сделки…")
def load_deals_sdelki_raw() -> list[list[str]]:
    return _open_sheet("deals_sdelki").get_all_values()


def _norm_name(s: str) -> str:
    """Нормализация текста: неразрывные пробелы, лишние пробелы; регистр не трогаем."""
    return re.sub(r"\s+", " ", str(s).replace("\xa0", " ")).strip()


def _month_key(label: str) -> tuple[int, int]:
    """'авг.-26' → (2026, 8) для сортировки. Неизвестное → (0,0)."""
    m = re.match(r"([а-я]{3})\.?-?(\d{2})", label.lower())
    if not m:
        return (0, 0)
    return (2000 + int(m.group(2)), _MONTH_RU_SHORT.get(m.group(1), 0))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def deals_frame() -> pd.DataFrame:
    """Посделочная база в DataFrame: месяц, клиент, продукт/подтип, канал/подкатегория,
    все денежные компоненты и посчитанные уровни дохода (валовая/чистая маржа, ЧП)."""
    rows = load_deals_sdelki_raw()
    recs = []
    for row in rows[DEALS_DATA_START - 1:]:
        def g(col1: int) -> str:
            i = col1 - 1
            return row[i] if 0 <= i < len(row) else ""
        month = _norm_name(g(DEALS_COL["month"]))
        if not month:
            continue
        rec = {
            "month": month,
            "client": _norm_name(g(DEALS_COL["client_comb"])) or _norm_name(g(DEALS_COL["client"])),
            "product": _norm_name(g(DEALS_COL["product"])),
            "subtype": _norm_name(g(DEALS_COL["subtype"])),
            "channel": _norm_name(g(DEALS_COL["channel"])),
            "channel_sub": _norm_name(g(DEALS_COL["channel_sub"])),
            "sale": _norm_name(g(DEALS_COL["sale"])).lower(),
        }
        for k, c in DEALS_MONEY.items():
            rec[k] = parse_ru_number(g(c))
        recs.append(rec)
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    df["gross"] = df[DEALS_GROSS_ADD].sum(axis=1)
    df["net_margin"] = df["gross"] + df[DEALS_NET_MARGIN_ADD].sum(axis=1)
    df["net_profit"] = df["net_margin"] + df[DEALS_NET_PROFIT_ADD].sum(axis=1)
    return df


def deals_months() -> list[str]:
    """Список месяцев (сырые метки листа) в хронологическом порядке."""
    df = deals_frame()
    if df.empty:
        return []
    return sorted(df["month"].unique(), key=_month_key)


def deals_month_label(raw: str) -> str:
    """'авг.-26' → 'Август 2026' (для подписей)."""
    y, m = _month_key(raw)
    return f"{_MONTH_RU_FULL[m - 1]} {y}" if m else raw


def deals_period_label(months: list[str]) -> str:
    """Подпись выбранного диапазона: один месяц → 'Август 2026', диапазон → 'Июнь–Август 2026'."""
    if not months:
        return "—"
    ms = sorted(months, key=_month_key)
    if len(ms) == 1:
        return deals_month_label(ms[0])
    y0, m0 = _month_key(ms[0])
    y1, m1 = _month_key(ms[-1])
    if y0 == y1:
        return f"{_MONTH_RU_FULL[m0 - 1]}–{_MONTH_RU_FULL[m1 - 1]} {y1}"
    return f"{deals_month_label(ms[0])} – {deals_month_label(ms[-1])}"


def _agg_metrics(d: pd.DataFrame) -> dict:
    """Агрегаты + уровни дохода для набора сделок."""
    turn = d["turnover"].sum()
    gross = d["gross"].sum()
    nm = d["net_margin"].sum()
    npf = d["net_profit"].sum()
    deals = len(d)
    return {
        "clients": int(d["client"].nunique()), "deals": deals,
        "turnover": turn, "our_comm": d["our_comm"].sum(),
        "gross": gross, "net_margin": nm, "net_profit": npf,
        "gross_pct": gross / turn if turn else 0.0,
        "net_margin_pct": nm / turn if turn else 0.0,
        "net_profit_pct": npf / turn if turn else 0.0,
        "avg_check": turn / deals if deals else 0.0,
    }


def _ordered_groups(values, order: list[str]) -> list[str]:
    """Значения в порядке order, затем прочие (по алфавиту)."""
    present = list(dict.fromkeys(values))
    known = [x for x in order if x in present]
    rest = sorted(x for x in present if x not in order)
    return known + rest


def _client_only(d: pd.DataFrame) -> pd.DataFrame:
    """Только КЛИЕНТСКИЕ сделки: исключаем ликвидность по любому маркеру
    (канал «(ликвидность)» или продукт «Ликвидность»)."""
    return d[(d["channel"] != DEALS_LIQUIDITY_CHANNEL) & (d["product"] != DEALS_LIQUIDITY_PRODUCT)]


def deals_agg(kind: str, months: list[str]) -> pd.DataFrame:
    """Иерархия по каналам/продуктам за выбранные месяцы (только клиентские сделки).

    Строки: level 0 — верхний уровень (полное разбиение), level 1 — вложенная
    детализация (подкатегории банка / подтипы продукта), 'total' — ИТОГО.
    Ликвидность исключена в обоих разрезах → итоги каналов и продуктов совпадают.
    """
    df = deals_frame()
    d = _client_only(df[df["month"].isin(months)])
    recs = []
    if kind == "channels":
        for ch in _ordered_groups(d["channel"], DEALS_CH_ORDER):
            sub = d[d["channel"] == ch]
            recs.append({"name": ch, "level": 0, **_agg_metrics(sub)})
            if ch == DEALS_CH_BANK:
                for sc in _ordered_groups(sub[sub["channel_sub"] != ""]["channel_sub"], []):
                    ssub = sub[sub["channel_sub"] == sc]
                    recs.append({"name": sc, "level": 1, **_agg_metrics(ssub)})
    else:
        for pr in _ordered_groups(d["product"], DEALS_PR_ORDER):
            sub = d[d["product"] == pr]
            recs.append({"name": pr, "level": 0, **_agg_metrics(sub)})
            subtypes = sub.groupby("subtype")["turnover"].sum().sort_values(ascending=False)
            for sc in subtypes.index:
                if not sc:
                    continue
                recs.append({"name": sc, "level": 1, **_agg_metrics(sub[sub["subtype"] == sc])})
    recs.append({"name": "ИТОГО", "level": "total", **_agg_metrics(d)})
    return pd.DataFrame(recs)


def deals_monthly_totals(kind: str, months: list[str]) -> pd.DataFrame:
    """Итоги по каждому месяцу (для графика динамики), только клиентские сделки.

    kind оставлен для совместимости — ликвидность исключена в обоих разрезах,
    поэтому помесячные итоги каналов и продуктов совпадают.
    """
    df = deals_frame()
    recs = []
    for m in sorted(months, key=_month_key):
        d = _client_only(df[df["month"] == m])
        recs.append({"month": m, "label": deals_month_label(m), **_agg_metrics(d)})
    return pd.DataFrame(recs)


def deals_sale_split(months: list[str]) -> pd.DataFrame:
    """Первичные vs повторные клиентские сделки (по столбцу «Продажа») за период."""
    df = deals_frame()
    d = _client_only(df[df["month"].isin(months)])
    recs = []
    for tag in ("первичная", "повторная"):
        recs.append({"sale": tag, **_agg_metrics(d[d["sale"] == tag])})
    return pd.DataFrame(recs)


def deals_top_clients(months: list[str], n: int = 15, by: str = "net_profit") -> pd.DataFrame:
    """Топ клиентов за период (только клиентские сделки), сортировка по метрике by.

    Строки — клиент + агрегаты (_agg_metrics). Возвращает первые n."""
    df = deals_frame()
    d = _client_only(df[df["month"].isin(months)])
    if d.empty:
        return pd.DataFrame()
    recs = [{"name": cl, **_agg_metrics(sub)} for cl, sub in d.groupby("client")]
    res = pd.DataFrame(recs).sort_values(by, ascending=False)
    return res.head(n).reset_index(drop=True)


def deals_monthly_by_group(kind: str, months: list[str], valcol: str = "turnover"):
    """Помесячная разбивка метрики valcol по группам (каналы/продукты), клиентские сделки.

    Возвращает (DataFrame со столбцами month/label + по столбцу на группу, список групп
    в правильном порядке) — для стека динамики.
    """
    df = deals_frame()
    d = _client_only(df[df["month"].isin(months)])
    col = "channel" if kind == "channels" else "product"
    order = DEALS_CH_ORDER if kind == "channels" else DEALS_PR_ORDER
    groups = _ordered_groups(d[col], order) if not d.empty else []
    recs = []
    for m in sorted(months, key=_month_key):
        dm = d[d["month"] == m]
        row = {"month": m, "label": deals_month_label(m)}
        for gname in groups:
            row[gname] = dm[dm[col] == gname][valcol].sum()
        recs.append(row)
    return pd.DataFrame(recs), groups


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
