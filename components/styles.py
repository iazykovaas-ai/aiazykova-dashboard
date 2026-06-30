import plotly.graph_objects as go
import streamlit as st

PALETTE = {
    "bg": "#0A0E20",        # глубокий тёмно-синий фон
    "sidebar": "#0E1430",   # боковое меню
    "card": "#141A33",      # панели-карточки
    "ink": "#E8EAF6",       # основной текст (почти белый)
    "muted": "#8A90B8",     # приглушённый текст / подписи осей
    "line": "#262E52",      # сетка / границы
    "primary": "#7B6FF0",   # сиренево-фиолетовый акцент
    "success": "#2FD9A6",   # неоновый зелёный (рост)
    "danger": "#FF5C7A",    # розово-красный (падение)
    "warning": "#F5B544",   # янтарный
}

# Неоновая палитра серий (как в Сбер-навигаторе): голубой, маджента, зелёный, фиолетовый…
CHART_COLORS = [
    "#36C5F0",  # голубой неон
    "#E94FA1",  # маджента
    "#2FD9A6",  # бирюзово-зелёный
    "#8B7BF0",  # фиолетовый
    "#4A7DFF",  # синий
    "#F5B544",  # янтарный
    "#FF8AC4",  # розовый
    "#3FE0C5",  # бирюза
]

