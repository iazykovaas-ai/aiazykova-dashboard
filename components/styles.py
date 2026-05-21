import plotly.graph_objects as go
import streamlit as st

PALETTE = {
    "bg": "#ECEAF2",
    "sidebar": "#E2DFEB",
    "card": "#FFFFFF",
    "ink": "#2A2640",
    "muted": "#7A7592",
    "line": "#D8D4E2",
    "primary": "#9B86C7",
    "success": "#7FC9A8",
    "danger": "#E89A9A",
    "warning": "#E8B989",
}

CHART_COLORS = [
    "#B8A3DC",  # лаванда
    "#9DD8BE",  # мята
    "#F0C8A0",  # персик
    "#EFA9C0",  # пыльная роза
    "#A9C9EE",  # небо
    "#F0DBA0",  # ваниль
    "#C5B2EC",  # сирень
    "#B8DCC8",  # шалфей
]

_CSS = """
<style>
    /* ===== База ===== */
    .stApp { background: #ECEAF2; }
    html, body, [class*="css"] {
        font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #2A2640;
    }

    header[data-testid="stHeader"] { background: transparent; height: 0; }
    #MainMenu, footer { visibility: hidden; }

    /* ===== Sidebar ===== */
    [data-testid="stSidebar"] {
        background: #E2DFEB;
        border-right: 1px solid #D8D4E2;
    }
    [data-testid="stSidebarNav"] a {
        border-radius: 10px;
        margin: 2px 8px;
        padding: 8px 12px !important;
        font-weight: 500;
        color: #4A4566 !important;
    }
    [data-testid="stSidebarNav"] a:hover {
        background: #D4CFE0;
        color: #2A2640 !important;
    }

    /* ===== Заголовки ===== */
    h1, h2, h3, h4 { color: #2A2640; letter-spacing: -0.02em; }
    h1 { font-weight: 700; }
    h2 { font-weight: 650; }
    h3 { font-weight: 600; font-size: 1.05rem; color: #4A4566; }

    /* ===== KPI ===== */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #D8D4E2;
        border-radius: 18px;
        padding: 20px 22px;
        box-shadow:
            0 4px 14px rgba(80, 70, 120, 0.08),
            0 1px 2px rgba(80, 70, 120, 0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(80, 70, 120, 0.14);
    }
    [data-testid="stMetricLabel"] {
        color: #7A7592;
        font-size: 0.74rem !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
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
        color: #2A2640;
        font-size: clamp(1.2rem, 2.2vw, 1.9rem) !important;
        font-weight: 700;
        letter-spacing: -0.02em;
        white-space: nowrap;
    }
    [data-testid="stMetricDelta"] { font-size: 0.85rem; font-weight: 600; }

    /* ===== Карточка-обёртка для графика ===== */
    .chart-card {
        background: #FFFFFF;
        border: 1px solid #D8D4E2;
        border-radius: 18px;
        padding: 22px 24px 16px;
        box-shadow: 0 4px 14px rgba(80, 70, 120, 0.08);
        margin-bottom: 18px;
    }
    .chart-card h4 {
        margin: 0 0 6px 0;
        font-size: 0.98rem;
        font-weight: 600;
        color: #2A2640;
    }
    .chart-card .subtitle {
        color: #7A7592;
        font-size: 0.82rem;
        margin: 0 0 14px 0;
    }

    /* ===== Hero с пастельным градиентом ===== */
    .hero {
        background:
            radial-gradient(circle at 20% 20%, rgba(184, 163, 220, 0.55) 0%, transparent 55%),
            radial-gradient(circle at 80% 70%, rgba(157, 216, 190, 0.45) 0%, transparent 55%),
            linear-gradient(135deg, #DCD4EC 0%, #C8D8E8 100%);
        border: 1px solid #D8D4E2;
        border-radius: 22px;
        padding: 30px 34px;
        margin-bottom: 24px;
        box-shadow: 0 8px 24px rgba(80, 70, 120, 0.12);
    }
    .hero h1 { color: #2A2640; margin: 0; font-size: 1.8rem; }
    .hero p { color: #5A5476; margin: 8px 0 0; font-size: 0.95rem; }

    /* ===== Таблицы ===== */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #D8D4E2;
    }

    /* ===== Info ===== */
    [data-testid="stAlert"] {
        border-radius: 12px;
        border: none;
        background: #EFEAF7;
        color: #4A4566;
        padding: 14px 18px;
    }

    hr { border-color: #D8D4E2; margin: 1.2rem 0; }

    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }

    /* Скроллбар */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: #ECEAF2; }
    ::-webkit-scrollbar-thumb { background: #C8C2D6; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #B0A8C6; }
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
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif",
                  color=PALETTE["ink"], size=12),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
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


def style_plotly_2d(fig, height: int = 340):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif",
                  color=PALETTE["ink"], size=12),
        colorway=CHART_COLORS,
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12,
                        font_color=PALETTE["ink"], bordercolor=PALETTE["line"]),
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
        lighting=dict(ambient=0.65, diffuse=0.8, specular=0.2,
                      roughness=0.55, fresnel=0.1),
        lightposition=dict(x=100, y=200, z=200),
        hoverinfo="name",
    )


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
