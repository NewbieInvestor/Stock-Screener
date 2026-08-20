"""
fetch_data.py

Job independiente de la app Streamlit. Descarga los fundamentales de
todos los tickers (IBEX 35, Mercado Continuo, S&P 500, Russell 2000)
y los guarda en un CSV local (market_data.csv) junto con un timestamp.

Pensado para ejecutarse solo, de forma programada (cron, GitHub Actions,
Task Scheduler...), NO dentro de la app Streamlit. La app solo lee el
CSV que este script genera, así que abre al instante.

Uso manual:
    python fetch_data.py

Uso con cron (todos los días a las 06:00, hora del servidor):
    0 6 * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/python fetch_data.py >> fetch_log.txt 2>&1

Uso con GitHub Actions: ver el ejemplo de workflow al final de este archivo
(coméntalo/pégalo en .github/workflows/fetch_data.yml).
"""

import io
import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

# yfinance imprime por consola el JSON crudo de error (p.ej. "HTTP Error
# 404: Quote not found for symbol: FI") cada vez que una petición falla,
# aunque el reintento posterior vaya a tener éxito. Esto no es un ticker
# roto: es Yahoo devolviendo 404 de forma transitoria cuando varios hilos
# consultan en paralelo. Silenciamos ese ruido; nuestro propio código de
# reintentos y logging (más abajo) ya se encarga de gestionarlo.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

OUTPUT_CSV = "market_data.csv"
OUTPUT_META = "market_data_meta.json"
FAILED_LOG = "fetch_failed.txt"

# ============================================================
# 1. Listas de tickers por índice
# ============================================================

IBEX_TICKERS = [
    "ANA.MC", "ANE.MC", "AMS.MC", "MTS.MC", "SAB.MC", "SAN.MC", "BKT.MC", "CABK.MC",
    "ACX.MC", "ACS.MC", "AENA.MC", "CLNX.MC", "ENG.MC", "ELE.MC", "FER.MC",
    "GRF.MC", "IAG.MC", "IDR.MC", "ITX.MC", "COL.MC", "LOG.MC", "MAP.MC",
    "MEL.MC", "MRL.MC", "NTGY.MC", "PUIG.MC", "RED.MC", "REP.MC", "ROVI.MC", "SCYR.MC",
    "TEF.MC", "UNI.MC"
]
# Nota: GCO.MC y FLUI.MC se han quitado porque Yahoo Finance devuelve 404
# para ellos. Si sabes el ticker correcto de esas dos empresas en Yahoo,
# añádelo de nuevo aquí con el símbolo bueno.

BME_EXTRA_TICKERS = [
    "A3M.MC", "AI.MC", "APAM.MC", "ALM.MC", "AZK.MC", "BST.MC", "CAF.MC", "CIE.MC",
    "DIA.MC", "DOM.MC", "EBRO.MC", "EDR.MC", "ENC.MC", "FAE.MC", "FDR.MC", "GEST.MC",
    "GIGA.MC", "LDA.MC", "MCM.MC", "MVC.MC", "NBI.MC",
    "NXT.MC", "OHLA.MC", "PHM.MC", "PRM.MC", "PVA.MC", "REN.MC", "SGRE.MC", "SLR.MC",
    "TL5.MC", "TUB.MC", "TRE.MC", "VID.MC", "VIS.MC"
]
# Nota: GCO.MC, FLUI.MC, IZE.MC y NHH.MC se han quitado porque Yahoo Finance
# devuelve 404 para ellos (ticker incorrecto o ya no cotiza con ese sufijo).
# Si sabes el ticker correcto de alguna de esas empresas, añádelo de nuevo
# arriba con el símbolo bueno.

