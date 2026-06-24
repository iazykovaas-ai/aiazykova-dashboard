from __future__ import annotations

import streamlit as st


def format_money(value: float, unit: str = "$") -> str:
    """Деньги в USD: $1.2M / $340.5k / $12. Валюта всегда доллары."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}k"
    return f"${value:.0f}"


def fmt_kusd(value: float) -> str:
    """Форматирует значение, поданное в тыс. USD. Всегда в тысячах."""
    # Разделитель тысяч — неразрывный пробел
    return f"${value:,.0f} k".replace(",", " ")


def fmt_usd_full(value: float) -> str:
    """Значение в USD (не в тысячах)."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f} M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f} k"
    return f"${value:.0f}"


def fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def kpi_row(items: list[dict]) -> None:
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        value = item["value"]
        if item.get("money"):
            value = format_money(value, item.get("unit", "₽"))
        delta = item.get("delta")
        col.metric(label=item["label"], value=value, delta=delta)
