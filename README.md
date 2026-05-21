# Дашборд ВЭД-агентства

Streamlit-приложение для мониторинга финансовых и операционных метрик.

## Установка

```powershell
cd c:\Users\User\Projects\workspace-aiazykova\dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Запуск (демо-режим, на stub-данных)

```powershell
streamlit run app.py
```

Откроется в браузере на `http://localhost:8501`.

## Подключение Google Sheets

1. Получите сервис-аккаунт (см. memory: `reference_google_sheets_mcp.md`)
2. Положите ключ как `dashboard/service_account.json`
3. Откройте таблицу для email сервис-аккаунта (Editor / Viewer)
4. В `config.py` подставьте `spreadsheet_id` и имена листов
5. В страницах (`pages/*.py`) замените `use_stub=True` → `use_stub=False`

## Структура

```
dashboard/
├── app.py                 # главная страница
├── config.py              # ID таблиц, типы клиентов, направления
├── requirements.txt
├── .streamlit/config.toml # тема оформления
├── data/
│   └── sheets_loader.py   # загрузка из Sheets + stub-данные + кэш
├── components/
│   └── kpi.py             # KPI-карточки, форматирование денег
└── pages/
    └── 1_📈_PnL.py        # P&L по направлениям
```

## Добавление новой страницы (нового мониторинга)

1. Создать файл `pages/N_<emoji>_<Имя>.py` (номер задаёт порядок в меню)
2. Скопировать шаблон из `1_📈_PnL.py`
3. Добавить ключ источника в `config.SHEETS` и заглушку в `data/sheets_loader.load_stub`

## Дальнейшее развитие

- Страница «План vs Факт» (Бюджет M1 + Бюджет M2 + Ребюджет M3)
- Страница «Потребность в ликвидности» (валютный gap T+0/T+1/T+2)
- Страница «Клиенты по типам» (14 типов)
- Подключение выгрузки из 1С (PL/CF) — после стабилизации Sheets-источника