SP500_TICKERS = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB",
    "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP",
    "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "AAPL", "AMAT", "APTV", "ACGL",
    "ADM", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL",
    "BAC", "BAX", "BDX", "BRK-B", "BBY", "TECH", "BIIB", "BLK", "BX", "BA", "BKNG", "BWA", "BSX",
    "BMY", "AVGO", "BR", "BRO", "BF-B", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CZR", "CPT", "CPB", "COF",
    "CAH", "KMX", "CCL", "CARR", "CTLT", "CAT", "CBOE", "CBRE", "CDW", "CE", "COR", "CNC", "CNP", "CF",
    "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX",
    "CME", "CMS", "KO", "CTSH", "CL", "CMCSA", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW",
    "CPAY", "CTVA", "CSGP", "COST", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DVA", "DE", "DAL",
    "XRAY", "DVN", "DXCM", "FANG", "DLR", "DFS", "DG", "DLTR", "D", "DPZ", "DOV", "DOW", "DTE",
    "DUK", "DD", "EMN", "ETN", "EBAY", "ECL", "EIX", "EW", "EA", "ELV", "EMR", "ENPH", "ETR", "EOG",
    "EPAM", "EQT", "EFX", "EQIX", "EQR", "ESS", "EL", "ETSY", "EG", "EVRG", "ES", "EXC", "EXPE", "EXPD",
    "EXR", "XOM", "FFIV", "FAST", "FRT", "FDX", "FITB", "FSLR", "FE", "FIS", "FI", "FMC", "F",
    "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC",
    "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC",
    "HSIC", "HSY", "HPE", "HLT", "HOLX", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM",
    "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "ICE", "IFF", "IP",
    "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM",
    "JNPR", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KLAC", "KHC", "KR", "LHX", "LH",
    "LRCX", "LW", "LVS", "LDOS", "LEN", "LIN", "LYV", "LKQ", "LMT", "L", "LOW", "LULU", "LYB",
    "MTB", "MRO", "MPC", "MKTX", "MAR", "MMC", "MLM", "MAS", "MA", "MTCH", "MKC", "MCD", "MCK",
    "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "MHK", "MOH",
    "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM",
    "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA",
    "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PANW",
    "PH", "PAYX", "PAYC", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL",
    "PPG", "PPL", "PFG", "PG", "PGR", "PSA", "PEG", "PTC", "PHM", "QRVO", "PWR", "QCOM", "DGX",
    "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "ROK", "ROL", "ROP", "ROST",
    "RCL", "SPGI", "CRM", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SNA",
    "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY",
    "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TFX", "TER", "TSLA", "TXN", "TXT",
    "TMO", "TJX", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR",
    "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VTR", "VLTO", "VRSN", "VRSK", "VZ",
    "VRTX", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "WAB", "WMT", "WBD", "WM", "WAT", "WEC",
    "WFC", "WELL", "WST", "WDC", "WRK", "WY", "WHR", "WMB", "WTW", "WYNN", "XEL", "XYL", "YUM",
    "ZBRA", "ZBH", "ZTS"
]

# iShares bloquea las peticiones automatizadas de forma consistente (con o
# sin sesión/cookies/Referer), así que abandonamos esa fuente. En su lugar
# usamos la API pública del screener de Nasdaq, filtrando por capitalización
# pequeña/micro como aproximación a "estilo Russell 2000". No es la
# composición exacta del índice (eso no existe gratis en ningún sitio, ver
# nota más abajo), pero da una cesta amplia y real de small/micro caps de
# NYSE, Nasdaq y AMEX sin que te bloqueen la petición.
NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"


