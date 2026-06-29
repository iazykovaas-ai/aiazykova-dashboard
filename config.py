from pathlib import Path

ROOT = Path(__file__).parent

SERVICE_ACCOUNT_FILE = Path(r"C:\Users\User\.gcp\claude-sheets.json")
# Email сервис-аккаунта (доступ к таблицам):
# claude-mcp@claude-sheets-494613.iam.gserviceaccount.com

# Основная таблица с данными компании
SPREADSHEET_ID = "1IE-ViT-bX6CYN6OZBvdgUPKEFoyywro8cWX287NWfyE"

# Таблица «Мониторинг» (дневной мониторинг по дате закрытия сделки)
MONITORING_SPREADSHEET_ID = "16WYf82yG19ILCX1KfEgLuoVn-WToDSAQtXW6p2cDIgE"

# Книга «ИИ GLOBAL Бизнес-Модель» — бюджет/факт по сегментам
BUSINESS_MODEL_SPREADSHEET_ID = "1jI6__M_o-i4OvzhGntjgGLViAmFVzWYqesZrcNu8E7k"

# Последний закрытый месяц для дашборда (1=Jan ... 12=Dec)
TARGET_MONTH = 4   # Apr
TARGET_YEAR = 2026
MONTH_NAMES_RU = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTH_NAMES_SHORT = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                     "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]

# Маппинг страниц дашборда на источники
SHEETS = {
    "pl_global": {"spreadsheet_id": SPREADSHEET_ID, "worksheet": "PL GLOBAL"},
    "business_block": {"spreadsheet_id": SPREADSHEET_ID, "worksheet": "Бизнес-блок"},
    "monitoring": {"spreadsheet_id": MONITORING_SPREADSHEET_ID,
                   "worksheet": "Мониторинг по дате закрытия сделки"},
    "rebudget": {"spreadsheet_id": BUSINESS_MODEL_SPREADSHEET_ID, "worksheet": "2026 Ребюджет"},
    "fact_forecast": {"spreadsheet_id": BUSINESS_MODEL_SPREADSHEET_ID, "worksheet": "Факт - прогноз"},
}

CACHE_TTL_SECONDS = 300

# Ключевые строки в PL GLOBAL (1-индексированные, как в листе).
# Идентификация по MAC-коду (колонка B) + название (колонка C).
PL_ROWS = {
    # 000 — Оборот (Turnover) — справочная сумма всех направлений
    "turnover":          5,
    # PL 1 000 — Выручка (Revenue)
    "revenue":           15,
    # PL 2 000 — Прямые расходы (Direct costs)
    "direct_costs":      25,
    #  100 — Валовая прибыль (Gross Profit)
    "gross_profit":      35,
    #  200 — Turnover ratio, % (маржа к обороту, %)
    "turnover_ratio":    45,
    # PL 500 / 600 / 700 — Переоценки / FX
    "revaluation":       54,
    "realized_fx":       55,
    "unrealized_fx":     56,
    # PL 5 000 — OPEX (всего операционных расходов)
    "opex":              57,
    # Разбивка OPEX по группам:
    "opex_software_it":  58,    # PL 5 100
    "opex_marketing":    68,    # PL 5 200
    "opex_personnel":    76,    # PL 5 300
    "opex_ga":          102,    # PL 5 400 — General & Administrative
    "opex_consulting":  132,    # PL 5 500 — Consulting & Audit
    "opex_legal":       138,    # PL 5 600 — Legal & Compliance
    "opex_other":       144,    # PL 5 700 — Other Operating Expenses
    #  300 — Операционная прибыль (Operating Profit)
    "operating_profit": 145,
    # PL 6 000 — Прочие доходы и расходы
    "other_income":     146,
    # PL 7 000 — Финансовые доходы и расходы
    "financial_inc_exp":168,
    #  400 — Прибыль до налога (PBT)
    "pbt":              173,
    # PL 8 000 — Налог на прибыль
    "income_tax":       174,
    #  500 — Чистая прибыль
    "net_profit":       177,
}

