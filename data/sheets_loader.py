from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from config import (CACHE_TTL_SECONDS, PL_BUDGET_2026_COLS, PL_FACT_2025_COLS,
                    PL_FACT_2026_COLS, PL_ROWS, SERVICE_ACCOUNT_FILE, SHEETS)


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


# ============= СДЕЛКИ (книга RUDA): витрины + посделочная вкладка «Сделки» =============
from config import (DEALS_CH_FILTERS, DEALS_CH_ROLLUP, DEALS_COL,  # noqa: E402
                    DEALS_DATA_START, DEALS_GROSS_ADD, DEALS_LIQUIDITY_CHANNEL,
                    DEALS_LIQUIDITY_PRODUCT, DEALS_MONEY, DEALS_NET_MARGIN_ADD,
                    DEALS_OBMEN_FLAG, DEALS_PR_FILTERS, DEALS_PROFIT_VAR_ADD,
                    DEALS_SIZE_GROUPS, DEALS_VITRINA_LEVELS)

_MONTH_RU_SHORT = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "июн": 6,
                   "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}
_MONTH_RU_FULL = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
_VIT_SHEET = {"channels": "deals_channels", "products": "deals_products"}
_VIT_NUM = ["clients", "deals", "turnover", "our_comm", *DEALS_VITRINA_LEVELS.values()]
_SIZE_SET = {s.lower() for s in DEALS_SIZE_GROUPS}


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю сделки…")
def load_deals_sdelki_raw() -> list[list[str]]:
    return _open_sheet("deals_sdelki").get_all_values()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Загружаю витрину RUDA…")
def load_deals_vitrina_raw(sheet_key: str) -> list[list]:
    """Витрина целиком; числа — без округления отображения (точные суммы за диапазон)."""
    return _open_sheet(sheet_key).get_all_values(value_render_option="UNFORMATTED_VALUE")


def _norm_name(s: str) -> str:
    """Нормализация текста: неразрывные пробелы, лишние пробелы; регистр не трогаем."""
    return re.sub(r"\s+", " ", str(s).replace("\xa0", " ")).strip()


def _month_key(label: str) -> tuple[int, int]:
    """'авг.-26' → (2026, 8) для сортировки. Неизвестное → (0,0)."""
    m = re.match(r"([а-я]{3})\.?-?(\d{2})", label.lower())
    if not m:
        return (0, 0)
    return (2000 + int(m.group(2)), _MONTH_RU_SHORT.get(m.group(1), 0))


def deals_period_yms(label: str) -> list[int]:
    """Подпись периода витрины → месяцы ГГГГММ: «Август 2026» → [202608];
    «2 квартал 2026» → [202604, 202605, 202606]. Не период → []."""
    s = _norm_name(label).lower()
    m = re.fullmatch(r"([1-4]) квартал (\d{4})", s)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        return [y * 100 + mm for mm in range(3 * q - 2, 3 * q + 1)]
    m = re.fullmatch(r"([а-я]+) (\d{4})", s)
    if m and m.group(1).capitalize() in _MONTH_RU_FULL:
        return [int(m.group(2)) * 100 + _MONTH_RU_FULL.index(m.group(1).capitalize()) + 1]
    return []


def deals_period_short(label: str) -> str:
    """Короткая подпись для оси: «Август 2026» → «Август», «1 квартал 2026» → «1 кв»."""
    s = re.sub(r"\s+\d{4}$", "", _norm_name(label))
    return s.replace(" квартал", " кв")


def deals_period_label(periods: list[str]) -> str:
    """Один период → как в витрине; диапазон → «Январь–Август 2026» / «1 квартал–Август 2026»."""
    if not periods:
        return "—"
    if len(periods) == 1:
        return periods[0]
    a, b = periods[0], periods[-1]
    ya, yb = a[-4:], b[-4:]
    return f"{a[:-5]}–{b}" if ya == yb and ya.isdigit() else f"{a} – {b}"


def ym_label(ym: int) -> str:
    """202608 → «Август 2026»."""
    return f"{_MONTH_RU_FULL[ym % 100 - 1]} {ym // 100}"


