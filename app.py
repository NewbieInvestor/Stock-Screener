"""
App Streamlit para explorar interactivamente market_data.csv.
Incluye Módulo de Análisis Profundo con Valoración Triple (DCF, PER Histórico con EPS Actual
y PER Histórico con EPS a 5 Años) junto con ROIC Exacto.
"""

import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Screener", layout="wide")

DATA_CSV = "market_data.csv"

# --- CONSTANTES PARA EL DCF Y VALORACIONES ---
WACC = 0.10              # Tasa de descuento (10%)
TERMINAL_GROWTH = 0.025  # Crecimiento a perpetuidad (2.5%)
PROJECTION_YEARS = 5     # Años a proyectar

@st.cache_data(ttl=3600)
def load_data():
    return pd.read_csv(DATA_CSV)

@st.cache_data(ttl=1800)
def load_price_history(ticker, period="1y"):
    return yf.Ticker(ticker).history(period=period)

@st.cache_data(ttl=3600)
def load_ticker_extra(ticker):
    """Datos adicionales de Yahoo Finance para la ficha completa."""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}

    return {
        "sector": info.get("sector", "-"),
        "industria": info.get("industry", "-"),
        "empleados": info.get("fullTimeEmployees", "-"),
        "resumen": info.get("longBusinessSummary", ""),
        "web": info.get("website", ""),
        "country": info.get("country", "-"),
        "target_price": info.get("targetMeanPrice"),
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "recommendation": info.get("recommendationKey", "-"),
        "num_analysts": info.get("numberOfAnalystOpinions"),
        "beta": info.get("beta"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "rev_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "gross_margins": info.get("grossMargins"),
        "oper_margins": info.get("operatingMargins"),
        "profit_margins": info.get("profitMargins"),
        "ebitda_margins": info.get("ebitdaMargins"),
        "roa": info.get("returnOnAssets"),
        "roe": info.get("returnOnEquity"),
        "operating_cf": info.get("operatingCashflow"),
        "free_cf": info.get("freeCashflow"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "ebitda": info.get("ebitda"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "book_value": info.get("bookValue"),
        "cash_per_share": info.get("totalCashPerShare"),
        "shares_out": info.get("sharesOutstanding"),
        "float_shares": info.get("floatShares"),
        "insiders_pct": info.get("heldPercentInsiders"),
        "institutions_pct": info.get("heldPercentInstitutions"),
        "short_ratio": info.get("shortRatio"),
        "short_pct_float": info.get("shortPercentOfFloat"),
        "shares_short": info.get("sharesShort"),
        "shares_short_prior": info.get("sharesShortPriorMonth"),
        "div_rate": info.get("dividendRate"),
        "trail_div_rate": info.get("trailingAnnualDividendRate"),
        "div_yield": info.get("dividendYield"),
        "payout_ratio": info.get("payoutRatio"),
    }

def get_df_row(df, keywords):
    """Busca filas en DataFrames de Yahoo Finance de forma flexible e insensible a mayúsculas."""
    if df is None or df.empty:
        return None
    for idx in df.index:
        idx_str = str(idx).lower()
        if any(kw.lower() in idx_str for kw in keywords):
            s = df.loc[idx].dropna()
            if not s.empty:
                return s
    return None

def get_historical_pe(ticker_obj, years=5):
    """Calcula la media del PER histórico propio de la empresa cruzando EPS anual y precios mensuales."""
    try:
        inc_stmt = ticker_obj.income_stmt
        if inc_stmt is None or inc_stmt.empty:
            return None

        eps_row = get_df_row(inc_stmt, ["diluted eps", "basic eps", "beneficio por accion"])
        if eps_row is None:
            return None

        hist = ticker_obj.history(period=f"{years}y", interval="1mo")
        if hist.empty:
            return None

        annual_pes = []
        for date, eps in eps_row.items():
            if pd.notna(eps) and eps > 0:
                year = date.year
                year_prices = hist.loc[hist.index.year == year, "Close"]
                if not year_prices.empty:
                    avg_price = year_prices.mean()
                    pe_year = avg_price / eps
                    if 2 < pe_year < 150:  # Filtrar anomalías numéricas puntuales
                        annual_pes.append(pe_year)

        if len(annual_pes) >= 2:  # Evita una "media" basada en un único año (poco histórico)
            return sum(annual_pes) / len(annual_pes)
    except Exception:
        pass
    return None

def get_cagr_growth(inc_stmt):
    """Calcula el CAGR de Ventas y EPS con los años disponibles en el income_stmt YA descargado
    (lo reutiliza de la llamada que ya hace get_deep_metrics para el ROIC — no añade llamadas de red).
    Devuelve None si el año base es <= 0 (el CAGR no tiene sentido matemático ahí)."""
    rev_cagr = None
    eps_cagr = None
    try:
        if inc_stmt is None or inc_stmt.empty:
            return None, None

        rev_row = get_df_row(inc_stmt, ["total revenue", "operating revenue", "ingresos totales"])
        eps_row = get_df_row(inc_stmt, ["diluted eps", "basic eps", "beneficio por accion"])

        for row, is_eps in [(rev_row, False), (eps_row, True)]:
            if row is None or len(row) < 2:
                continue
            row_sorted = row.sort_index()  # más antiguo primero
            oldest, newest = row_sorted.iloc[0], row_sorted.iloc[-1]
            n_years = len(row_sorted) - 1
            if pd.notna(oldest) and pd.notna(newest) and oldest > 0 and n_years > 0:
                cagr = ((newest / oldest) ** (1 / n_years) - 1) * 100
                if is_eps:
                    eps_cagr = cagr
                else:
                    rev_cagr = cagr
    except Exception:
        pass
    return rev_cagr, eps_cagr

# --- CAVEATS DE FIABILIDAD POR SECTOR/INDUSTRIA ---
# Palabras clave (en minúsculas) para detectar sectores donde estos modelos
# estándar (DCF por FCF, ROIC, PER histórico) son menos representativos.
FINANCIAL_KEYWORDS = ["financial", "bank", "insurance", "capital markets", "mortgage", "asset management"]
REAL_ESTATE_KEYWORDS = ["real estate", "reit"]
CYCLICAL_KEYWORDS = ["oil & gas", "steel", "airlines", "auto manufacturers", "auto parts",
                      "semiconductor", "copper", "gold", "coal", "aluminum", "metals & mining",
                      "shipping", "chemicals", "uranium", "drilling", "iron", "lumber"]

def get_valuation_caveats(sector, industry):
    """Indica qué métricas del Análisis Profundo son menos fiables para este sector/industria."""
    sector_l = str(sector).lower()
    industry_l = str(industry).lower()

    is_fin = any(kw in sector_l or kw in industry_l for kw in FINANCIAL_KEYWORDS)
    is_re = any(kw in sector_l or kw in industry_l for kw in REAL_ESTATE_KEYWORDS)
    is_util = "utilities" in sector_l
    is_cyclical = any(kw in industry_l for kw in CYCLICAL_KEYWORDS)

    flags = {"dcf": False, "roic": False, "per_hist": False}
    reasons = []

    if is_fin or is_re:
        flags["dcf"] = True
        flags["roic"] = True
        reasons.append("Financiero/REIT: el FCF y el ROIC no reflejan bien este modelo de negocio "
                        "(la deuda es materia prima, no capital invertido) — mejor mirar ROE/ROA.")
    if is_util:
        flags["roic"] = True
        reasons.append("Utility regulada: el ROIC vs WACC pierde sentido porque el retorno lo fija el regulador.")
    if is_cyclical:
        flags["per_hist"] = True
        reasons.append("Sector cíclico: el PER histórico medio puede reflejar un pico o un valle de beneficio, "
                        "no una valoración real.")

    return flags, reasons

@st.cache_data(show_spinner=False, ttl=3600)
def get_deep_metrics(ticker, current_price):
    """Calcula ROIC exacto, PER Histórico propio, FCF Medio, Valor Intrínseco (DCF, EPS Actual y EPS 5Y)
    y CAGR de Ventas/EPS de los últimos años disponibles."""
    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    sector = str(info.get("sector", ""))
    industry = str(info.get("industry", ""))
    
    is_financial_or_reit = (
        "financial" in sector.lower() 
        or "real estate" in sector.lower() 
        or "reit" in industry.lower() 
        or "bank" in industry.lower()
        or "mortgage" in industry.lower()
    )
    
    # 1. ROIC Exacto
    roic = None
    inc_stmt = None
    try:
        inc_stmt = t.income_stmt
        bal_sheet = t.balance_sheet
        
        ebit_row = get_df_row(inc_stmt, ["ebit", "operating income", "resultado de explotacion"])
        pretax_row = get_df_row(inc_stmt, ["pretax income", "income before tax"])
        tax_row = get_df_row(inc_stmt, ["tax provision", "income tax expense"])

        ebit = ebit_row.iloc[0] if ebit_row is not None else None
        pretax = pretax_row.iloc[0] if pretax_row is not None else None
        tax_prov = tax_row.iloc[0] if tax_row is not None else None

        tax_rate = (tax_prov / pretax) if (pretax and tax_prov and pretax > 0) else 0.21
        if tax_rate < 0 or tax_rate > 0.5:
            tax_rate = 0.21

        nopat = ebit * (1 - tax_rate) if ebit is not None else None

        debt_row = get_df_row(bal_sheet, ["total debt", "long term debt", "deuda total"])
        equity_row = get_df_row(bal_sheet, ["stockholders equity", "total equity", "patrimonio neto"])
        cash_row = get_df_row(bal_sheet, ["cash and cash equivalents", "efectivo"])

        total_debt = debt_row.iloc[0] if debt_row is not None else 0
        total_equity = equity_row.iloc[0] if equity_row is not None else None
        cash = cash_row.iloc[0] if cash_row is not None else 0

        if nopat is not None and total_equity is not None:
            invested_capital = total_debt + total_equity - cash
            if invested_capital > 0:
                roic = (nopat / invested_capital) * 100
    except Exception:
        pass

    # 1b. Crecimiento CAGR 3-4 años (Ventas y EPS) — reutiliza el income_stmt ya descargado arriba,
    # no hace ninguna llamada de red adicional.
    rev_cagr, eps_cagr = get_cagr_growth(inc_stmt)
        
    # 2. DCF (FCF Medio 3 Años)
    intrinsic_dcf = None
    status_note = None
    mean_fcf = None

    try:
        cash_flow = t.cash_flow
        fcf_series = get_df_row(cash_flow, ["free cash flow", "flujo de caja libre"])

        if fcf_series is None:
            ocf_row = get_df_row(cash_flow, ["operating cash flow"])
            capex_row = get_df_row(cash_flow, ["capital expenditure", "capex"])
            if ocf_row is not None:
                fcf_series = ocf_row + capex_row if capex_row is not None else ocf_row

        if fcf_series is not None and len(fcf_series) > 0:
            mean_fcf = float(fcf_series.head(3).mean())

            if mean_fcf <= 0:
                status_note = "FCF Negativo"
            else:
                projected_fcf = [mean_fcf * ((1 + 0.05) ** i) for i in range(1, PROJECTION_YEARS + 1)]
                discounted_fcf = sum([f / ((1 + WACC) ** i) for i, f in enumerate(projected_fcf, 1)])

                terminal_val = (projected_fcf[-1] * (1 + TERMINAL_GROWTH)) / (WACC - TERMINAL_GROWTH)
                discounted_tv = terminal_val / ((1 + WACC) ** PROJECTION_YEARS)

                enterprise_value = discounted_fcf + discounted_tv

                shares_out = info.get("sharesOutstanding")
                if not shares_out:
                    shares_row = get_df_row(t.balance_sheet, ["share issued", "ordinary shares number"])
                    if shares_row is not None:
                        shares_out = shares_row.iloc[0]

                equity_value = enterprise_value if is_financial_or_reit else (enterprise_value - total_debt + cash)

                if shares_out and shares_out > 0:
                    iv = equity_value / shares_out
                    if iv > 0:
                        intrinsic_dcf = iv
                    else:
                        status_note = "IV DCF Negativo"
        else:
            status_note = "Sin datos FCF"
    except Exception:
        status_note = "Error DCF"

    # 3. PER Histórico Propio y Valoración por EPS
    pe_hist = get_historical_pe(t)
    iv_pe_actual = None
    iv_pe_growth = None
    
    eps_trailing = info.get("trailingEps")
    if not eps_trailing and t.income_stmt is not None:
        eps_row = get_df_row(t.income_stmt, ["diluted eps", "basic eps"])
        if eps_row is not None:
            eps_trailing = eps_row.iloc[0]

    if eps_trailing and eps_trailing > 0 and pe_hist:
        iv_pe_actual = eps_trailing * pe_hist
        
        future_eps = eps_trailing * ((1 + 0.05) ** PROJECTION_YEARS)
        future_price = future_eps * pe_hist
        iv_pe_growth = future_price / ((1 + WACC) ** PROJECTION_YEARS)

    return roic, intrinsic_dcf, pe_hist, iv_pe_actual, iv_pe_growth, status_note, mean_fcf, sector, industry, rev_cagr, eps_cagr

def fmt_val(val, is_pct=False, is_money=False, multiplier=1.0):
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

# PRESETS DE FILTROS
VALUATION_PRESETS = [("Cualquiera", None, None), ("Positivo (>0)", 0, None), ("Bajo (<10)", None, 10), ("Bajo (<15)", None, 15), ("Bajo (<20)", None, 20), ("Bajo (<30)", None, 30), ("Bajo (<50)", None, 50), ("Alto (>50)", 50, None), ("Negativo (<0)", None, 0), ("Personalizado", "custom", "custom")]
GROWTH_PRESETS = [("Cualquiera", None, None), ("Positivo (>0%)", 0, None), ("Over 5%", 5, None), ("Over 10%", 10, None), ("Over 15%", 15, None), ("Over 20%", 20, None), ("Over 30%", 30, None), ("Over 50%", 50, None), ("Negativo (<0%)", None, 0), ("Personalizado", "custom", "custom")]
RATIO_PRESETS = [("Cualquiera", None, None), ("Bajo (<1)", None, 1), ("Bajo (<2)", None, 2), ("Moderado (<0.5)", None, 0.5), ("Alto (>2)", 2, None), ("Personalizado", "custom", "custom")]
PB_PRESETS = [("Cualquiera", None, None), ("Positivo (>0)", 0, None), ("Bajo (<1)", None, 1), ("Bajo (<2)", None, 2), ("Bajo (<3)", None, 3), ("Bajo (<5)", None, 5), ("Bajo (<10)", None, 10), ("Alto (>10)", 10, None), ("Negativo (<0)", None, 0), ("Personalizado", "custom", "custom")]
MCAP_PRESETS = [("Cualquiera", None, None), ("Mega (200bln+)", 200, None), ("Large (10bln-200bln)", 10, 200), ("Mid (2bln-10bln)", 2, 10), ("Small (300mln-2bln)", 0.3, 2), ("Micro (50mln-300mln)", 0.05, 0.3), ("Nano (under 50mln)", None, 0.05), ("+Large (over 10bln)", 10, None), ("+Mid (over 2bln)", 2, None), ("+Small (over 300mln)", 0.3, None), ("+Micro (over 50mln)", 0.05, None), ("-Large (under 200bln)", None, 200), ("-Mid (under 10bln)", None, 10), ("-Small (under 2bln)", None, 2), ("-Micro (under 300mln)", None, 0.3), ("Personalizado", "custom", "custom")]

PEG_PRESETS = [("Cualquiera", None, None), ("Muy Bajo (<0.5)", None, 0.5), ("Bajo (<1.0)", None, 1.0), ("Bajo (<1.5)", None, 1.5), ("Moderado (<2.0)", None, 2.0), ("Alto (>2.0)", 2.0, None), ("Negativo (<0)", None, 0), ("Personalizado", "custom", "custom")]
DEBT_EQUITY_PRESETS = [("Cualquiera", None, None), ("Sin Deuda / Muy Bajo (<0.2)", None, 0.2), ("Bajo (<0.5)", None, 0.5), ("Saludable (<1.0)", None, 1.0), ("Moderado (<1.5)", None, 1.5), ("Moderado (<2.0)", None, 2.0), ("Alto (>2.0)", 2.0, None), ("Personalizado", "custom", "custom")]
CURRENT_RATIO_PRESETS = [("Cualquiera", None, None), ("Fuerte (>2.0)", 2.0, None), ("Saludable (>1.5)", 1.5, None), ("Aceptable (>1.0)", 1.0, None), ("Bajo (<1.0)", None, 1.0), ("Peligro (<0.5)", None, 0.5), ("Personalizado", "custom", "custom")]

def finviz_filter(col, label, kind="growth", key_prefix=""):
    presets = {
        "valuation": VALUATION_PRESETS,
        "growth": GROWTH_PRESETS,
        "ratio": RATIO_PRESETS,
        "mcap": MCAP_PRESETS,
        "pb": PB_PRESETS,
        "peg": PEG_PRESETS,
        "debt_equity": DEBT_EQUITY_PRESETS,
        "current_ratio": CURRENT_RATIO_PRESETS,
    }[kind]
    
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
    st.markdown(f"##### {title}")
    for label, val in items:
        st.markdown(f"**{label}:** {val}")
    st.markdown("---")

def main():
    st.title("📊 Stock Screener")

    try:
        df = load_data()
    except FileNotFoundError:
        st.error(f"No se encuentra {DATA_CSV} en esta carpeta. Ejecuta fetch_data.py primero.")
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
        indices_sel = st.multiselect("Índices", indices_disponibles, default=indices_disponibles)
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
            sels["PEG"] = finviz_filter("PEG", "PEG", "peg", "val")
        with c4:
            sels["P/FCF"] = finviz_filter("P/FCF", "P/FCF", "valuation", "val")
            sels["P/S"] = finviz_filter("P/S", "P/S", "valuation", "val")

    with tab_gro:
        c1, c2 = st.columns(2)
        with c1:
            sels["Crec. Ventas YoY (%)"] = finviz_filter("Crec. Ventas YoY (%)", "Crec. Ventas YoY", "growth", "gro")
        with c2:
            sels["Crec. EPS YoY (%)"] = finviz_filter("Crec. EPS YoY (%)", "Crec. EPS YoY", "growth", "gro")
        st.caption("El crecimiento a 3 años (CAGR de Ventas y EPS) se calcula en el Análisis Profundo, "
                   "no aquí — requiere histórico de varios años que no merece la pena descargar para las 2.500+ empresas del universo.")

    with tab_rent:
        c1, c2, c3 = st.columns(3)
        with c1:
            sels["ROIC Aprox. (%)"] = finviz_filter("ROIC Aprox. (%)", "ROIC (Aprox.)", "growth", "cal")
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
            sels["Debt/Equity"] = finviz_filter("Debt/Equity", "Debt/Equity", "debt_equity", "sal")
        with c2:
            sels["Current Ratio"] = finviz_filter("Current Ratio", "Current Ratio", "current_ratio", "sal")
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

    # --- SECCIÓN: ANÁLISIS PROFUNDO ---
    st.markdown("---")
    st.subheader("🧠 Análisis Profundo (DCF, PER Histórico y ROIC Exacto)")
    st.write("Calcula el Valor Intrínseco por múltiples métodos (DCF, PER con EPS actual y PER con EPS proyectado a 5 años) junto con el PER histórico propio y ROIC real.")
    
    with st.expander("ℹ️ ¿Cómo se calculan las métricas del Análisis Profundo?"):
        st.markdown("""
        **1. Valor Intrínseco DCF (Flujos de Caja):**
        * Basado en la media del FCF de los últimos 3 años proyectado al **5% anual** durante 5 años.
        * Descontado al **10% anual (WACC)** con valor terminal al **2.5% de crecimiento perpetuo**.

        **2. PER Histórico Propio (5 Años):**
        * Calcula el PER medio real de la propia empresa cruzando sus precios de cierre mensuales con sus beneficios anuales (EPS) de los últimos 5 años.

        **3. Valoración por PER y Beneficios (EPS):**
        * **IV PER (EPS Actual):** $\\text{EPS Actual} \\times \\text{PER Histórico}$.
        * **IV PER (EPS 5Y Growth):** $\\text{EPS Proyectado al 5\\% a 5 años} \\times \\text{PER Histórico}$ descontado al $10\\%$ anual.

        **4. Rentabilidad sobre Capital Invertido (ROIC Exacto):**
        $$ROIC = \\frac{\\text{NOPAT}}{\\text{Capital Invertido}} = \\frac{\\text{EBIT} \\times (1 - \\text{Tasa Impositiva})}{\\text{Deuda Total} + \\text{Patrimonio Neto} - \\text{Caja}}$$

        **5. Crecimiento CAGR (Ventas y EPS):**
        * Tasa de crecimiento anual compuesto entre el año más antiguo y el más reciente disponibles en el
          income statement (normalmente 3-4 años). Se omite si el año base es negativo o cero (el CAGR no
          tiene sentido matemático ahí) — verás "N/A" en esos casos, no un cero falso.

        **⚠️ Limitaciones por sector:** estos modelos asumen supuestos genéricos (WACC 10%, crecimiento 5%,
        terminal 2.5%) iguales para cualquier empresa, y no funcionan igual de bien en todos los sectores
        (financieras, REITs, utilities reguladas, cíclicas...). Las celdas marcadas con **\\*** en la tabla
        indican una métrica con fiabilidad reducida para esa empresa concreta — revisa la leyenda bajo la tabla.
        """)

    if st.button("🚀 Ejecutar Análisis Profundo", type="primary"):
        if len(resultado) == 0:
            st.warning("⚠️ No hay ninguna empresa en los resultados para analizar.")
        elif len(resultado) > 25:
            st.warning(f"⚠️ Tienes {len(resultado)} empresas en pantalla. Filtra para dejar un máximo de 25 antes de ejecutar la petición.")
        else:
            deep_results = []
            all_reasons = []
            tickers_list = resultado["Ticker"].tolist()
            
            progress_bar = st.progress(0, text="Iniciando conexión con balances...")
            
            for i, ticker in enumerate(tickers_list):
                progress_bar.progress((i + 1) / len(tickers_list), text=f"Analizando {ticker} ({i+1}/{len(tickers_list)})...")
                
                nombre = resultado.loc[resultado["Ticker"] == ticker, "Nombre"].values[0]
                precio_actual = resultado.loc[resultado["Ticker"] == ticker, "Precio"].values[0]
                
                roic, iv_dcf, pe_hist, iv_pe_act, iv_pe_gro, note, mean_fcf, sector, industry, rev_cagr, eps_cagr = get_deep_metrics(ticker, precio_actual)

                flags, reasons = get_valuation_caveats(sector, industry)
                all_reasons.extend(reasons)

                def _mark(value, flagged):
                    """Añade * al valor si la métrica está marcada como poco fiable para este sector."""
                    return f"{value}*" if (flagged and value != "N/A") else value

                iv_dcf_val = round(iv_dcf, 2) if iv_dcf else (note if note else "N/A")
                pe_hist_val = round(pe_hist, 1) if pe_hist else "N/A"
                iv_pe_act_val = round(iv_pe_act, 2) if iv_pe_act else "N/A"
                iv_pe_gro_val = round(iv_pe_gro, 2) if iv_pe_gro else "N/A"
                roic_val = round(roic, 2) if roic else "N/A"
                rev_cagr_val = round(rev_cagr, 2) if rev_cagr is not None else "N/A"
                eps_cagr_val = round(eps_cagr, 2) if eps_cagr is not None else "N/A"

                deep_results.append({
                    "Ticker": ticker,
                    "Nombre": nombre,
                    "Precio Actual": round(precio_actual, 2) if pd.notna(precio_actual) else "N/A",
                    "FCF": fmt_val(mean_fcf, is_money=True) if mean_fcf is not None else "N/A",
                    "IV DCF (FCF)": _mark(iv_dcf_val, flags["dcf"]),
                    "PER Hist. Medio": _mark(pe_hist_val, flags["per_hist"]),
                    "IV PER (EPS Actual)": _mark(iv_pe_act_val, flags["per_hist"]),
                    "IV PER (EPS 5Y Growth)": _mark(iv_pe_gro_val, flags["per_hist"]),
                    "ROIC Exacto (%)": _mark(roic_val, flags["roic"]),
                    "Crec. Ventas CAGR (%)": rev_cagr_val,
                    "Crec. EPS CAGR (%)": eps_cagr_val,
                })
                           
            progress_bar.empty()
            st.success("¡Análisis profundo completado! 🎉")
            
            df_deep = pd.DataFrame(deep_results)
            st.dataframe(df_deep, hide_index=True, use_container_width=True)

            if all_reasons:
                unique_reasons = sorted(set(all_reasons))
                leyenda = "  \n".join(f"* {r}" for r in unique_reasons)
                st.caption(leyenda)

    # --- SECCIÓN: FICHA DE EMPRESA ---
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

    ver_ficha = st.button("🔎 Ver ficha", type="secondary")

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

    st.markdown("### 📋 Key Statistics")

    total_cash = extra.get("total_cash")
    total_debt = extra.get("total_debt")
    ebitda = extra.get("ebitda")

    net_debt = (total_debt - total_cash) if (total_debt is not None and total_cash is not None) else None
    net_debt_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda != 0) else None

    col1, col2, col3 = st.columns(3)

    with col1:
        mcap_val = row.get("Market Cap (B)")
        if (pd.isna(mcap_val) or mcap_val is None) and extra.get("shares_out") and row.get("Precio"):
            mcap_val = (row.get("Precio") * extra.get("shares_out")) / 1e9

        render_block("COMPANY", [
            ("Market Cap", fmt_val(mcap_val, is_money=True, multiplier=1e9)),
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
            ("ROIC (Aprox.)", fmt_val(row.get("ROIC Aprox. (%)") / 100 if pd.notna(row.get("ROIC Aprox. (%)")) else None, is_pct=True)),
        ])

    with col2:
        render_block("GROWTH", [
            ("Revenue Growth", fmt_val(extra.get("rev_growth") or (row.get("Crec. Ventas YoY (%)") / 100 if pd.notna(row.get("Crec. Ventas YoY (%)")) else None), is_pct=True)),
            ("Earnings Growth", fmt_val(extra.get("earnings_growth") or (row.get("Crec. EPS YoY (%)") / 100 if pd.notna(row.get("Crec. EPS YoY (%)")) else None), is_pct=True)),
        ])
        st.caption("Crecimiento a 3 años (CAGR): disponible en la sección Análisis Profundo, más arriba.")

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