"""
App Streamlit para explorar interactivamente market_data.csv (generado
por fetch_data.py). Permite filtrar por índice, valoración, crecimiento
y calidad, y al seleccionar una empresa muestra una ficha estilo
Finviz/ScreenerHero con gráfico de precio y métricas financieras detalladas.

Uso:
    streamlit run app.py
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
    """Datos adicionales de Yahoo Finance para la ficha completa (Ownership, 
    Cash Flow, Balance Sheet, Consenso de analistas, etc.)."""
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        info = {}

    return {
        "sector": info.get("sector", "-"),
        "industria": info.get("industry", "-"),
        "empleados": info.get("fullTimeEmployees", "-"),
        "resumen": info.get("longBusinessSummary", ""),
        "web": info.get("website", ""),
        "country": info.get("country", "-"),
        
        # Valoración / Objetivos
        "target_price": info.get("targetMeanPrice"),
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "recommendation": info.get("recommendationKey", "-"),
        "num_analysts": info.get("numberOfAnalystOpinions"),
        "beta": info.get("beta"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        
        # Profitability & Growth
        "rev_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "gross_margins": info.get("grossMargins"),
        "oper_margins": info.get("operatingMargins"),
        "profit_margins": info.get("profitMargins"),
        "ebitda_margins": info.get("ebitdaMargins"),
        "roa": info.get("returnOnAssets"),
        "roe": info.get("returnOnEquity"),
        
        # Cash Flow & Leverage
        "operating_cf": info.get("operatingCashflow"),
        "free_cf": info.get("freeCashflow"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "ebitda": info.get("ebitda"),
        
        # Balance Sheet
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "book_value": info.get("bookValue"),
        "cash_per_share": info.get("totalCashPerShare"),
        
        # Ownership
        "shares_out": info.get("sharesOutstanding"),
        "float_shares": info.get("floatShares"),
        "insiders_pct": info.get("heldPercentInsiders"),
        "institutions_pct": info.get("heldPercentInstitutions"),
        
        # Short Interest
        "short_ratio": info.get("shortRatio"),
        "short_pct_float": info.get("shortPercentOfFloat"),
        "shares_short": info.get("sharesShort"),
        "shares_short_prior": info.get("sharesShortPriorMonth"),
        
        # Dividends
        "div_rate": info.get("dividendRate"),
        "trail_div_rate": info.get("trailingAnnualDividendRate"),
        "div_yield": info.get("dividendYield"),
        "payout_ratio": info.get("payoutRatio"),
    }


def fmt_val(val, is_pct=False, is_money=False, multiplier=1.0):
    """Helper para formatear números de forma limpia (K, M, B, T, %)"""
    if val is None or pd.isna(val):
        return "—"
    try:
        num = float(val) * multiplier
        if is_pct:
            return f"{num * 100:.2f}%" if abs(num) <= 1.0 else f"{num:.2f}%"
        if is_money or abs(num) >= 1e6:
            if abs(num) >= 1e12:
                return f"{num / 1e12:.2f}T"
            elif abs(num) >= 1e9:
                return f"{num / 1e9:.2f}B"
            elif abs(num) >= 1e6:
                return f"{num / 1e6:.2f}M"
        return f"{num:,.2f}"
    except Exception:
        return str(val)


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

PB_PRESETS = [
    ("Cualquiera", None, None),
    ("Positivo (>0)", 0, None),
    ("Bajo (<1)", None, 1),
    ("Bajo (<2)", None, 2),
    ("Bajo (<3)", None, 3),
    ("Bajo (<5)", None, 5),
    ("Bajo (<10)", None, 10),
    ("Alto (>10)", 10, None),
    ("Negativo (<0)", None, 0),
    ("Personalizado", "custom", "custom"),
]

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
    presets = {"valuation": VALUATION_PRESETS, "growth": GROWTH_PRESETS, "ratio": RATIO_PRESETS, "mcap": MCAP_PRESETS, "pb": PB_PRESETS}[kind]
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
        return (min_v, max_v, label)

    if lo is None and hi is None:
        return None
    return (lo, hi, label)


def apply_finviz_filter(df, col, sel, allow_na=True):
    if sel is None:
        return pd.Series(True, index=df.index)
    lo, hi, _label = sel
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


def render_block(title, items):
    """Muestra un bloque de estadísticas con formato de clave - valor."""
    st.markdown(f"##### {title}")
    for label, val in items:
        st.markdown(f"**{label}:** {val}")
    st.markdown("---")


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
            sels["P/B"] = finviz_filter("P/B", "P/B", "pb", "val")
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

    activos = []
    if len(indices_sel) != len(indices_disponibles):
        activos.append(f"**Índices:** {', '.join(indices_sel) if indices_sel else 'ninguno'}")
    for col, sel in sels.items():
        if sel is None:
            continue
        lo, hi, label = sel
        if lo is not None and hi is not None:
            rango = f"{lo:g} – {hi:g}"
        elif lo is not None:
            rango = f"≥ {lo:g}"
        elif hi is not None:
            rango = f"≤ {hi:g}"
        else:
            continue
        activos.append(f"**{col}:** {label} ({rango})")

    if activos:
        st.caption("Filtros activos: " + "  ·  ".join(activos))
    else:
        st.caption("Sin filtros activos — mostrando todo el universo seleccionado.")

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

    # --- SECCIÓN SUPERIOR: GRÁFICO Y RESUMEN ---
    st.markdown(f"### {row['Nombre']} ({ticker_sel})")
    st.caption(f"{row['Índice']}  ·  {extra.get('sector', '-')} / {extra.get('industria', '-')}  ·  País: {extra.get('country', '-')}")

    if not hist.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=hist.index, open=hist["Open"], high=hist["High"],
            low=hist["Low"], close=hist["Close"], name=ticker_sel,
        )])
        fig.update_layout(
            height=420, margin=dict(l=10, r=10, t=20, b=10),
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No se pudo cargar el histórico de precio.")

    if extra.get("resumen"):
        with st.expander("Descripción del negocio"):
            st.write(extra["resumen"])

    # --- SECCIÓN INFERIOR: KEY STATISTICS EN BLOQUES (ESTILO FINVIZ) ---
    st.markdown("### 📋 Key Statistics")

    # Cálculos derivados para Cash Flow y Deuda Neta
    total_cash = extra.get("total_cash")
    total_debt = extra.get("total_debt")
    ebitda = extra.get("ebitda")

    net_debt = (total_debt - total_cash) if (total_debt is not None and total_cash is not None) else None
    net_debt_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda != 0) else None

    col1, col2, col3 = st.columns(3)

    # COLUMNA 1: COMPANY, VALUATION, PROFITABILITY
    with col1:
        render_block("COMPANY", [
            ("Market Cap", fmt_val(row.get("Market Cap (B)"), is_money=True, multiplier=1e9)),
            ("Price", f"{row.get('Precio', 0):.2f}"),
            ("Employees", fmt_val(extra.get("empleados"))),
            ("Country", extra.get("country", "-")),
            ("Sector", extra.get("sector", "-")),
            ("Industry", extra.get("industria", "-")),
        ])

        render_block("VALUATION", [
            ("P/E (Trailing)", fmt_val(row.get("PER (Trailing)"))),
            ("P/E (Forward)", fmt_val(row.get("PER (Forward)"))),
            ("PEG", fmt_val(row.get("PEG"))),
            ("EV/EBITDA", fmt_val(row.get("EV/EBITDA"))),
            ("EV/Sales", fmt_val(row.get("EV/Sales"))),
            ("P/S", fmt_val(row.get("P/S"))),
            ("P/B", fmt_val(row.get("P/B"))),
            ("P/FCF", fmt_val(row.get("P/FCF"))),
        ])

        render_block("PROFITABILITY", [
            ("Gross Margin", fmt_val(extra.get("gross_margins") or (row.get("Margen Bruto (%)") / 100 if pd.notna(row.get("Margen Bruto (%)")) else None), is_pct=True)),
            ("Oper. Margin", fmt_val(extra.get("oper_margins") or (row.get("Margen Operativo (%)") / 100 if pd.notna(row.get("Margen Operativo (%)")) else None), is_pct=True)),
            ("Profit Margin", fmt_val(extra.get("profit_margins") or (row.get("Margen Neto (%)") / 100 if pd.notna(row.get("Margen Neto (%)")) else None), is_pct=True)),
            ("ROE", fmt_val(extra.get("roe") or (row.get("ROE (%)") / 100 if pd.notna(row.get("ROE (%)")) else None), is_pct=True)),
            ("ROA", fmt_val(extra.get("roa") or (row.get("ROA (%)") / 100 if pd.notna(row.get("ROA (%)")) else None), is_pct=True)),
            ("ROIC", fmt_val(row.get("ROIC (%)") / 100 if pd.notna(row.get("ROIC (%)")) else None, is_pct=True)),
        ])

    # COLUMNA 2: GROWTH, CASH FLOW & LEVERAGE, BALANCE SHEET, DIVIDENDS
    with col2:
        render_block("GROWTH", [
            ("Revenue Growth", fmt_val(extra.get("rev_growth") or (row.get("Crec. Ventas YoY (%)") / 100 if pd.notna(row.get("Crec. Ventas YoY (%)")) else None), is_pct=True)),
            ("Earnings Growth", fmt_val(extra.get("earnings_growth") or (row.get("Crec. EPS YoY (%)") / 100 if pd.notna(row.get("Crec. EPS YoY (%)")) else None), is_pct=True)),
            ("Revenue Growth 3Y", fmt_val(row.get("Crec. Ventas 3Y (%)") / 100 if pd.notna(row.get("Crec. Ventas 3Y (%)")) else None, is_pct=True)),
            ("EPS Growth 3Y", fmt_val(row.get("Crec. EPS 3Y (%)") / 100 if pd.notna(row.get("Crec. EPS 3Y (%)")) else None, is_pct=True)),
        ])

        render_block("CASH FLOW & LEVERAGE", [
            ("Operating CF", fmt_val(extra.get("operating_cf"), is_money=True)),
            ("Free CF", fmt_val(extra.get("free_cf"), is_money=True)),
            ("Total Debt", fmt_val(total_debt, is_money=True)),
            ("Total Cash", fmt_val(total_cash, is_money=True)),
            ("Net Debt", fmt_val(net_debt, is_money=True)),
            ("Net Debt / EBITDA", fmt_val(net_debt_ebitda)),
        ])

        render_block("BALANCE SHEET", [
            ("Debt / Equity", fmt_val(extra.get("debt_to_equity") or row.get("Debt/Equity"))),
            ("Current Ratio", fmt_val(extra.get("current_ratio") or row.get("Current Ratio"))),
            ("Quick Ratio", fmt_val(extra.get("quick_ratio"))),
            ("Book Value / Share", fmt_val(extra.get("book_value"))),
            ("Cash / Share", fmt_val(extra.get("cash_per_share"))),
        ])

        render_block("DIVIDENDS", [
            ("Forward Div Rate", fmt_val(extra.get("div_rate"))),
            ("Trailing Div Rate", fmt_val(extra.get("trail_div_rate"))),
            ("Div Yield", fmt_val(extra.get("div_yield"), is_pct=True)),
            ("Payout Ratio", fmt_val(extra.get("payout_ratio") or (row.get("Payout Ratio (%)") / 100 if pd.notna(row.get("Payout Ratio (%)")) else None), is_pct=True)),
        ])

    # COLUMNA 3: ANALYST CONSENSUS, OWNERSHIP, SHORT INTEREST
    with col3:
        render_block("ANALYST CONSENSUS", [
            ("Rating", extra.get("recommendation", "-")),
            ("Target Mean", fmt_val(extra.get("target_price"))),
            ("Target Range", f"{fmt_val(extra.get('target_low'))} – {fmt_val(extra.get('target_high'))}"),
            ("# Analysts", fmt_val(extra.get("num_analysts"))),
        ])

        render_block("OWNERSHIP", [
            ("Shares Out.", fmt_val(extra.get("shares_out"))),
            ("Float", fmt_val(extra.get("float_shares"))),
            ("Insiders", fmt_val(extra.get("insiders_pct"), is_pct=True)),
            ("Institutions", fmt_val(extra.get("institutions_pct"), is_pct=True)),
        ])

        render_block("SHORT INTEREST", [
            ("Short Ratio", fmt_val(extra.get("short_ratio"))),
            ("Short % Float", fmt_val(extra.get("short_pct_float"), is_pct=True)),
            ("Shares Short", fmt_val(extra.get("shares_short"))),
            ("Short (prev mo.)", fmt_val(extra.get("shares_short_prior"))),
        ])

    if extra.get("web"):
        st.markdown(f"🔗 [Web corporativa]({extra['web']})")


if __name__ == "__main__":
    main()