# ---------- посделочная база «Сделки» ----------
@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def deals_frame() -> pd.DataFrame:
    """Посделочная база в DataFrame: месяц (ГГГГММ), клиент, признаки для условий витрин,
    денежные компоненты и уровни дохода (валовая / чистая маржа / после перем. расходов)."""
    rows = load_deals_sdelki_raw()
    recs = []
    for row in rows[DEALS_DATA_START - 1:]:
        def g(col1: int) -> str:
            i = col1 - 1
            return row[i] if 0 <= i < len(row) else ""
        y, m = _month_key(_norm_name(g(DEALS_COL["month"])))
        if not m:
            continue
        comb = _norm_name(g(DEALS_COL["client_comb"]))
        rec = {
            "ym": y * 100 + m,
            "client": comb or _norm_name(g(DEALS_COL["client"])),
            "client_comb": comb.upper(),
            "product": _norm_name(g(DEALS_COL["product"])),
            "subtype": _norm_name(g(DEALS_COL["subtype"])),
            "channel": _norm_name(g(DEALS_COL["channel"])),
            "channel_sub": _norm_name(g(DEALS_COL["channel_sub"])),
            "first_deal": _norm_name(g(DEALS_COL["first_deal"])).lower(),
            "cur_in": _norm_name(g(DEALS_COL["cur_in"])).upper(),
            "cur_out": _norm_name(g(DEALS_COL["cur_out"])).upper(),
            "obmen": _norm_name(g(DEALS_COL["obmen"])).lower() == DEALS_OBMEN_FLAG,
            "payment": _norm_name(g(DEALS_COL["payment"])),
            "size": _norm_name(g(DEALS_COL["size"])),
        }
        for k, c in DEALS_MONEY.items():
            rec[k] = parse_ru_number(g(c))
        recs.append(rec)
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    df["gross"] = df[DEALS_GROSS_ADD].sum(axis=1)
    df["net_margin"] = df["gross"] + df[DEALS_NET_MARGIN_ADD].sum(axis=1)
    df["profit_var"] = df["net_margin"] + df[DEALS_PROFIT_VAR_ADD].sum(axis=1)
    return df


def _agg_metrics(d: pd.DataFrame) -> dict:
    """Агрегаты + уровни дохода для набора сделок."""
    turn = d["turnover"].sum()
    pv = d["profit_var"].sum()
    deals = len(d)
    return {
        "clients": int(d["client"].nunique()), "deals": deals,
        "turnover": turn, "gross": d["gross"].sum(), "profit_var": pv,
        "profit_var_pct": pv / turn if turn else 0.0,
        "avg_check": turn / deals if deals else 0.0,
    }


def _client_only(d: pd.DataFrame) -> pd.DataFrame:
    """Только КЛИЕНТСКИЕ сделки: исключаем ликвидность по любому маркеру
    (канал «(ликвидность)» или продукт «Ликвидность»)."""
    return d[(d["channel"] != DEALS_LIQUIDITY_CHANNEL) & (d["product"] != DEALS_LIQUIDITY_PRODUCT)]


def deals_sale_split(yms: list[int]) -> pd.DataFrame:
    """Первичные vs повторные продажи за месяцы yms — как строки «первичные продажи» /
    «повторные продажи» витрины: по AI «Это самая первая сделка клиента» (да / нет)."""
    df = deals_frame()
    d = _client_only(df[df["ym"].isin(yms)])
    recs = []
    for tag, flag in (("первичная", "да"), ("повторная", "нет")):
        recs.append({"sale": tag, **_agg_metrics(d[d["first_deal"] == flag])})
    return pd.DataFrame(recs)


def deals_top_clients(yms: list[int], n: int = 15, by: str = "profit_var") -> pd.DataFrame:
    """Топ клиентов за месяцы yms (только клиентские сделки), сортировка по метрике by."""
    df = deals_frame()
    d = _client_only(df[df["ym"].isin(yms)])
    if d.empty:
        return pd.DataFrame()
    recs = [{"name": cl, **_agg_metrics(sub)} for cl, sub in d.groupby("client")]
    res = pd.DataFrame(recs).sort_values(by, ascending=False)
    return res.head(n).reset_index(drop=True)


# ---------- витрины «Каналы по размеру сделки» / «Продуктовые группы» ----------
def _vit_label(s: str) -> str:
    """«Импорт (клиентский) всего, в т.ч.:» → «Импорт (клиентский)»."""
    s = _norm_name(s)
    s = re.sub(r",?\s*(всего,?\s*)?(в т\.\s?ч\.|в том числе):?$", "", s)
    return re.sub(r"\s+всего$", "", s).strip(" ,:")