# Группировка метрик для отображения в P&L-таблице:
# (ключ, отображаемое имя, тип строки: 'total' — итог, 'item' — обычная строка, 'subitem' — отступ)
PL_TABLE_LAYOUT = [
    ("turnover",          "Turnover (Оборот)",              "item"),
    ("revenue",           "Revenue (Выручка)",              "total"),
    ("direct_costs",      "Direct costs (Прямые расходы)",  "item"),
    ("gross_profit",      "Gross Profit (Валовая прибыль)", "total"),
    ("turnover_ratio",    "Turnover ratio, %",              "item"),
    ("revaluation",       "Revaluation Gains / Losses (Прибыль/убыток от переоценки)",       "item"),
    ("realized_fx",       "Realized FX Gains / Losses (Прибыль/убыток от банковских конвертаций)", "item"),
    ("unrealized_fx",     "Unrealized FX Gains / Losses (Нереализованные валютные прибыли/убытки)", "item"),
    ("opex",              "OPEX (всего)",                   "total"),
    ("opex_software_it",  "  Software & IT Expenses (Расходы на ПО и ИТ)",         "subitem"),
    ("opex_marketing",    "  Marketing & Advertising (Маркетинг и реклама)",       "subitem"),
    ("opex_personnel",    "  Personnel costs (Расходы на персонал)",               "subitem"),
    ("opex_ga",           "  General & Administrative (Общехоз. и админ. расходы)", "subitem"),
    ("opex_consulting",   "  Consulting and Audit (Консалтинг и аудит)",           "subitem"),
    ("opex_legal",        "  Legal & Compliance (Юридические и комплаенс расходы)", "subitem"),
    ("opex_other",        "  Other Operating Expenses (Прочие операционные расходы)", "subitem"),
    ("operating_profit",  "Operating Profit (Операционная прибыль)",            "total"),
    ("other_income",      "Other income and expenses (Прочие доходы и расходы)", "item"),
    ("financial_inc_exp", "Financial Income & Expenses (Финансовые доходы и расходы)", "item"),
    ("pbt",               "Profit Before Tax (Прибыль до налогообложения)",     "total"),
    ("income_tax",        "Corporate Income Tax (Налог на прибыль)",            "item"),
    ("net_profit",        "Net Profit (Чистая прибыль)",    "total"),
]

# ============= МОНИТОРИНГ (по дате закрытия сделки) =============
# Лист-шаблон: D–G = месячные итоги (март…июнь), с H — по дням (даты в строке 1).
MON_DAILY_START_COL = 8                       # колонка H — первая дневная
MON_MONTH_TOTAL_COLS = {3: 4, 4: 5, 5: 6, 6: 7}   # месяц → колонка итога (D..G)

# Сводные строки (1-индекс), идентификация по метке в колонке C.
MON_SUMMARY_ROWS = {
    "turnover":        {"row": 3,  "label": "Оборот всего",                "fmt": "money"},
    "marginal_profit": {"row": 4,  "label": "Маржинальная прибыль всего",  "fmt": "money"},
    "marginality":     {"row": 5,  "label": "Маржинальность средняя",      "fmt": "pct"},
    "avg_check":       {"row": 6,  "label": "Средний чек",                 "fmt": "money"},
    "deals":           {"row": 7,  "label": "Кол-во закрытых сделок",      "fmt": "int"},
    "active_clients":  {"row": 8,  "label": "Активные клиенты",            "fmt": "int"},
    "payment_term":    {"row": 9,  "label": "Средневзвеш срок оплаты",     "fmt": "num"},
    "trigger_deals":   {"row": 10, "label": "Кол-во триггерных сделок",    "fmt": "int"},
    "revaluation":     {"row": 11, "label": "Переоценка всего, в тч.:",    "fmt": "money"},
}

