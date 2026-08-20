"""
app.py

App Streamlit para explorar interactivamente market_data.csv (generado
por fetch_data.py). Permite filtrar por índice, valoración, crecimiento
y calidad, y al seleccionar una empresa muestra una ficha estilo
Finviz/ScreenerHero con gráfico de precio.

Uso:
    streamlit run app.py

Requiere que market_data.csv exista en la misma carpeta (ejecuta
fetch_data.py primero, o usa run_screener.bat).
"""

import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Screener", layout="wide")

DATA_CSV = "market_data.csv"


@st.cache_data(ttl=3600)
def load_data():
    return pd.read_csv(DATA_CSV)


@st.cache_data(ttl=1800)
def load_price_history(ticker, period="1y"):
    return yf.Ticker(ticker).history(period=period)


@st.cache_data(ttl=3600)
def load_ticker_extra(ticker):
    """Datos adicionales que no están en el CSV masivo (descripción,
    sector, industria, empleados...) para la ficha estilo Finviz."""
    info = yf.Ticker(ticker).info
    return {
        "sector": info.get("sector", "-"),
        "industria": info.get("industry", "-"),
        "empleados": info.get("fullTimeEmployees", "-"),
        "resumen": info.get("longBusinessSummary", ""),
        "web": info.get("website", ""),
        "target_price": info.get("targetMeanPrice"),
        "recomendacion": info.get("recommendationKey", "-"),
        "beta": info.get("beta"),
        "dividend_yield": info.get("dividendYield"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
    }


VALUATION_PRESETS = [
    ("Cualquiera", None, None),
    ("Positivo (>0)", 0, None),
    ("Bajo (<10)", None, 10),
    ("Bajo (<15)", None, 15),
    ("Bajo (<20)", None, 20),
    ("Bajo (<30)", None, 30),
    ("Bajo (<50)", None, 50),
    ("Alto (>50)", 50, None),
    ("Negativo (<0)", None, 0),
    ("Personalizado", "custom", "custom"),
]

GROWTH_PRESETS = [
    ("Cualquiera", None, None),
    ("Positivo (>0%)", 0, None),
    ("Over 5%", 5, None),
    ("Over 10%", 10, None),
    ("Over 15%", 15, None),
    ("Over 20%", 20, None),
    ("Over 30%", 30, None),
    ("Over 50%", 50, None),
    ("Negativo (<0%)", None, 0),
    ("Personalizado", "custom", "custom"),
]

RATIO_PRESETS = [
    ("Cualquiera", None, None),
    ("Bajo (<1)", None, 1),
    ("Bajo (<2)", None, 2),
    ("Moderado (<0.5)", None, 0.5),
    ("Alto (>2)", 2, None),
    ("Personalizado", "custom", "custom"),
]

# Market Cap en miles de millones (B), igual que la columna del CSV.
# Umbrales estilo Finviz: Mega >=200B, Large 10-200B, Mid 2-10B,
# Small 0.3-2B, Micro 0.05-0.3B, Nano <0.05B (50M).
MCAP_PRESETS = [
    ("Cualquiera", None, None),
    ("Mega (200bln+)", 200, None),
    ("Large (10bln-200bln)", 10, 200),
    ("Mid (2bln-10bln)", 2, 10),
    ("Small (300mln-2bln)", 0.3, 2),
    ("Micro (50mln-300mln)", 0.05, 0.3),
    ("Nano (under 50mln)", None, 0.05),
    ("+Large (over 10bln)", 10, None),
    ("+Mid (over 2bln)", 2, None),
    ("+Small (over 300mln)", 0.3, None),
    ("+Micro (over 50mln)", 0.05, None),
    ("-Large (under 200bln)", None, 200),
    ("-Mid (under 10bln)", None, 10),
    ("-Small (under 2bln)", None, 2),
    ("-Micro (under 300mln)", None, 0.3),
    ("Personalizado", "custom", "custom"),
]


def finviz_filter(col, label, kind="growth", key_prefix=""):
    """Dropdown de presets estilo Finviz/ScreenerHero (Any, Over X%,
    Positive, Negative...) con opción de rango personalizado. Devuelve
    (min, max) o None si no se aplica filtro."""
    presets = {"valuation": VALUATION_PRESETS, "growth": GROWTH_PRESETS, "ratio": RATIO_PRESETS, "mcap": MCAP_PRESETS}[kind]
    labels = [p[0] for p in presets]
    key = f"{key_prefix}_{col}"
    choice = st.selectbox(label, labels, key=key)
    lo, hi = dict((p[0], (p[1], p[2])) for p in presets)[choice]

    if lo == "custom":
        c1, c2 = st.columns(2)
        min_v = c1.number_input("Min", value=None, key=f"{key}_min", format="%.2f", placeholder="Min")
        max_v = c2.number_input("Max", value=None, key=f"{key}_max", format="%.2f", placeholder="Max")
        if min_v is None and max_v is None:
            return None
        return (min_v, max_v)

    if lo is None and hi is None:
        return None
    return (lo, hi)


def apply_finviz_filter(df, col, sel, allow_na=True):
    if sel is None:
        return pd.Series(True, index=df.index)
    lo, hi = sel
    serie = pd.to_numeric(df[col], errors="coerce")
    mask = pd.Series(True, index=df.index)
    if lo is not None:
        mask &= serie >= lo
    if hi is not None:
        mask &= serie <= hi
    if allow_na:
        mask = mask | serie.isna()
    else:
        mask = mask & serie.notna()
    return mask


def main():
    st.title("📊 Stock Screener")

    try:
        df = load_data()
    except FileNotFoundError:
        st.error(
            f"No se encuentra {DATA_CSV} en esta carpeta. "
            "Ejecuta fetch_data.py primero (o run_screener.bat)."
        )
        return

    ignorar_na = st.checkbox(
        "Incluir empresas con dato faltante en un filtro (en vez de excluirlas)",
        value=True,
    )

    sels = {}
    tab_desc, tab_val, tab_gro, tab_rent, tab_sal = st.tabs(
        ["🏷️ Descriptivo", "💰 Valoración", "📈 Crecimiento", "⭐ Rentabilidad", "🏦 Salud Financiera"]
    )

    with tab_desc:
        indices_disponibles = sorted(df["Índice"].dropna().unique().tolist())
        indices_sel = st.multiselect(
            "Índices", indices_disponibles, default=indices_disponibles
        )
        sels["Market Cap (B)"] = finviz_filter("Market Cap (B)", "Market Cap", "mcap", "desc")

    df_f = df[df["Índice"].isin(indices_sel)] if indices_sel else df.copy()

    with tab_val:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sels["PER (Trailing)"] = finviz_filter("PER (Trailing)", "PER (Trailing)", "valuation", "val")
            sels["EV/EBITDA"] = finviz_filter("EV/EBITDA", "EV/EBITDA", "valuation", "val")
        with c2:
            sels["PER (Forward)"] = finviz_filter("PER (Forward)", "PER (Forward)", "valuation", "val")
            sels["EV/Sales"] = finviz_filter("EV/Sales", "EV/Sales", "valuation", "val")
        with c3:
            sels["P/B"] = finviz_filter("P/B", "P/B", "valuation", "val")
            sels["PEG"] = finviz_filter("PEG", "PEG", "valuation", "val")
        with c4:
            sels["P/FCF"] = finviz_filter("P/FCF", "P/FCF", "valuation", "val")
            sels["P/S"] = finviz_filter("P/S", "P/S", "valuation", "val")

    with tab_gro:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sels["Crec. Ventas YoY (%)"] = finviz_filter("Crec. Ventas YoY (%)", "Crec. Ventas YoY", "growth", "gro")
        with c2:
            sels["Crec. Ventas 3Y (%)"] = finviz_filter("Crec. Ventas 3Y (%)", "Crec. Ventas 3Y", "growth", "gro")
        with c3:
            sels["Crec. EPS YoY (%)"] = finviz_filter("Crec. EPS YoY (%)", "Crec. EPS YoY", "growth", "gro")
        with c4:
            sels["Crec. EPS 3Y (%)"] = finviz_filter("Crec. EPS 3Y (%)", "Crec. EPS 3Y", "growth", "gro")

    with tab_rent:
        c1, c2, c3 = st.columns(3)
        with c1:
            sels["ROIC (%)"] = finviz_filter("ROIC (%)", "ROIC", "growth", "cal")
            sels["Margen Bruto (%)"] = finviz_filter("Margen Bruto (%)", "Margen Bruto", "growth", "cal")
        with c2:
            sels["ROE (%)"] = finviz_filter("ROE (%)", "ROE", "growth", "cal")
            sels["Margen Operativo (%)"] = finviz_filter("Margen Operativo (%)", "Margen Operativo", "growth", "cal")
        with c3:
            sels["ROA (%)"] = finviz_filter("ROA (%)", "ROA", "growth", "cal")
            sels["Margen Neto (%)"] = finviz_filter("Margen Neto (%)", "Margen Neto", "growth", "cal")

    with tab_sal:
        c1, c2, c3 = st.columns(3)
        with c1:
            sels["Debt/Equity"] = finviz_filter("Debt/Equity", "Debt/Equity", "ratio", "sal")
        with c2:
            sels["Current Ratio"] = finviz_filter("Current Ratio", "Current Ratio", "ratio", "sal")
        with c3:
            sels["Payout Ratio (%)"] = finviz_filter("Payout Ratio (%)", "Payout Ratio", "growth", "sal")

    mask = pd.Series(True, index=df_f.index)
    for col, sel in sels.items():
        mask &= apply_finviz_filter(df_f, col, sel, allow_na=ignorar_na)

    resultado = df_f[mask].sort_values("PER (Trailing)")

    st.subheader(f"Resultados: {len(resultado)} empresas")
    st.dataframe(resultado, use_container_width=True, height=350)

    st.markdown("---")
    st.subheader("🔎 Ficha de empresa")

    if resultado.empty:
        st.info("Ajusta los filtros para ver resultados y poder seleccionar una empresa.")
        return

    ticker_sel = st.selectbox(
        "Selecciona una empresa de los resultados para ver su ficha",
        resultado["Ticker"].tolist(),
        format_func=lambda t: f"{t} — {resultado.loc[resultado['Ticker'] == t, 'Nombre'].values[0]}",
    )

    ver_ficha = st.button("🔎 Ver ficha", type="primary")

    if not ticker_sel:
        return

    # Recuerda la última ficha cargada entre reruns (p.ej. al tocar
    # filtros) para no perderla, pero sin recargar datos de Yahoo salvo
    # que el usuario pulse el botón explícitamente.
    if ver_ficha:
        st.session_state["ficha_ticker"] = ticker_sel

    if "ficha_ticker" not in st.session_state:
        st.info("Pulsa \"Ver ficha\" para cargar el gráfico y los datos de la empresa seleccionada.")
        return

    ticker_sel = st.session_state["ficha_ticker"]
    if ticker_sel not in resultado["Ticker"].values:
        st.info("Pulsa \"Ver ficha\" para cargar el gráfico y los datos de la empresa seleccionada.")
        return

    row = resultado[resultado["Ticker"] == ticker_sel].iloc[0]

    with st.spinner(f"Cargando datos de {ticker_sel}..."):
        try:
            extra = load_ticker_extra(ticker_sel)
        except Exception:
            extra = {}
        try:
            hist = load_price_history(ticker_sel)
        except Exception:
            hist = pd.DataFrame()

    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.markdown(f"### {row['Nombre']} ({ticker_sel})")
        st.caption(f"{row['Índice']}  ·  {extra.get('sector', '-')} / {extra.get('industria', '-')}")

        if not hist.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=hist.index, open=hist["Open"], high=hist["High"],
                low=hist["Low"], close=hist["Close"], name=ticker_sel,
            )])
            fig.update_layout(
                height=400, margin=dict(l=10, r=10, t=30, b=10),
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No se pudo cargar el histórico de precio.")

        if extra.get("resumen"):
            with st.expander("Descripción del negocio"):
                st.write(extra["resumen"])

    with col_b:
        st.markdown("**Precio y valoración**")
        st.metric("Precio", f"{row['Precio']:.2f}")
        if extra.get("52w_high") and extra.get("52w_low"):
            st.caption(f"Rango 52 semanas: {extra['52w_low']:.2f} – {extra['52w_high']:.2f}")
        if extra.get("target_price"):
            st.caption(f"Precio objetivo (consenso): {extra['target_price']:.2f}")
        if extra.get("recomendacion") and extra["recomendacion"] != "-":
            st.caption(f"Recomendación consenso: {extra['recomendacion']}")

        st.markdown("---")
        stats = {
            "PER (Trailing)": row.get("PER (Trailing)"),
            "PER (Forward)": row.get("PER (Forward)"),
            "P/B": row.get("P/B"),
            "P/FCF": row.get("P/FCF"),
            "P/S": row.get("P/S"),
            "PEG": row.get("PEG"),
            "EV/EBITDA": row.get("EV/EBITDA"),
            "ROIC (%)": row.get("ROIC (%)"),
            "ROE (%)": row.get("ROE (%)"),
            "ROA (%)": row.get("ROA (%)"),
            "Margen Bruto (%)": row.get("Margen Bruto (%)"),
            "Margen Neto (%)": row.get("Margen Neto (%)"),
            "Debt/Equity": row.get("Debt/Equity"),
            "Current Ratio": row.get("Current Ratio"),
            "Crec. Ventas 3Y (%)": row.get("Crec. Ventas 3Y (%)"),
            "Crec. EPS 3Y (%)": row.get("Crec. EPS 3Y (%)"),
            "Market Cap (B)": row.get("Market Cap (B)"),
        }
        for k, v in stats.items():
            if pd.notna(v):
                st.write(f"**{k}:** {v:,.2f}")
            else:
                st.write(f"**{k}:** —")

        if extra.get("web"):
            st.markdown(f"[Web corporativa]({extra['web']})")


if __name__ == "__main__":
    main()