_CSS = """
<style>
    /* ===== База: тёмный сине-фиолетовый фон со свечениями ===== */
    .stApp {
        background:
            radial-gradient(900px circle at 12% -5%, rgba(123, 111, 240, 0.18) 0%, transparent 45%),
            radial-gradient(1100px circle at 95% 0%, rgba(54, 197, 240, 0.12) 0%, transparent 45%),
            radial-gradient(900px circle at 80% 110%, rgba(233, 79, 161, 0.10) 0%, transparent 45%),
            linear-gradient(160deg, #0A0E20 0%, #0C1230 55%, #0A0E22 100%);
        background-attachment: fixed;
    }
    html, body, [class*="css"] {
        font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #E8EAF6;
    }

    header[data-testid="stHeader"] { background: transparent; height: 0; }
    #MainMenu, footer { visibility: hidden; }

    /* ===== Sidebar ===== */
    [data-testid="stSidebar"] {
        background: rgba(14, 20, 48, 0.92);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(8px);
    }
    [data-testid="stSidebarNav"] a {
        border-radius: 10px;
        margin: 2px 8px;
        padding: 8px 12px !important;
        font-weight: 500;
        color: #AEB4D8 !important;
    }
    [data-testid="stSidebarNav"] a:hover {
        background: rgba(123, 111, 240, 0.16);
        color: #FFFFFF !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: linear-gradient(90deg, rgba(123, 111, 240, 0.28), rgba(54, 197, 240, 0.12));
        color: #FFFFFF !important;
    }

    /* Переименовать пункт меню главной страницы (app -> Дэшборд ВЭД-агентства) */
    [data-testid="stSidebarNav"] ul li:first-child a span { display: none; }
    [data-testid="stSidebarNav"] ul li:first-child a::after {
        content: "Дэшборд ВЭД-агентства";
        font-weight: 600;
        color: #C7CCEC;
    }
    [data-testid="stSidebarNav"] ul li:first-child a[aria-current="page"]::after { color: #FFFFFF; }

    /* Последний пункт (Сегменты) — пока в разработке: зачёркнуто + «(в работе)» */
    [data-testid="stSidebarNav"] ul li:last-child a span { display: none; }
    [data-testid="stSidebarNav"] ul li:last-child a::after {
        content: "С̶е̶г̶м̶е̶н̶т̶ы̶ (в работе)";
        font-weight: 600;
        color: #8A90B8;
    }

    /* ===== Заголовки ===== */
    h1, h2, h3, h4 { color: #F2F3FA; letter-spacing: -0.02em; }
    h1 { font-weight: 700; }
    h2 { font-weight: 650; }
    h3 { font-weight: 600; font-size: 1.05rem; color: #C7CCEC; }

    /* ===== KPI ===== */
    [data-testid="stMetric"] {
        background: linear-gradient(160deg, rgba(24, 31, 60, 0.95) 0%, rgba(18, 24, 48, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 18px;
        padding: 20px 22px;
        min-height: 150px;            /* все карточки одной высоты */
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        box-shadow:
            0 8px 26px rgba(0, 0, 0, 0.35),
            inset 0 1px 0 rgba(255, 255, 255, 0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: rgba(123, 111, 240, 0.45);
        box-shadow: 0 14px 34px rgba(64, 50, 140, 0.40);
    }
    [data-testid="stMetricLabel"] {
        color: #8A90B8;
        font-size: 0.74rem !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        min-height: 2.5em;   /* резерв под 2 строки — карточки одной высоты */
        /* Перенос на 2 строки вместо «…» */
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.25;
    }
    [data-testid="stMetricLabel"] > div,
    [data-testid="stMetricLabel"] p {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        word-break: break-word;
    }
    [data-testid="stMetricValue"] {
        color: #FFFFFF;
        font-size: clamp(1.2rem, 2.2vw, 1.9rem) !important;
        font-weight: 700;
        letter-spacing: -0.02em;
        white-space: nowrap;
    }
    [data-testid="stMetricDelta"] { font-size: 0.85rem; font-weight: 600; }

    /* ===== Карточка-обёртка для графика ===== */
    .chart-card {
        background: linear-gradient(160deg, rgba(22, 28, 55, 0.92) 0%, rgba(16, 22, 44, 0.92) 100%);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 18px;
        padding: 22px 24px 16px;
        box-shadow: 0 8px 26px rgba(0, 0, 0, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.03);
        margin-bottom: 18px;
    }
    .chart-card h4 {
        margin: 0 0 6px 0;
        font-size: 0.98rem;
        font-weight: 600;
        color: #F2F3FA;
    }
    .chart-card .subtitle {
        color: #8A90B8;
        font-size: 0.82rem;
        margin: 0 0 14px 0;
    }

    /* ===== Hero с неоновым градиентом ===== */
    .hero {
        background:
            radial-gradient(circle at 18% 20%, rgba(123, 111, 240, 0.45) 0%, transparent 55%),
            radial-gradient(circle at 82% 75%, rgba(54, 197, 240, 0.28) 0%, transparent 55%),
            radial-gradient(circle at 60% 50%, rgba(233, 79, 161, 0.16) 0%, transparent 60%),
            linear-gradient(135deg, #1A1B43 0%, #141A3A 60%, #101637 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 22px;
        padding: 30px 34px;
        margin-bottom: 24px;
        box-shadow: 0 12px 34px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    .hero h1 { color: #FFFFFF; margin: 0; font-size: 1.8rem; }
    .hero p { color: #B6BCE4; margin: 8px 0 0; font-size: 0.95rem; }

    /* ===== Таблицы ===== */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.07);
    }

    /* ===== Табы ===== */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(20, 26, 51, 0.6);
        padding: 5px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        border-radius: 9px;
        padding: 6px 16px;
        color: #AEB4D8;
    }
    [data-testid="stTabs"] [aria-selected="true"] {
        background: linear-gradient(90deg, rgba(123, 111, 240, 0.85), rgba(54, 197, 240, 0.55)) !important;
        color: #FFFFFF !important;
    }

    /* ===== Ссылки-разделы (page_link как карточки) ===== */
    [data-testid="stPageLink"] a {
        font-weight: 600 !important;
        font-size: 1.04rem !important;
        color: #F2F3FA !important;
        padding: 4px 2px !important;
    }
    [data-testid="stPageLink"] a:hover {
        color: #B7AEFF !important;
    }

    /* ===== Info ===== */
    [data-testid="stAlert"] {
        border-radius: 12px;
        border: 1px solid rgba(123, 111, 240, 0.25);
        background: rgba(123, 111, 240, 0.10);
        color: #C7CCEC;
        padding: 14px 18px;
    }

    /* ===== Expander ===== */
    [data-testid="stExpander"] {
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        background: rgba(20, 26, 51, 0.5);
    }

    hr { border-color: rgba(255, 255, 255, 0.08); margin: 1.2rem 0; }

    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }

    /* Скроллбар */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: #0A0E20; }
    ::-webkit-scrollbar-thumb { background: #2A3360; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #3A4680; }
</style>
"""


