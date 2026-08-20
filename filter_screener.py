"""
Filtra market_data.csv buscando empresas tipo "moat + calidad + PER bajo".
Ajusta los umbrales en la sección CONFIG a tu gusto.
"""
import pandas as pd

# ---------------- CONFIG ----------------
INPUT_CSV = "market_data.csv"
OUTPUT_CSV = "screener_resultados.csv"

PER_MAX = 20            # PER trailing máximo
MARGEN_NETO_MIN = 10    # % margen neto mínimo
MARGEN_BRUTO_MIN = 30   # % margen bruto mínimo (proxy de moat/poder de precio)
ROIC_MIN = 12           # % ROIC mínimo (rentabilidad sobre capital invertido, moat real)
ROE_MIN = 15            # % ROE mínimo
ROA_MIN = 5             # % ROA mínimo
DEBT_EQUITY_MAX = 150   # deuda/equity máxima
CURRENT_RATIO_MIN = 1.0 # liquidez mínima
MARKET_CAP_MIN = 0.05   # en miles de millones (50M) — evita micro-caps ilíquidas extremas

# ROIC no está disponible para todas las filas (requiere bookValue y
# sharesOutstanding en yfinance, que a veces faltan). Si REQUIRE_ROIC es
# True, las filas sin ROIC se descartan directamente. Si es False, el
# filtro de ROIC simplemente se ignora en esas filas (más permisivo).
REQUIRE_ROIC = False
# -----------------------------------------

df = pd.read_csv(INPUT_CSV)

if REQUIRE_ROIC:
    roic_ok = df["ROIC (%)"] >= ROIC_MIN
else:
    roic_ok = df["ROIC (%)"].isna() | (df["ROIC (%)"] >= ROIC_MIN)

filtros = (
    (df["PER (Trailing)"] > 0) & (df["PER (Trailing)"] <= PER_MAX) &
    (df["Margen Neto (%)"] >= MARGEN_NETO_MIN) &
    (df["Margen Bruto (%)"] >= MARGEN_BRUTO_MIN) &
    roic_ok &
    (df["ROE (%)"] >= ROE_MIN) &
    (df["ROA (%)"] >= ROA_MIN) &
    (df["Debt/Equity"].fillna(0) <= DEBT_EQUITY_MAX) &
    (df["Current Ratio"] >= CURRENT_RATIO_MIN) &
    (df["Market Cap (B)"] >= MARKET_CAP_MIN)
)

resultado = df[filtros].copy()
# Ordena priorizando ROIC (cuando existe) como señal principal de moat
resultado = resultado.sort_values(["ROIC (%)", "PER (Trailing)"], ascending=[False, True])

cols_mostrar = [
    "Ticker", "Nombre", "Índice", "Precio", "PER (Trailing)", "PER (Forward)",
    "Margen Bruto (%)", "Margen Operativo (%)", "Margen Neto (%)",
    "ROIC (%)", "ROE (%)", "ROA (%)", "Debt/Equity", "Current Ratio", "Market Cap (B)"
]

resultado[cols_mostrar].to_csv(OUTPUT_CSV, index=False)

print(f"Total analizado: {len(df)}")
print(f"Pasan el filtro: {len(resultado)}")
print(f"Guardado en {OUTPUT_CSV}\n")
print(resultado[cols_mostrar].head(30).to_string(index=False))
