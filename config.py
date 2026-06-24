from pathlib import Path

ROOT = Path(__file__).parent

SERVICE_ACCOUNT_FILE = Path(r"C:\Users\User\.gcp\claude-sheets.json")
# Email сервис-аккаунта (доступ к таблицам):
# claude-mcp@claude-sheets-494613.iam.gserviceaccount.com

# Основная таблица с данными компании
SPREADSHEET_ID = "1IE-ViT-bX6CYN6OZBvdgUPKEFoyywro8cWX287NWfyE"

# Таблица «Мониторинг» (дневной мониторинг по дате закрытия сделки)
MONITORING_SPREADSHEET_ID = "16WYf82yG19ILCX1KfEgLuoVn-WToDSAQtXW6p2cDIgE"

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

# Колонки факта 2026 в PL GLOBAL (1-индекс): Jan=17, Feb=19, Mar=21, Apr=23, ... шаг 2 (между каждой парой M2M-колонка)
PL_FACT_2026_COLS = {m: 17 + (m - 1) * 2 for m in range(1, 13)}
# Колонки факта 2025: Jan=5 ... Dec=16
PL_FACT_2025_COLS = {m: 4 + m for m in range(1, 13)}
# Колонки бюджета 2026: Jan=51 (AY) ... Dec=62 (BJ)
PL_BUDGET_2026_COLS = {m: 50 + m for m in range(1, 13)}