# Заголовки блоков «по бизнес-линиям» (1-индекс строки заголовка; 11 линий идут ниже).
MON_LINE_BLOCKS = {
    "turnover":        {"header": 14, "label": "Оборот",                "fmt": "money"},
    "marginal_profit": {"header": 27, "label": "Маржинальная прибыль",  "fmt": "money"},
    "marginality":     {"header": 40, "label": "Маржинальность средняя", "fmt": "pct"},
    "avg_check":       {"header": 53, "label": "Средний чек",           "fmt": "money"},
    "deals":           {"header": 66, "label": "Кол-во закрытых сделок", "fmt": "int"},
    "active_clients":  {"header": 79, "label": "Активные клиенты",      "fmt": "int"},
}

# 11 бизнес-линий в порядке листа Мониторинга.
MON_LINES = ["Bank opt_import", "Bank import", "Direct opt_import", "Direct import",
             "Exchange", "Special", "Sber import", "Sber export", "Export", "Partner", "Dealing"]

# Отображаемые имена метрик мониторинга (для переключателя на странице).
MON_METRIC_LABELS = {
    "turnover":        "Оборот",
    "marginal_profit": "Маржинальная прибыль",
    "marginality":     "Маржинальность",
    "avg_check":       "Средний чек",
    "deals":           "Кол-во закрытых сделок",
    "active_clients":  "Активные клиенты",
    "payment_term":    "Средневзвеш. срок оплаты",
    "trigger_deals":   "Триггерные сделки",
    "revaluation":     "Переоценка",
}


# Колонки факта 2026 в PL GLOBAL (1-индекс): Jan=17, Feb=19, Mar=21, Apr=23, ... шаг 2 (между каждой парой M2M-колонка)
PL_FACT_2026_COLS = {m: 17 + (m - 1) * 2 for m in range(1, 13)}
# Колонки факта 2025: Jan=5 ... Dec=16
PL_FACT_2025_COLS = {m: 4 + m for m in range(1, 13)}
# Колонки бюджета 2026: Jan=51 (AY) ... Dec=62 (BJ)
PL_BUDGET_2026_COLS = {m: 50 + m for m in range(1, 13)}

# ============= СЕГМЕНТЫ: бюджет (2026 Ребюджет) и факт (Факт - прогноз) =============
# Строки сегментов маржинальной прибыли ОДИНАКОВЫ в обоих листах; различаются только столбцы.
SEG_MARGIN_ROWS = [
    (10, "Опт. банки"),
    (19, "Банк. импорт"),
    (29, "Опт. клиенты"),
    (37, "Прямой импорт"),
    (45, "Конвертация"),
    (53, "Спец клиенты"),
    (56, "Sber импорт"),
    (60, "Sber конверт."),
    (64, "Экспорт"),
    (68, "Партнёры"),
    (71, "Дилинг"),
    (74, "TD"),
]
SEG_MARGIN_TOTAL_ROW = 5                       # итог «Маржинальная прибыль, USD»
SEG_BUDGET_COL = {m: 13 + m for m in range(1, 13)}   # Ребюджет N..Y = янв..дек (май=18)
SEG_FACT_COL = {m: 22 + m for m in range(1, 7)}      # Факт-прогноз W..AB = янв..июн (май=27)

# Полный список статей P&L для селектора метрик: (рус. название, [строки PL GLOBAL]).
# Где две строки — суммируются (две части одной статьи).
PL_FULL_METRICS = [
    ("Оборот", [5]),
    ("Валовая прибыль (маржа)", [35]),
    ("Переоценка", [54]),
    ("Внутрибанковские конвертации", [55]),
    ("OPEX (операционные расходы)", [57]),
    ("  ПО и ИТ", [58]),
    ("  Маркетинг и реклама", [68]),
    ("  Расходы на персонал", [76]),
    ("  Общехоз. и админ. расходы", [102]),
    ("  Консалтинг и аудит", [132]),
    ("  Юридические и комплаенс", [138]),
    ("Операционная прибыль", [145]),
    ("Прочие доходы и расходы", [146]),
    ("Процентные доходы/расходы", [169]),
    ("Курсовые и переоценка фин. инструментов", [170, 171]),
    ("Прибыль до налогообложения (PBT)", [173]),
    ("Налог на прибыль", [174]),
    ("Чистая прибыль", [177]),
]