def get_smallcap_tickers(limit=2000):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }
    params = {
        "tableonly": "true",
        "limit": str(limit),
        "offset": "0",
        "exchange": "nasdaq",
    }
    try:
        resp = requests.get(NASDAQ_SCREENER_URL, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        status = payload.get("status") or {}
        data = payload.get("data")

        if not data:
            print(
                f"AVISO: Nasdaq respondió sin datos. status={status}. "
                f"Primeros 300 caracteres del cuerpo: {resp.text[:300]}"
            )
            return []

        rows = (data.get("table") or {}).get("rows") or []
        tickers = [
            r["symbol"].strip()
            for r in rows
            if r.get("symbol") and r["symbol"].strip().replace(".", "").replace("-", "").isalnum()
        ]
        print(f"Small/micro caps (Nasdaq screener): {len(tickers)} tickers")
        return tickers
    except Exception as e:
        print(
            f"AVISO: no se pudo descargar el listado de small caps de Nasdaq "
            f"({type(e).__name__}: {e or '(sin mensaje)'}). El screener seguirá "
            "funcionando solo con S&P 500 + Mercado Español hasta que se resuelva esto."
        )
        return []


# Se mantiene el nombre anterior como alias para no tener que tocar el resto
# del script (get_all_indexed_tickers lo sigue llamando igual).
def get_russell2000_tickers():
    return get_smallcap_tickers()


def get_all_indexed_tickers():
    russell = get_russell2000_tickers()
    indexed = []
    for t in IBEX_TICKERS:
        indexed.append((t, "IBEX 35"))
    for t in BME_EXTRA_TICKERS:
        indexed.append((t, "Mercado Continuo (BME)"))
    for t in SP500_TICKERS:
        indexed.append((t, "S&P 500"))
    for t in russell:
        if t not in SP500_TICKERS:
            indexed.append((t, "Small/Micro Cap (US)"))

    seen, deduped = set(), []
    for ticker, idx in indexed:
        if ticker in seen:
            continue
        seen.add(ticker)
        deduped.append((ticker, idx))
    return deduped


# ============================================================
# 2. Descarga por ticker (igual que en la app, pero pensado para
#    correr sin prisa y con más tolerancia a fallos)
# ============================================================

def fetch_stock_data(item, max_retries=4):
    ticker, index_name = item
    last_error = "sin datos (info vacío o sin precio)"

    for attempt in range(max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            price = info.get("currentPrice", info.get("regularMarketPrice"))
            if not info or price is None:
                if attempt < max_retries:
                    # Backoff más largo: los 404 de Yahoo bajo carga con
                    # varios hilos en paralelo suelen ser transitorios y
                    # necesitan más de 1-3s para despejarse.
                    time.sleep(2.0 * (attempt + 1))
                    continue
                return {"__error__": ticker, "__reason__": last_error}

            mcap = info.get("marketCap")
            fcf = info.get("freeCashflow")
            p_fcf = (mcap / fcf) if (mcap and fcf and fcf > 0) else None

            op_margins = info.get("operatingMargins")
            total_rev = info.get("totalRevenue")
            ebit = (op_margins * total_rev) if (op_margins is not None and total_rev is not None) else None

            total_debt = info.get("totalDebt")
            total_cash = info.get("totalCash")

            # totalStockholderEquity casi nunca viene poblado en info con
            # las versiones recientes de yfinance -> por eso ROIC salía
            # vacío al 100%. Fallback: bookValue x sharesOutstanding, que
            # sí suele estar disponible y evita otra llamada de red
            # (balance_sheet) por ticker, que dispararía el rate-limit.
            total_equity = info.get("totalStockholderEquity")
            if total_equity is None:
                book_value = info.get("bookValue")
                shares_out = info.get("sharesOutstanding")
                if book_value is not None and shares_out is not None:
                    total_equity = book_value * shares_out

            invested_capital = (
                total_debt + total_equity - total_cash
                if None not in (total_debt, total_equity, total_cash)
                else None
            )
            # Tasa impositiva aproximada estándar (el tipo efectivo real
            # requeriría el income statement completo -> más llamadas).
            tax_rate = 0.21
            nopat = (ebit * (1 - tax_rate)) if ebit is not None else None
            roic = (
                (nopat / invested_capital * 100)
                if (nopat is not None and invested_capital and invested_capital > 0)
                else None
            )

            def pct(key):
                val = info.get(key)
                return val * 100 if val is not None else None

            return {
                "Ticker": ticker,
                "Nombre": info.get("shortName", ticker),
                "Índice": index_name,
                "Precio": price,
                "PER (Trailing)": info.get("trailingPE"),
                "PER (Forward)": info.get("forwardPE"),
                "P/FCF": p_fcf,
                "PEG": info.get("pegRatio"),
                "P/S": info.get("priceToSalesTrailing12Months"),
                "P/B": info.get("priceToBook"),
                "EV/EBITDA": info.get("enterpriseToEbitda"),
                "EV/Sales": info.get("enterpriseToRevenue"),
                "ROIC (%)": roic,
                "ROA (%)": pct("returnOnAssets"),
                "ROE (%)": pct("returnOnEquity"),
                "Margen Bruto (%)": pct("grossMargins"),
                "Margen Operativo (%)": pct("operatingMargins"),
                "Margen Neto (%)": pct("profitMargins"),
                "Current Ratio": info.get("currentRatio"),
                "Debt/Equity": info.get("debtToEquity"),
                "Payout Ratio (%)": pct("payoutRatio"),
                "Crec. Ventas YoY (%)": pct("revenueGrowth"),
                "Crec. Ventas 3Y (%)": pct("revenueGrowth"),
                "Crec. EPS YoY (%)": pct("earningsGrowth"),
                "Crec. EPS 3Y (%)": pct("earningsQuarterlyGrowth"),
                "Market Cap (B)": (mcap / 1e9) if mcap else None,
            }
        except Exception as e:
            last_error = f"{type(e).__name__}: {e or '(sin mensaje)'}"
            if attempt < max_retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            return {"__error__": ticker, "__reason__": last_error}

    return {"__error__": ticker, "__reason__": last_error}


def main():
    all_indexed = get_all_indexed_tickers()
    print(f"Descargando {len(all_indexed)} tickers...")

    # Workers moderados + procesado por lotes: es un job en background,
    # no hay prisa por el usuario, así que priorizamos no chocar con el
    # rate-limit de Yahoo sobre la velocidad bruta.
    results = []
    batch_size = 100
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i in range(0, len(all_indexed), batch_size):
            batch = all_indexed[i:i + batch_size]
            batch_results = list(executor.map(fetch_stock_data, batch))
            results.extend(batch_results)
            done = min(i + batch_size, len(all_indexed))
            print(f"  progreso: {done}/{len(all_indexed)}")
            if done < len(all_indexed):
                time.sleep(5)  # pausa entre lotes para no saturar Yahoo

    ok = [r for r in results if r is not None and "__error__" not in r]
    failed = [r for r in results if r is not None and "__error__" in r]

    df = pd.DataFrame(ok)
    df.to_csv(OUTPUT_CSV, index=False)

    meta = {
        "last_updated_utc": datetime.now(timezone.utc).isoformat(),
        "total_attempted": len(all_indexed),
        "total_ok": len(ok),
        "total_failed": len(failed),
    }
    with open(OUTPUT_META, "w") as f:
        json.dump(meta, f, indent=2)

    # Guarda ticker + motivo, para poder distinguir de un vistazo un
    # ticker realmente deslistado/mal escrito de un 404 transitorio de
    # Yahoo que no se resolvió ni tras los reintentos.
    with open(FAILED_LOG, "w") as f:
        for r in failed:
            f.write(f"{r['__error__']}\t{r.get('__reason__', '')}\n")

    print(f"Hecho: {len(ok)} ok, {len(failed)} fallidos. Guardado en {OUTPUT_CSV}")
    if failed:
        print(f"  (motivos de los fallos en {FAILED_LOG})")


if __name__ == "__main__":
    main()

# ============================================================
# Ejemplo de workflow de GitHub Actions (guárdalo como
# .github/workflows/fetch_data.yml si quieres que corra en la nube
# gratis en vez de en tu propia máquina):
#
# name: Fetch market data
# on:
#   schedule:
#     - cron: "0 6 * * *"   # todos los días a las 06:00 UTC
#   workflow_dispatch: {}   # también puedes lanzarlo a mano
# jobs:
#   fetch:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/checkout@v4
#       - uses: actions/setup-python@v5
#         with:
#           python-version: "3.11"
#       - run: pip install yfinance pandas requests
#       - run: python fetch_data.py
#       - uses: actions/upload-artifact@v4  # o haz commit del CSV al repo
#         with:
#           name: market-data
#           path: |
#             market_data.csv
#             market_data_meta.json
# ============================================================