def apply():
    st.markdown(_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="hero"><h1>{title}</h1>'
        + (f"<p>{subtitle}</p>" if subtitle else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def chart_card_open(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="chart-card"><h4>{title}</h4>'
        + (f'<div class="subtitle">{subtitle}</div>' if subtitle else ""),
        unsafe_allow_html=True,
    )


def chart_card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def style_plotly_3d(fig, height: int = 460):
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=10, t=10, b=25),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif",
                  color=PALETTE["ink"], size=12),
        hoverlabel=dict(
            bgcolor="#1B2247",
            bordercolor=PALETTE["primary"],
            font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif",
                      size=15, color=PALETTE["ink"]),
            align="left",
            namelength=-1,   # не обрезать длинные подписи
        ),
        scene=dict(
            bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                backgroundcolor="rgba(0,0,0,0)",
                gridcolor=PALETTE["line"],
                zerolinecolor=PALETTE["line"],
                color=PALETTE["muted"],
                showspikes=False,
            ),
            yaxis=dict(
                backgroundcolor="rgba(0,0,0,0)",
                gridcolor=PALETTE["line"],
                zerolinecolor=PALETTE["line"],
                color=PALETTE["muted"],
                showspikes=False,
            ),
            zaxis=dict(
                backgroundcolor="rgba(0,0,0,0)",
                gridcolor=PALETTE["line"],
                zerolinecolor=PALETTE["line"],
                color=PALETTE["muted"],
                showspikes=False,
            ),
            camera=dict(eye=dict(x=1.6, y=-1.7, z=1.1)),
            aspectmode="manual",
            aspectratio=dict(x=1.4, y=1, z=0.9),
        ),
    )
    return fig


def wrap_label(s, width: int = 12) -> str:
    """Переносит длинную подпись на несколько строк (<br>) по словам — для осей графиков."""
    words = str(s).split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "<br>".join(lines)


def col_separators(n: int, color: str = "rgba(150,160,200,0.16)", y0: float = -0.32):
    """Бледные пунктирные вертикальные разделители между n столбцами (по границам).
    Для вертикальных баров. Возвращает shapes для fig.update_layout(shapes=...)."""
    return [dict(type="line", xref="x", yref="paper", x0=k + 0.5, x1=k + 0.5,
                 y0=y0, y1=1, layer="below",
                 line=dict(color=color, width=1, dash="dot"))
            for k in range(n - 1)]


def row_separators(n: int, color: str = "rgba(150,160,200,0.16)", x0: float = -0.30):
    """Бледные пунктирные горизонтальные разделители между n строками (по границам).
    Для горизонтальных баров; протянуты влево в зону подписей."""
    return [dict(type="line", yref="y", xref="paper", y0=k + 0.5, y1=k + 0.5,
                 x0=x0, x1=1, layer="below",
                 line=dict(color=color, width=1, dash="dot"))
            for k in range(n - 1)]


def style_plotly_2d(fig, height: int = 340):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif",
                  color=PALETTE["ink"], size=12),
        colorway=CHART_COLORS,
        hoverlabel=dict(bgcolor="#1B2247", font_size=12,
                        font_color=PALETTE["ink"], bordercolor=PALETTE["primary"]),
        xaxis=dict(gridcolor=PALETTE["line"], zerolinecolor=PALETTE["line"],
                   color=PALETTE["muted"]),
        yaxis=dict(gridcolor=PALETTE["line"], zerolinecolor=PALETTE["line"],
                   color=PALETTE["muted"]),
    )
    return fig


