import json
import operator as op_mod
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Screener Profesional: Finviz Style", layout="wide")

st.title("Screener Fundamental (S&P 500 + Mercado Español + Small/Micro Cap US)")

DATA_CSV = Path("market_data.csv")
META_JSON = Path("market_data_meta.json")

# ============================================================
# Carga de datos pregenerados por fetch_data.py
# ============================================================

if not DATA_CSV.exists():
    st.error(
        "No existe `market_data.csv` todavía. Esta app ya no descarga los datos "
        "en vivo: ejecuta primero `python fetch_data.py` (o espera a que corra "
        "el job programado) para generar el archivo, y luego recarga esta página."
    )
    st.stop()

df = pd.read_csv(DATA_CSV)

if df.empty:
    st.error("`market_data.csv` existe pero está vacío. Revisa el log del último `fetch_data.py`.")
    st.stop()

if META_JSON.exists():
    meta = json.loads(META_JSON.read_text())
    last_updated = datetime.fromisoformat(meta["last_updated_utc"])
    age = datetime.now(timezone.utc) - last_updated
    horas = age.total_seconds() / 3600
    st.caption(
        f"📅 Datos actualizados hace {horas:.1f}h "
        f"({meta['total_ok']}/{meta['total_attempted']} tickers ok, "
        f"{meta['total_failed']} fallidos en la última descarga)"
    )
    if horas > 30:
        st.warning(
            "Los datos tienen más de 30h de antigüedad. Comprueba que el job "
            "programado (`fetch_data.py`) se esté ejecutando correctamente."
        )
else:
    st.caption("📅 (No se encontró `market_data_meta.json` — fecha de actualización desconocida)")

# --- FILTROS DE INTERFAZ ---
with st.expander("🌍 **Selección de Mercado e Índice**", expanded=True):
    indices_disponibles = sorted(df["Índice"].dropna().unique().tolist())
    indices_opt = st.multiselect(
        "Índices a incluir",
        options=indices_disponibles,
        default=[i for i in ["S&P 500", "IBEX 35"] if i in indices_disponibles] or indices_disponibles
    )
    st.caption(
        "\"Small/Micro Cap (US)\" es una aproximación por capitalización al "
        "estilo Russell 2000, no la composición oficial del índice (esa no "
        "existe en ningún sitio gratuito)."
    )

with st.expander("🔍 **Filtros de Valoración (Valuation)**"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        max_per = st.number_input("PER Máximo", value=100.0)
        max_fwd_per = st.number_input("Forward PER Máximo", value=100.0)
    with col2:
        max_p_fcf = st.number_input("P/FCF Máximo", value=100.0)
        max_peg = st.number_input("PEG Máximo", value=10.0)
    with col3:
        max_ps = st.number_input("P/S Máximo", value=50.0)
        max_pb = st.number_input("P/B Máximo", value=50.0)
    with col4:
        max_ev_ebitda = st.number_input("EV/EBITDA Máximo", value=50.0)
        max_ev_sales = st.number_input("EV/Sales Máximo", value=50.0)

with st.expander("📊 **Rentabilidad y Márgenes (Financial & ROIC)**"):
    col1, col2, col3 = st.columns(3)
    with col1:
        min_roic = st.number_input("ROIC Mínimo (%)", value=-50.0)
        min_roe = st.number_input("ROE Mínimo (%)", value=-50.0)
    with col2:
        min_roa = st.number_input("ROA Mínimo (%)", value=-50.0)
        min_gross_margin = st.number_input("Margen Bruto Mínimo (%)", value=-50.0)
    with col3:
        min_op_margin = st.number_input("Margen Operativo Mínimo (%)", value=-50.0)
        min_net_margin = st.number_input("Margen Neto Mínimo (%)", value=-50.0)

with st.expander("📈 **Crecimiento e Histórico (Growth)**"):
    col1, col2 = st.columns(2)
    with col1:
        min_sales_yoy = st.number_input("Crecimiento Ventas YoY Mínimo (%)", value=-100.0)
        min_sales_3y = st.number_input("Crecimiento Ventas 3Y Mínimo (%)", value=-100.0)
    with col2:
        min_eps_yoy = st.number_input("Crecimiento EPS YoY Mínimo (%)", value=-100.0)
        min_eps_3y = st.number_input("Crecimiento EPS 3Y Mínimo (%)", value=-100.0)

# --- APLICAR FILTROS ---
filtered_df = df[df["Índice"].isin(indices_opt)].copy()


def passes(col, op, threshold):
    return filtered_df[col].isna() | op(filtered_df[col], threshold)


filtered_df = filtered_df[
    passes("PER (Trailing)", op_mod.le, max_per) &
    passes("PER (Forward)", op_mod.le, max_fwd_per) &
    passes("P/FCF", op_mod.le, max_p_fcf) &
    passes("PEG", op_mod.le, max_peg) &
    passes("P/S", op_mod.le, max_ps) &
    passes("P/B", op_mod.le, max_pb) &
    passes("EV/EBITDA", op_mod.le, max_ev_ebitda) &
    passes("EV/Sales", op_mod.le, max_ev_sales) &
    passes("ROIC (%)", op_mod.ge, min_roic) &
    passes("ROE (%)", op_mod.ge, min_roe) &
    passes("ROA (%)", op_mod.ge, min_roa) &
    passes("Margen Bruto (%)", op_mod.ge, min_gross_margin) &
    passes("Margen Operativo (%)", op_mod.ge, min_op_margin) &
    passes("Margen Neto (%)", op_mod.ge, min_net_margin) &
    passes("Crec. Ventas YoY (%)", op_mod.ge, min_sales_yoy) &
    passes("Crec. Ventas 3Y (%)", op_mod.ge, min_sales_3y) &
    passes("Crec. EPS YoY (%)", op_mod.ge, min_eps_yoy) &
    passes("Crec. EPS 3Y (%)", op_mod.ge, min_eps_3y)
]

# --- VISTA FINAL DE TABLA ---
st.write(f"### Resultados ({len(filtered_df)} de {len(df)} empresas coinciden)")

st.dataframe(
    filtered_df.style.format({
        "Precio": "${:.2f}",
        "PER (Trailing)": "{:.2f}",
        "PER (Forward)": "{:.2f}",
        "P/FCF": "{:.2f}",
        "PEG": "{:.2f}",
        "P/S": "{:.2f}",
        "P/B": "{:.2f}",
        "EV/EBITDA": "{:.2f}",
        "EV/Sales": "{:.2f}",
        "ROIC (%)": "{:.2f}%",
        "ROA (%)": "{:.2f}%",
        "ROE (%)": "{:.2f}%",
        "Margen Bruto (%)": "{:.2f}%",
        "Margen Operativo (%)": "{:.2f}%",
        "Margen Neto (%)": "{:.2f}%",
        "Current Ratio": "{:.2f}",
        "Debt/Equity": "{:.2f}",
        "Payout Ratio (%)": "{:.2f}%",
        "Crec. Ventas YoY (%)": "{:.2f}%",
        "Crec. Ventas 3Y (%)": "{:.2f}%",
        "Crec. EPS YoY (%)": "{:.2f}%",
        "Crec. EPS 3Y (%)": "{:.2f}%",
        "Market Cap (B)": "${:.2f}B"
    }, na_rep="—"),
    use_container_width=True,
    hide_index=True
)