def _vitrina_colmap(rows: list[list[str]]) -> dict[str, int]:
    """Столбцы витрины по шапке (строка названий + строка единиц), а не по буквам."""
    for i in range(1, len(rows)):
        units = [_norm_name(c).lower() for c in rows[i]]
        if "сделок, шт" not in units:
            continue
        names = [_norm_name(c) for c in rows[i - 1]]
        cmap: dict[str, int] = {}
        for j, u in enumerate(units):
            n = names[j] if j < len(names) else ""
            if u.startswith("клиентов"):
                cmap.setdefault("clients", j)
            elif u == "сделок, шт":
                cmap.setdefault("deals", j)
            elif u == "оборот":
                cmap.setdefault("turnover", j)
            elif u == "комиссия для клиента":
                cmap.setdefault("our_comm", j)
            elif u == "usd" and n in DEALS_VITRINA_LEVELS:
                cmap.setdefault(DEALS_VITRINA_LEVELS[n], j)
        return cmap
    return {}


def _vit_tree(kind: str, recs: list[dict]) -> list[dict]:
    """Место каждой строки витрины в иерархии: group → sub → detail (+ size для групп размера).

    Каналы: группы — строки с «итого» («Собственные клиенты итого», «Банковский канал итого»),
    детализация — постоплата/предоплата. Продукты: группы — «… (клиентский)» и «Поставщики
    ликвидности» (флаг liq), детализация — рубль на вход / на выход / без рубля.
    """
    out, group, sub, detail, liq = [], "", "", "", False
    for rec in recs:
        lab = rec["label"]
        low = lab.lower()
        role = "line"
        if low in _SIZE_SET:
            role = "size"
        elif low == "итого":
            group, sub, detail, liq = "ИТОГО", "", "", False
            role = "total"
        elif (kind == "channels" and "итого" in low) or (
                kind == "products" and ("(клиентский)" in low or low.startswith("поставщики ликвидности"))):
            group, sub, detail = lab, "", ""
            liq = low.startswith("поставщики ликвидности")
        elif (kind == "channels" and low in ("постоплата", "предоплата")) or (
                kind == "products" and low in ("рубль на вход", "рубль на выход", "без рубля")):
            detail = lab
        else:
            sub, detail = lab, ""
        out.append({**rec, "role": role, "group": group, "sub": sub, "detail": detail,
                    "size": lab if role == "size" else "", "liq": liq})
    return out


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def deals_vitrina_blocks(kind: str) -> tuple[list[str], dict[str, list[dict]]]:
    """Периоды витрины (в порядке листа) и строки каждого блока с местом в иерархии.
    Пустые блоки (оборот ИТОГО = 0) не берем."""
    rows = load_deals_vitrina_raw(_VIT_SHEET[kind])
    cmap = _vitrina_colmap(rows)
    if not {"clients", "deals", "turnover", "gross", "net_margin", "profit_var"} <= cmap.keys():
        return [], {}
    raw: dict[str, list[dict]] = {}
    cur = None
    for r in rows:
        a = _norm_name(r[0]) if r else ""
        if deals_period_yms(a):
            cur = a
            raw[cur] = []
            continue
        if cur is None or not a or a.lower().startswith("доля"):
            continue

        def cell(k: str) -> str:
            j = cmap.get(k)
            return r[j] if j is not None and j < len(r) else ""
        if not re.search(r"\d", str(cell("deals"))):
            continue                      # строки шапки следующего блока
        raw[cur].append({"label": _vit_label(a), **{k: parse_ru_number(cell(k)) for k in _VIT_NUM}})
    blocks = {p: _vit_tree(kind, recs) for p, recs in raw.items()}
    periods = [p for p, b in blocks.items()
               if any(x["role"] == "total" and x["turnover"] for x in b)]
    return periods, {p: blocks[p] for p in periods}


def _filter_mask(d: pd.DataFrame, conds) -> pd.Series:
    m = pd.Series(True, index=d.index)
    for col, op, val in conds:
        s = d[col]
        if op == "==":
            m &= s == val
        elif op == "!=":
            m &= s != val
        elif op == "in":
            m &= s.isin(val)
        elif op == "not in":
            m &= ~s.isin(val)
    return m