def cuboid_mesh(x0, x1, y0, y1, z0, z1, color, name=""):
    """3D-кубоид через Mesh3d (12 треугольников)."""
    x = [x0, x1, x1, x0, x0, x1, x1, x0]
    y = [y0, y0, y1, y1, y0, y0, y1, y1]
    z = [z0, z0, z0, z0, z1, z1, z1, z1]
    # 12 треугольников = 6 граней × 2
    i = [0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6]
    k = [2, 3, 6, 7, 5, 4, 6, 7, 7, 4, 6, 5]
    return go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k,
        color=color, name=name,
        flatshading=True, opacity=1.0, showscale=False,
        lighting=dict(ambient=0.55, diffuse=0.9, specular=0.32,
                      roughness=0.4, fresnel=0.15),
        lightposition=dict(x=100, y=200, z=200),
        hoverinfo="name",
    )


def sparkline(values, color: str = "#36C5F0", height: int = 70):
    """Мини-график тренда под KPI (без осей, прозрачный фон)."""
    vals = list(values)
    while vals and vals[-1] == 0:   # обрезаем хвост из будущих (нулевых) месяцев
        vals.pop()
    if not vals:
        vals = [0]
    if color.startswith("#") and len(color) == 7:
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fill = f"rgba({r},{g},{b},0.15)"
    else:
        fill = color
    fig = go.Figure(go.Scatter(
        x=list(range(len(vals))), y=vals, mode="lines",
        line=dict(color=color, width=2, shape="spline"),
        fill="tozeroy", fillcolor=fill,
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=2, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def gauge(value: float, title: str = "", vmax: float = 150, target: float = 100,
          suffix: str = "%", color: str = "#2FD9A6", height: int = 230):
    """Спидометр (gauge) с порогом-целью."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(suffix=suffix, font=dict(color="#FFFFFF", size=30)),
        title=dict(text=title, font=dict(color="#C7CCEC", size=14)),
        gauge=dict(
            axis=dict(range=[0, vmax], tickcolor="#8A90B8",
                      tickfont=dict(color="#8A90B8", size=10)),
            bar=dict(color=color, thickness=0.28),
            bgcolor="rgba(255,255,255,0.04)",
            bordercolor="rgba(255,255,255,0.08)", borderwidth=1,
            steps=[
                dict(range=[0, target * 0.7], color="rgba(255,92,122,0.12)"),
                dict(range=[target * 0.7, target], color="rgba(245,181,68,0.12)"),
                dict(range=[target, vmax], color="rgba(47,217,166,0.12)"),
            ],
            threshold=dict(line=dict(color="#FF5C7A", width=3), thickness=0.85, value=target),
        ),
    ))
    fig.update_layout(
        height=height, margin=dict(l=24, r=24, t=46, b=8),
        paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#E8EAF6"),
    )
    return fig


def mom_colors(values, base_color="#8B7BF0", up="47,217,166", down="255,92,122"):
    """Цвета баров по динамике к предыдущему значению: рост — зелёный, снижение — красный;
    насыщенность пропорциональна силе % изменения. Возвращает (colors, changes)."""
    chg = [None]
    for i in range(1, len(values)):
        p = values[i - 1]
        chg.append((values[i] - p) / abs(p) * 100 if p else 0.0)
    maxmag = max((abs(c) for c in chg if c is not None), default=1) or 1
    colors = []
    for c in chg:
        if c is None:
            colors.append(base_color)
        else:
            a = 0.35 + 0.65 * min(abs(c) / maxmag, 1.0)
            colors.append(f"rgba({up if c >= 0 else down},{a:.2f})")
    return colors, chg


def bar3d(labels, values, formatter=str):
    """3D bar chart. labels - X categories, values - Z heights."""
    fig = go.Figure()
    for i, (label, val) in enumerate(zip(labels, values)):
        color = CHART_COLORS[i % len(CHART_COLORS)]
        fig.add_trace(cuboid_mesh(
            x0=i - 0.35, x1=i + 0.35,
            y0=-0.35, y1=0.35,
            z0=0, z1=val,
            color=color, name=f"{label}: {formatter(val)}",
        ))
    fig.update_layout(
        scene=dict(
            xaxis=dict(tickmode="array", tickvals=list(range(len(labels))),
                       ticktext=labels, title=""),
            yaxis=dict(showticklabels=False, title=""),
            zaxis=dict(title=""),
        ),
        showlegend=False,
    )
    return fig
