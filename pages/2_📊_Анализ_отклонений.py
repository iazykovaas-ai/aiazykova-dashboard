import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.assistant import render_assistant
from components.kpi import fmt_kusd
from components.styles import (PALETTE, apply, chart_card_close, chart_card_open,
                               hero, style_plotly_2d)
from config import (MONTH_NAMES_RU, MONTH_NAMES_SHORT, PL_FULL_METRICS,
                    TARGET_MONTH, TARGET_YEAR)
from data.sheets_loader import (load_pl_global_raw, pl_value, pl_rows_value,
                                seg_fact_months,
                                seg_margin_budget, seg_margin_fact, seg_margin_total)

st.set_page_config(page_title="Анализ отклонений", page_icon="📊", layout="wide")
apply()
render_assistant()

hero("📊 Анализ отклонений",
     "Факт против плана и против прошлого периода — с разбором по факторам и кратким выводом")

rows = load_pl_global_raw()


def _md(s: str) -> str:
    """Экранирует $ — иначе markdown трактует $...$ как формулу LaTeX
    (курсивный шрифт и съеденные пробелы между разрядами)."""
    return s.replace("$", "\\$")


def inline_radio(label, options, key):
    """Радио с подписью в той же строке (компактно, без переноса)."""
    c1, c2 = st.columns([1, 6], vertical_alignment="center")
    c1.markdown(f"<div style='font-weight:600;color:#C7CCEC;'>{label}</div>",
                unsafe_allow_html=True)
    return c2.radio(label, options, horizontal=True,
                    label_visibility="collapsed", key=key)


# Метрики с заполненным бюджетом (выручка/прямые расходы — пусто, не показываем)
PF_METRICS = [("turnover", "Оборот"), ("gross_profit", "Маржинальная прибыль"),
              ("opex", "OPEX"), ("net_profit", "Чистая прибыль")]
KPI_KEYS = ["turnover", "gross_profit", "net_profit"]

# Факторы P&L, складывающиеся в чистую прибыль (выручка/прямые расходы — внутри маржи)
# Факторы = детальные статьи P&L (как переводили), без промежуточных прибылей (OP/PBT).
# OPEX и финансовые разложены на статьи; в сумме дают чистую прибыль.
PNL_FACTORS = [
    ([35],       "Валовая прибыль (маржа)"),
    ([54],       "Переоценка"),
    ([55],       "Внутрибанковские конвертации"),
    ([56],       "Нереализованные курсовые"),
    ([58],       "IT расходы"),
    ([68],       "Маркетинг"),
    ([76],       "Расходы на персонал"),
    ([102],      "Общехоз. и админ. расходы"),
    ([132],      "Консалтинг и аудит"),
    ([138],      "Комплаенс"),
    ([144],      "Прочие операционные расходы"),
    ([146],      "Прочие доходы и расходы"),
    ([169],      "Финансовые доходы и расходы"),
    ([170, 171], "Хеджирование"),
    ([172],      "Прочие финансовые"),
    ([174],      "Налог"),
]


def pl_sum(metric, a, b, source):
    return sum(pl_value(rows, metric, m, source) for m in range(a, b + 1))


def waterfall_bridge(start_label, start_val, steps, end_label, end_val, title, subtitle):
    chart_card_open(title, subtitle)
    labels = [start_label] + [s[0] for s in steps] + [end_label]
    measures = ["absolute"] + ["relative"] * len(steps) + ["total"]
    values = [start_val] + [s[1] for s in steps] + [end_val]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measures, x=labels, y=values,
        text=[fmt_kusd(v) for v in values],
        textposition="outside", textfont=dict(color=PALETTE["ink"], size=11),
        connector=dict(line=dict(color=PALETTE["line"], width=1)),
        increasing=dict(marker=dict(color="#2FD9A6")),
        decreasing=dict(marker=dict(color="#FF5C7A")),
        totals=dict(marker=dict(color="#8B7BF0")),
    ))
    style_plotly_2d(fig, height=470)
    # Бледные пунктирные разделители между столбцами (по границам, не по центру),
    # протянуты вниз в зону подписей — каждый столбец как в своей «ячейке».
    seps = [dict(type="line", xref="x", yref="paper", x0=k + 0.5, x1=k + 0.5,
                 y0=-0.32, y1=1, layer="below",
                 line=dict(color="rgba(150,160,200,0.16)", width=1, dash="dot"))
            for k in range(len(labels) - 1)]
    fig.update_layout(yaxis=dict(title="тыс. USD", tickformat=",.0f"),
                      xaxis=dict(showgrid=False, tickangle=-30, automargin=True),
                      shapes=seps,
                      separators=". ", uniformtext_minsize=10, uniformtext_mode="hide")
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": True, "displaylogo": False,
                            "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
    chart_card_close()