def _clients_from_deals(kind: str, row: dict, yms: list[int]) -> float:
    """Уникальные клиенты строки витрины за месяцы yms — по «Сделкам», теми же условиями,
    что в формулах витрины. Незнакомая подпись строки → NaN."""
    df = deals_frame()
    d = df[df["ym"].isin(yms)]
    filters = DEALS_CH_FILTERS if kind == "channels" else DEALS_PR_FILTERS
    conds = ([("channel", "!=", DEALS_LIQUIDITY_CHANNEL)] if kind == "channels"
             else [("product", "!=", DEALS_LIQUIDITY_PRODUCT)])
    if row["group"] != "ИТОГО":
        for part in (row["group"], row["sub"], row["detail"]):
            if not part:
                continue
            f = filters.get(part.lower())
            if f is None:
                return float("nan")
            conds = conds + f
    if row["size"]:
        conds = conds + [("size", "==", row["size"])]
    sel = d[_filter_mask(d, conds)]
    return float(sel.loc[sel["client_comb"] != "", "client_comb"].nunique())


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def deals_vitrina(kind: str, periods: list[str]) -> pd.DataFrame:
    """Строки витрины за выбранные периоды — суммы блоков (клиентские сделки).

    Колонки: group/sub/detail/size/role, name (подпись строки), short (короткое имя для
    графиков), bar (строки для графиков — вместе дают ИТОГО), clients, deals, turnover,
    our_comm, уровни прибыли (USD и *_pct от оборота), avg_check.
    Клиенты: один период — из витрины; несколько — уникальные по «Сделкам» (условия витрины).
    Продукты: поставщики ликвидности исключены, ИТОГО = ИТОГО витрины − ликвидность.
    """
    _, blocks = deals_vitrina_blocks(kind)
    keys = ["group", "sub", "detail", "size"]
    recs, order = [], {}
    for p in periods:
        for i, r in enumerate(blocks.get(p, [])):
            k = tuple(r[c] for c in keys)
            order.setdefault(k, (i, len(order)))
            recs.append({**r, "_k": k})
    if not recs:
        return pd.DataFrame()
    raw = pd.DataFrame(recs)
    first = raw.drop_duplicates("_k").set_index("_k").drop(columns=_VIT_NUM)
    sums = raw.groupby("_k")[_VIT_NUM].sum()
    df = first.join(sums).reset_index()
    df["_o"] = df["_k"].map(order)
    df = df.sort_values("_o").reset_index(drop=True)

    yms = sorted({ym for p in periods for ym in deals_period_yms(p)})
    if len(periods) > 1:
        df["clients"] = [_clients_from_deals(kind, r, yms) for r in df.to_dict("records")]
    if kind == "products":
        liq = df[df["liq"] & (df["sub"] == "") & (df["size"] == "")]
        tot = df["role"] == "total"
        for c in _VIT_NUM:
            if c != "clients" and len(liq):
                df.loc[tot, c] = df.loc[tot, c].values - liq[c].sum()
        if tot.any():
            df.loc[tot, "clients"] = _clients_from_deals(kind, df[tot].iloc[0].to_dict(), yms)
        df = df[~df["liq"]].reset_index(drop=True)

    df["name"] = df["label"]
    is_line = df["role"] == "line"
    if kind == "channels":
        rollup = df["group"].str.lower() == DEALS_CH_ROLLUP
        df["bar"] = is_line & (df["detail"] == "") & (
            (rollup & (df["sub"] != "")) | (~rollup & (df["sub"] == "")))
    else:
        df["bar"] = is_line & (df["sub"] == "")
    df["short"] = (df["name"].str.replace(r"\s+итого$", "", regex=True)
                   .str.replace(" (клиентский)", "", regex=False))
    t = df["turnover"].replace(0, float("nan"))
    for lv in DEALS_VITRINA_LEVELS.values():
        df[f"{lv}_pct"] = (df[lv] / t).fillna(0.0)
    df["avg_check"] = (df["turnover"] / df["deals"].replace(0, float("nan"))).fillna(0.0)
    return df.drop(columns=["_k", "_o", "label"])


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def deals_vitrina_by_period(kind: str) -> pd.DataFrame:
    """По каждому периоду витрины: строки для графиков (bar) и ИТОГО — для динамики."""
    periods, _ = deals_vitrina_blocks(kind)
    out = []
    for p in periods:
        d = deals_vitrina(kind, [p])
        d = d[d["bar"] | (d["role"] == "total")].copy()
        d["period"] = p
        out.append(d)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