def contrib_bars(steps, title, subtitle):
    """Альтернатива мостику: горизонтальные бары вклада каждой статьи (зелёный/красный)."""
    chart_card_open(title, subtitle)
    items = sorted(steps, key=lambda s: s[1])
    fig = go.Figure(go.Bar(
        y=[l for l, _ in items], x=[d for _, d in items], orientation="h",
        marker=dict(color=["#2FD9A6" if d >= 0 else "#FF5C7A" for _, d in items], line=dict(width=0)),
        text=[fmt_kusd(d) for _, d in items], textposition="outside",
        textfont=dict(color=PALETTE["ink"], size=11),
        hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>"))
    style_plotly_2d(fig, height=max(260, 52 * len(items) + 120))
    fig.update_layout(xaxis=dict(showticklabels=False, showgrid=True, zeroline=True,
                                 zerolinecolor=PALETTE["muted"]),
                      yaxis=dict(showgrid=False, automargin=True),
                      separators=". ", uniformtext_minsize=10, uniformtext_mode="hide")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    chart_card_close()


def show_bridge(kind, start_label, start_val, steps, end_label, end_val, title, subtitle):
    if kind == "Вклад (бары)":
        contrib_bars(steps, title, subtitle)
        st.caption(_md(f"{start_label}: {fmt_kusd(start_val)}  →  {end_label}: {fmt_kusd(end_val)}"))
    else:
        waterfall_bridge(start_label, start_val, steps, end_label, end_val, title, subtitle)


def insight_box(total_dev, steps, subject="Чистая прибыль"):
    """Краткий авто-вывод: общее отклонение + топ факторов вверх/вниз."""
    real = [(l, d) for l, d in steps if "Прочее" not in l]
    pos = sorted([s for s in real if s[1] > 0], key=lambda s: -s[1])[:2]
    neg = sorted([s for s in real if s[1] < 0], key=lambda s: s[1])[:2]
    dirn = "выше" if total_dev >= 0 else "ниже"
    parts = [f"📌 **Итого {subject} {dirn} на {fmt_kusd(abs(total_dev))}.**"]
    if pos:
        parts.append("Рост за счёт: " + ", ".join(f"{l} ({fmt_kusd(d)})" for l, d in pos) + ".")
    if neg:
        parts.append("Снижение за счёт: " + ", ".join(f"{l} ({fmt_kusd(d)})" for l, d in neg) + ".")
    st.info(_md(" ".join(parts)))


def seg_steps(cur: dict, base: dict):
    out = [(l, cur.get(l, 0) - base.get(l, 0)) for l in cur]
    out = [(l, d) for l, d in out if abs(d) > 0.5]
    out.sort(key=lambda s: s[1])
    return out


def seg_sum(func, months):
    out: dict = {}
    for m in months:
        for k, v in func(m).items():
            out[k] = out.get(k, 0) + v
    return out


FACT_MONTHS = seg_fact_months()

tab_pf, tab_pp = st.tabs(["🎯 План vs Факт", "🔄 Период к периоду"])

# ============================ ПЛАН vs ФАКТ ============================
with tab_pf:
    st.markdown("##### 📅 Период")
    cfrom, cto = st.columns(2)
    with cfrom:
        st.session_state.setdefault("ao_from", 1)
        from_m = st.selectbox("С месяца", list(range(1, 13)),
                              format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_from")
    with cto:
        st.session_state.setdefault("ao_to", 1)
        to_m = st.selectbox("По месяц", list(range(1, 13)),
                            format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_to")
    if from_m > to_m:
        from_m, to_m = to_m, from_m
    period_label = (f"{MONTH_NAMES_RU[from_m - 1]} {TARGET_YEAR}" if from_m == to_m
                    else f"{MONTH_NAMES_RU[from_m - 1]} — {MONTH_NAMES_RU[to_m - 1]} {TARGET_YEAR}")

    # KPI: факт + % к плану
    labels = dict(PF_METRICS)
    for col, key in zip(st.columns(len(KPI_KEYS)), KPI_KEYS):
        fact = pl_sum(key, from_m, to_m, "fact")
        budget = pl_sum(key, from_m, to_m, "budget")
        done = fact / budget * 100 if budget else None
        col.metric(labels[key], fmt_kusd(fact),
                   f"{done - 100:+.1f}% к плану" if done is not None else "нет плана")

    st.markdown("")

    # Помесячно план/факт + % выполнения
    months = list(range(from_m, to_m + 1))
    mi = st.selectbox("Метрика для графика", list(range(len(PL_FULL_METRICS))),
                      format_func=lambda i: PL_FULL_METRICS[i][0].strip(), key="ao_metric")
    m_label, m_rows, m_fmt = PL_FULL_METRICS[mi]
    m_label = m_label.strip()
    plan = [pl_rows_value(rows, m_rows, m, "budget") for m in months]
    fact = [pl_rows_value(rows, m_rows, m, "fact") for m in months]

    def _fmt(v):
        return f"{v * 100:.2f}%" if m_fmt == "pct" else fmt_kusd(v)

    chart_card_open(f"Факт vs План · {m_label} · {period_label}",
                    "горизонтально · по месяцам")
    ynames = [MONTH_NAMES_RU[m - 1] for m in months]
    pv = [v * 100 if m_fmt == "pct" else v for v in plan]
    fv2 = [v * 100 if m_fmt == "pct" else v for v in fact]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=ynames, x=pv, name="План", orientation="h",
                         marker=dict(color="#8B7BF0"),
                         text=[_fmt(v) for v in plan], textposition="outside",
                         textfont=dict(color=PALETTE["ink"], size=11),
                         hovertemplate="<b>%{y}</b><br>План: %{text}<extra></extra>"))
    fig.add_trace(go.Bar(y=ynames, x=fv2, name="Факт", orientation="h",
                         marker=dict(color=["#2FD9A6" if f >= p else "#FF5C7A"
                                            for f, p in zip(fact, plan)]),
                         text=[_fmt(v) for v in fact], textposition="outside",
                         textfont=dict(color=PALETTE["ink"], size=11),
                         hovertemplate="<b>%{y}</b><br>Факт: %{text}<extra></extra>"))
    style_plotly_2d(fig, height=max(240, 95 * len(months)))
    fig.update_layout(barmode="group", yaxis=dict(autorange="reversed", showgrid=False),
                      xaxis=dict(showticklabels=False, showgrid=True),
                      legend=dict(orientation="h", y=1.15),
                      separators=". ", uniformtext_minsize=10, uniformtext_mode="hide")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # авто-описание за период
    if m_fmt == "pct":
        fp = sum(fact) / len(fact) if fact else 0
        pp = sum(plan) / len(plan) if plan else 0
        if pp:
            dev = (fp - pp) * 100
            st.info(f"📌 **{m_label}** за {period_label}: факт {fp * 100:.2f}% против плана "
                    f"{pp * 100:.2f}% — {'выше' if dev >= 0 else 'ниже'} на {abs(dev):.1f} п.п.")
        else:
            st.info(f"📌 **{m_label}**: факт {fp * 100:.2f}% (плана нет).")
    else:
        ftot, ptot = sum(fact), sum(plan)
        if ptot:
            dev = ftot - ptot
            st.info(_md(f"📌 **{m_label}** за {period_label}: факт {fmt_kusd(ftot)}, план "
                        f"{fmt_kusd(ptot)}, отклонение {'+' if dev >= 0 else '−'}{fmt_kusd(abs(dev))} "
                        f"({ftot / ptot * 100 - 100:+.0f}% к плану)."))
        else:
            st.info(_md(f"📌 **{m_label}** за {period_label}: факт {fmt_kusd(ftot)} (плана нет)."))
    chart_card_close()

    # Факторный мостик «Бюджет → Факт»
    st.markdown("##### 🔻 Разбор отклонения от плана")
    dim = inline_radio("Разрез", ["Сегменты (маржа)", "Статьи P&L"], "ao_bf_dim")
    bf_kind = inline_radio("Вид", ["Мостик", "Вклад (бары)"], "ao_bf_kind")
    if dim == "Статьи P&L":
        net_budget = pl_sum("net_profit", from_m, to_m, "budget")
        net_fact = pl_sum("net_profit", from_m, to_m, "fact")
        steps, covered = [], 0.0
        for row_list, label in PNL_FACTORS:
            bud = sum(pl_rows_value(rows, row_list, m, "budget") for m in months)
            var = sum(pl_rows_value(rows, row_list, m, "fact") for m in months) - bud
            if abs(var) < 0.5:        # пустые статьи не показываем
                continue
            steps.append((label, var))
            covered += var
        residual = (net_fact - net_budget) - covered
        if abs(residual) > 1:
            steps.append(("Прочее (без бюджета)", residual))
        show_bridge(bf_kind, "Бюджет ЧП", net_budget, steps, "Факт ЧП", net_fact,
                         f"Бюджет → Факт чистой прибыли · {period_label}",
                         "Вклад статей в отклонение (тыс. USD)")
        insight_box(net_fact - net_budget, steps)
    else:
        fmonths = [m for m in months if m in FACT_MONTHS]
        if not fmonths:
            st.warning("За выбранный период нет фактических данных по сегментам (факт по июнь).")
        else:
            budget = seg_sum(seg_margin_budget, fmonths)
            fact_seg = seg_sum(seg_margin_fact, fmonths)
            tot_b = sum(seg_margin_total(m, "budget") for m in fmonths)
            tot_f = sum(seg_margin_total(m, "fact") for m in fmonths)
            steps = seg_steps(fact_seg, budget)
            residual = (tot_f - tot_b) - sum(d for _, d in steps)
            if abs(residual) > 1:
                steps.append(("Прочие (other, agent и др.)", residual))
            plabel = (MONTH_NAMES_RU[fmonths[0] - 1] if len(fmonths) == 1
                      else f"{MONTH_NAMES_RU[fmonths[0] - 1]} — {MONTH_NAMES_RU[fmonths[-1] - 1]}")
            show_bridge(bf_kind, "Бюджет маржи", tot_b, steps, "Факт маржи", tot_f,
                             f"Бюджет → Факт маржинальной прибыли по сегментам · {plabel}",
                             "Вклад каждого сегмента в отклонение от плана (тыс. USD)")
            insight_box(tot_f - tot_b, steps, subject="Маржинальная прибыль")

    # ===================== ОБЩИЙ СВОД: все метрики =====================
    st.markdown("---")
    chart_card_open(f"📋 Общий свод · все метрики · {period_label}",
                    "факт vs план по всем статьям P&L")
    table, dev_info = [], []   # dev_info: (откл. в исходных ед., is_pct)
    for label, m_rows_, m_fmt_ in PL_FULL_METRICS:
        if m_fmt_ == "pct":
            fvals = [pl_rows_value(rows, m_rows_, m, "fact") for m in months]
            pvals = [pl_rows_value(rows, m_rows_, m, "budget") for m in months]
            f = sum(fvals) / len(fvals) if fvals else 0
            p = sum(pvals) / len(pvals) if pvals else 0
            dev = f - p
            fact_s, plan_s = f"{f * 100:.2f}%", (f"{p * 100:.2f}%" if p else "—")
            dev_s = (f"{dev * 100:+.2f} п.п." if p else "—")
            done_s = "—"
        else:
            f = sum(pl_rows_value(rows, m_rows_, m, "fact") for m in months)
            p = sum(pl_rows_value(rows, m_rows_, m, "budget") for m in months)
            dev = f - p
            fact_s, plan_s = fmt_kusd(f), (fmt_kusd(p) if p else "—")
            dev_s = fmt_kusd(dev)
            if not p:
                done_s = "—"                       # плана нет
            elif abs(p) < 10 or f * p < 0:
                done_s = "n/m"                     # план ≈ 0 или смена знака → % не показателен
            else:
                done_s = f"{f / p * 100:.1f}%"
        table.append({"Метрика": label.strip(), "Факт": fact_s, "План": plan_s,
                      "Отклонение": dev_s, "Выполнение": done_s})
        dev_info.append((dev, m_fmt_ == "pct"))

    # Оттенки отклонения по смыслу: рост ЧП (откл.≥0) — зелёный, иначе красный;
    # яркость — по величине, нормировка отдельно для денег и для процентов.
    mmax = max((abs(d) for d, ip in dev_info if not ip), default=1) or 1
    pmax = max((abs(d) for d, ip in dev_info if ip), default=1) or 1

    def _dev_styles(col):
        out = []
        for i in range(len(col)):
            d, ip = dev_info[i]
            scale = pmax if ip else mmax
            inten = min(1.0, abs(d) / scale) if scale else 0
            a = 0.12 + 0.5 * inten
            if d >= 0:
                out.append(f"background-color: rgba(47,217,166,{a:.2f}); color:#EAFBF4")
            else:
                out.append(f"background-color: rgba(255,92,122,{a:.2f}); color:#FFECF0")
        return out

    df_svod = pd.DataFrame(table)
    styler = (df_svod.style
              .apply(_dev_styles, subset=["Отклонение"])
              .set_properties(subset=["Факт", "План", "Отклонение", "Выполнение"],
                              **{"text-align": "right"}))
    st.dataframe(styler, use_container_width=True, hide_index=True)
    st.caption("Цвет «Отклонения»: зелёный — вклад в рост чистой прибыли, "
               "красный — снижение; насыщенность отражает размер отклонения. "
               "**n/m** в «Выполнении» — план ≈ 0 или смена знака, % не показателен.")
    chart_card_close()

    # ----- Общий анализ под сводом -----
    net_b = pl_sum("net_profit", from_m, to_m, "budget")
    net_f = pl_sum("net_profit", from_m, to_m, "fact")
    gp_b = pl_sum("gross_profit", from_m, to_m, "budget")
    gp_f = pl_sum("gross_profit", from_m, to_m, "fact")
    opex_b = pl_sum("opex", from_m, to_m, "budget")
    opex_f = pl_sum("opex", from_m, to_m, "fact")

    drivers = []
    for row_list, label in PNL_FACTORS:
        bud = sum(pl_rows_value(rows, row_list, m, "budget") for m in months)
        fct = sum(pl_rows_value(rows, row_list, m, "fact") for m in months)
        var = fct - bud
        if abs(var) >= 0.5:
            drivers.append((label, var, bud, fct))
    helped = sorted([d for d in drivers if d[1] > 0], key=lambda s: -s[1])[:3]
    hurt = sorted([d for d in drivers if d[1] < 0], key=lambda s: s[1])[:3]

    def _drv(l, d, b, f):
        # % к плану статьи — только когда показателен:
        if abs(b) < 10:                 # план практически нулевой
            note = ", план ≈ 0"
        elif f * b < 0:                 # факт и план разного знака — % обманчив
            note = ", смена знака"
        else:
            note = f", {d / abs(b) * 100:+.0f}%"
        return f"{l} ({fmt_kusd(d)}{note})"

    net_dev = net_f - net_b
    parts = [f"#### 🧭 Общий анализ · {period_label}"]
    if net_b:
        parts.append(
            f"**Чистая прибыль** составила {fmt_kusd(net_f)} против плана {fmt_kusd(net_b)} — "
            f"{'выше' if net_dev >= 0 else 'ниже'} плана на {fmt_kusd(abs(net_dev))} "
            f"({net_f / net_b * 100 - 100:+.0f}%).")
    else:
        parts.append(f"**Чистая прибыль** составила {fmt_kusd(net_f)} (план не задан).")
    if gp_b:
        parts.append(
            f"**Валовая прибыль (маржа)** — {fmt_kusd(gp_f)} при плане {fmt_kusd(gp_b)} "
            f"({'+' if gp_f >= gp_b else '−'}{fmt_kusd(abs(gp_f - gp_b))}, "
            f"{gp_f / gp_b * 100 - 100:+.0f}%).")
    if opex_b:
        over = opex_f - opex_b   # расходы хранятся со знаком «−»: over<0 ⇒ перерасход
        parts.append(
            f"**OPEX** — {fmt_kusd(opex_f)} при плане {fmt_kusd(opex_b)} "
            f"({'экономия' if over >= 0 else 'перерасход'} {fmt_kusd(abs(over))}, "
            f"{over / abs(opex_b) * 100:+.0f}%).")
    if helped:
        parts.append("**Рост за счёт:** "
                     + ", ".join(_drv(l, d, b, f) for l, d, b, f in helped) + ".")
    if hurt:
        parts.append("**Снижение за счёт:** "
                     + ", ".join(_drv(l, d, b, f) for l, d, b, f in hurt) + ".")
    st.markdown(_md("\n\n".join(parts)))

# ========================= ПЕРИОД К ПЕРИОДУ =========================
with tab_pp:
    dim2 = inline_radio("Разрез", ["Сегменты (маржа)", "Статьи P&L"], "ao_pp_dim")
    pp_kind = inline_radio("Вид", ["Мостик", "Вклад (бары)"], "ao_pp_kind")

    if dim2 == "Статьи P&L":
        c1, c2 = st.columns(2)
        with c1:
            cur_m = st.selectbox("Текущий месяц", list(range(1, 13)),
                                 format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                 index=TARGET_MONTH - 1, key="ao_pp_cur")
        with c2:
            prev_m = st.selectbox("Сравнить с месяцем", list(range(1, 13)),
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1],
                                  index=max(0, TARGET_MONTH - 2), key="ao_pp_prev")
        net_prev = pl_sum("net_profit", prev_m, prev_m, "fact")
        net_cur = pl_sum("net_profit", cur_m, cur_m, "fact")
        steps = []
        for row_list, label in PNL_FACTORS:
            delta = (pl_rows_value(rows, row_list, cur_m, "fact")
                     - pl_rows_value(rows, row_list, prev_m, "fact"))
            if abs(delta) > 1:
                steps.append((label, delta))
        show_bridge(pp_kind, f"ЧП {MONTH_NAMES_RU[prev_m - 1]}", net_prev, steps,
                         f"ЧП {MONTH_NAMES_RU[cur_m - 1]}", net_cur,
                         f"Чистая прибыль: {MONTH_NAMES_RU[prev_m - 1]} → {MONTH_NAMES_RU[cur_m - 1]} {TARGET_YEAR}",
                         "Вклад статей в изменение (тыс. USD)")
        insight_box(net_cur - net_prev, steps)
    else:
        if len(FACT_MONTHS) < 2:
            st.warning("Недостаточно фактических месяцев по сегментам.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                sc = st.selectbox("Текущий месяц", FACT_MONTHS, index=len(FACT_MONTHS) - 1,
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_pp_seg_cur")
            with c2:
                sp = st.selectbox("Сравнить с месяцем", FACT_MONTHS, index=len(FACT_MONTHS) - 2,
                                  format_func=lambda x: MONTH_NAMES_RU[x - 1], key="ao_pp_seg_prev")
            fact_cur = seg_margin_fact(sc)
            fact_prev = seg_margin_fact(sp)
            tot_cur = seg_margin_total(sc, "fact")
            tot_prev = seg_margin_total(sp, "fact")
            steps = seg_steps(fact_cur, fact_prev)
            residual = (tot_cur - tot_prev) - sum(d for _, d in steps)
            if abs(residual) > 1:
                steps.append(("Прочие (other, agent и др.)", residual))
            show_bridge(pp_kind, f"Маржа {MONTH_NAMES_RU[sp - 1]}", tot_prev, steps,
                             f"Маржа {MONTH_NAMES_RU[sc - 1]}", tot_cur,
                             f"Маржинальная прибыль по сегментам: {MONTH_NAMES_RU[sp - 1]} → {MONTH_NAMES_RU[sc - 1]} {TARGET_YEAR}",
                             "Вклад каждого сегмента в изменение (тыс. USD)")
            insight_box(tot_cur - tot_prev, steps, subject="Маржинальная прибыль")
