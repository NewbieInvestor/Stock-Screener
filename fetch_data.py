"""
fetch_data.py
Universo de tickers para Dow Jones Composite, NASDAQ 100, S&P 500, España
(IBEX 35 + Mercado Continuo) y Russell 2000.

CAMBIO DE ENFOQUE respecto a la versión anterior:
En vez de listas 100% hardcodeadas (que se quedan obsoletas en cuanto un
índice cambia de composición), el S&P 500, el NASDAQ 100 y el Russell 2000
se descargan en cada ejecución desde fuentes públicas que se actualizan
solas. Si la descarga falla (sin red, fuente caída, etc.) se usa una lista
estática de emergencia — que es exactamente el tipo de lista que tenías
antes, con los mismos riesgos de quedarse desactualizada.

Todas las listas (dinámicas o de fallback) pasan por:
  1. _dedupe()            -> elimina duplicados manteniendo el orden
  2. _validate_format()   -> avisa de tickers con una pinta rara antes de
                              gastar llamadas a yfinance en ellos
"""

import random
import re
import time
import io
import csv
import requests
import pandas as pd
import yfinance as yf


# --- UTILIDADES COMUNES -----------------------------------------------

def _dedupe(seq):
    """Elimina duplicados preservando el orden de aparición."""
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# Formato esperado: 1-6 letras, opcionalmente con un sufijo tipo -B, -A
# (acciones de clase), o el sufijo .MC para el mercado español.
_TICKER_RE = re.compile(r"^[A-Z0-9]{1,6}(-[A-Z]{1,2})?$|^[A-Z0-9]{1,6}\.MC$")


def _validate_format(tickers, label):
    """Avisa (no elimina) de tickers con formato sospechoso."""
    raros = [t for t in tickers if not _TICKER_RE.match(t)]
    if raros:
        print(f"⚠️  [{label}] {len(raros)} ticker(s) con formato inusual, revisa a mano: {raros}")
    return tickers


def _fetch_csv_tickers(url, ticker_col, timeout=15, header_marker=None,
                        asset_class_col=None, keep_asset_class="Equity"):
    """Descarga un CSV público y extrae la columna de tickers.

    header_marker: si el CSV trae texto antes de la cabecera real (como el
    de iShares, que mete metadatos del fondo arriba), se recorta todo lo
    anterior a ese marcador.
    asset_class_col / keep_asset_class: para CSVs de holdings de ETFs,
    para descartar líneas de cash/derivados que no son acciones.
    """
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    text = resp.text
    if header_marker and header_marker in text:
        text = text[text.index(header_marker):]
    reader = csv.DictReader(io.StringIO(text))
    tickers = []
    for row in reader:
        t = (row.get(ticker_col) or "").strip()
        if not t or t in ("-", "N/A"):
            continue
        if asset_class_col and row.get(asset_class_col) not in (None, "", keep_asset_class):
            continue
        tickers.append(t.replace(".", "-"))
    return _dedupe(tickers)


# --- DOW JONES COMPOSITE (65) ------------------------------------------
# No existe una fuente pública gratuita que se auto-actualice para este
# índice concreto (a diferencia del S&P 500 o el Nasdaq 100), así que se
# mantiene como lista estática. Se ha corregido un error real: "DOW" ya
# no forma parte del Dow Jones Industrial Average (fue sustituido por
# "SHW" en noviembre de 2024), así que sobraba en la lista original.
# Revisa esta lista manualmente de vez en cuando (composición oficial en
# https://en.wikipedia.org/wiki/Dow_Jones_Composite_Average), sobre todo
# los tramos de transporte y utilities, que no se han podido contrastar
# contra una fuente 100% actualizada.

def get_dowjones_tickers():
    tickers = [
        # Industrial (30)
        "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
        "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD", "MMM",
        "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT",
        # Transporte (20)
        "AAL", "CAR", "CHRW", "CSX", "DAL", "EXPD", "FDX", "JBHT", "KNX", "LUV",
        "MATX", "NSC", "ODFL", "R", "UNP", "UAL", "UPS", "XPO", "ALGT", "LSTR",
        # Utilities (15)
        "AEP", "AES", "ED", "D", "DUK", "EIX", "FE", "LNT", "NEE", "NI",
        "PCG", "PEG", "SRE", "SO", "WEC",
    ]
    return _validate_format(_dedupe(tickers), "Dow Jones Composite")


# --- NASDAQ 100 (dinámico) ---------------------------------------------

_NASDAQ100_URL = "https://raw.githubusercontent.com/Gary-Strauss/NASDAQ100_Constituents/master/data/nasdaq100_constituents.csv"

_NASDAQ100_FALLBACK = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD", "AMGN",
    "AMZN", "ANSS", "ASML", "AVGO", "AZN", "BKR", "BIIB", "BKNG", "CDNS", "CEG",
    "CHTR", "CMCSA", "COST", "CPRT", "CSGP", "CSX", "CTAS", "CTSH", "DDOG", "DLTR",
    "DXCM", "EA", "EXC", "FANG", "FAST", "FTNT", "GEHC", "GILD", "GOOG", "GOOGL",
    "HON", "IDXX", "ILMN", "INTC", "INTU", "ISRG", "KDP", "KHC", "KLAC", "LRCX",
    "LULU", "MAR", "MCHP", "MDB", "MDLZ", "MELI", "META", "MNST", "MRVL", "MSFT",
    "MU", "NFLX", "NVDA", "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR",
    "PDD", "PEP", "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SIRI", "SNPS",
    "TEAM", "TMUS", "TSLA", "TTD", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "XEL", "ZS",
]  # ⚠️ Lista de emergencia; puede estar desfasada. Se usa solo si falla la descarga.


def get_nasdaq100_tickers():
    try:
        tickers = _fetch_csv_tickers(_NASDAQ100_URL, ticker_col="Ticker")
        print(f"✅ NASDAQ 100 descargado en vivo ({len(tickers)} tickers).")
    except Exception as e:
        print(f"⚠️  No se pudo descargar el NASDAQ 100 actualizado ({e}); usando lista de respaldo (puede estar desfasada).")
        tickers = _dedupe(_NASDAQ100_FALLBACK)
    return _validate_format(tickers, "NASDAQ 100")


# --- S&P 500 (dinámico) -------------------------------------------------

_SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"

_SP500_FALLBACK = [
    "A", "AAL", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM", "ADP", "ADSK",
    "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB", "ALGN", "ALL", "ALLE", "AMAT",
    "AMCR", "AMD", "AME", "AMGN", "AMP", "AMT", "AMZN", "ANET", "ANSS", "AON", "AOS", "APA", "APD",
    "APH", "APTV", "ARE", "ATO", "AVB", "AVGO", "AVY", "AWK", "AXON", "AXP", "AZO", "BA", "BAC",
    "BALL", "BAX", "BBWI", "BBY", "BDX", "BEN", "BF-B", "BG", "BIIB", "BIO", "BK", "BKNG", "BKR",
    "BLDR", "BLK", "BMY", "BR", "BRK-B", "BRO", "BSX", "BWA", "BX", "BXP", "C", "CAG", "CAH",
    "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCJ", "CDNS", "CDW", "CE", "CEG", "CF", "CFG",
    "CHD", "CHRW", "CHTR", "CI", "CINF", "CL", "CLX", "CMA", "CMG", "CMI", "CMS", "CNC", "CNP",
    "COF", "COO", "COP", "COR", "COST", "CPB", "CPRT", "CPT", "CRL", "CRM", "CSCO", "CSGP", "CSX",
    "CTAS", "CTRA", "CTSH", "CTVA", "CVS", "CVX", "CZR", "D", "DAL", "DD", "DE", "DFS",
    "DG", "DGX", "DHI", "DHR", "DIS", "DLR", "DLTR", "DOC", "DOV", "DOW", "DPZ", "DRI", "DTE",
    "DUK", "DVA", "DVN", "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EG", "EIX", "EL", "ELV",
    "EMN", "EMR", "ENPH", "EOG", "EPAM", "EQT", "EQR", "EQIX", "ERIE", "ES", "ESS", "ETN",
    "ETR", "ETSY", "EVRG", "EW", "EXC", "EXPD", "EXPE", "EXR", "F", "FANG", "FAST", "FCX", "FDS",
    "FDX", "FE", "FFIV", "FI", "FICO", "FIS", "FITB", "FMC", "FOX", "FOXA", "FRT", "FSLR", "FTNT",
    "FTV", "GD", "GDDY", "GE", "GEHC", "GEN", "GEV", "GOOG", "GOOGL", "GPC", "GPK", "GPN", "GRMN", "GS", "GWW",
    "HAL", "HAS", "HBAN", "HCA", "HD", "HIG", "HII", "HLT", "HOLX", "HON", "HPE", "HPQ",
    "HRL", "HSIC", "HST", "HSY", "HUBB", "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN",
    "INCY", "INTC", "INTU", "INVH", "IP", "IPG", "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ",
    "J", "JBHT", "JBL", "JCI", "JKHY", "JNJ", "JNPR", "JPM", "K", "KDP", "KEY", "KEYS", "KHC",
    "KIM", "KLAC", "KMB", "KMI", "KMX", "KO", "KR", "L", "LDOS", "LEN", "LH", "LHX", "LIN",
    "LKQ", "LLY", "LMT", "LNT", "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB", "LYV", "MA",
    "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET", "META", "MGM", "MHK",
    "MKC", "MKTX", "MLM", "MMC", "MMM", "MNST", "MO", "MOH", "MOS", "MPC", "MPWR", "MRK", "MRNA",
    "MRO", "MS", "MSI", "MSFT", "MTB", "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE", "NEM", "NFLX",
    "NI", "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR", "NWS",
    "NWSA", "NXPI", "O", "ODFL", "OKE", "OMC", "ON", "ORLY", "ORCL", "OTIS", "OXY", "PANW", "PARA",
    "PAYX", "PAYC", "PYPL", "PNR", "PEP", "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD",
    "PLTR", "PM", "PNC", "PNW", "POOL", "PPG", "PPL", "PRU", "PSA", "PSX", "PTC", "PWR",
    "QCOM", "RCL", "REG", "REGN", "RF", "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RSG",
    "RTX", "RVTY", "SBAC", "SBUX", "SCHW", "SHW", "SJM", "SLB", "SNA", "SNPS",
    "SO", "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX", "STZ", "SWK", "SWKS", "SYF", "SYK",
    "SYY", "T", "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC", "TFX", "TGT", "TJX", "TMO",
    "TMUS", "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO", "TSN", "TSLA", "TT", "TTWO", "TXN",
    "TXT", "TYL", "UAL", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB", "V", "VICI",
    "VLO", "VLTO", "VMC", "VRSK", "VRSN", "VRTX", "VST", "VTR", "VTRS", "VZ", "WAB", "WAT", "WBA",
    "WBD", "WDC", "WEC", "WELL", "WFC", "WM", "WMB", "WMT", "WRB", "WST", "WTW", "WY",
    "WYNN", "XEL", "XOM", "XYL", "YUM", "ZBH", "ZBRA", "ZTS",
]  # ⚠️ Lista de emergencia; puede estar desfasada. Se usa solo si falla la descarga.


def get_sp500_tickers():
    try:
        tickers = _fetch_csv_tickers(_SP500_URL, ticker_col="Symbol")
        print(f"✅ S&P 500 descargado en vivo ({len(tickers)} tickers).")
    except Exception as e:
        print(f"⚠️  No se pudo descargar el S&P 500 actualizado ({e}); usando lista de respaldo (puede estar desfasada).")
        tickers = _dedupe(_SP500_FALLBACK)
    return _validate_format(tickers, "S&P 500")


# --- ESPAÑA: IBEX 35 + Mercado Continuo ---------------------------------
# El bloque IBEX 35 se ha actualizado a la composición vigente en agosto
# de 2026 (contrastada con investing.com). El bloque de "Mercado
# Continuo" (medium/small caps fuera del IBEX) NO se ha podido
# contrastar exhaustivamente contra una fuente actualizada — revísalo si
# depende de precisión.

def get_spain_tickers():
    tickers = [
        # IBEX 35 
        "SAN.MC", "BBVA.MC", "TEF.MC", "ITX.MC", "IBE.MC", "REP.MC", "AMS.MC",
        "CABK.MC", "SAB.MC", "FER.MC", "ACS.MC", "AENA.MC", "ELE.MC", "RED.MC", # Corregido REDE.MC -> RED.MC
        "MAP.MC", "COL.MC", "CLNX.MC", "FDR.MC", "GRF.MC", "ROVI.MC", "BKT.MC",
        "ANA.MC", "ENG.MC", "IAG.MC", "IDR.MC", "LOG.MC",
        "UNI.MC", "SLR.MC", "SCYR.MC", "ACX.MC", "NTGY.MC", "MTS.MC", "MRL.MC",
        "ANE.MC", "PUIG.MC",
        # Mercado Continuo (Corregido)
        "ALM.MC", "FAE.MC", "GRE.MC", "GEST.MC", "TLGO.MC", # Corregido FAES.MC -> FAE.MC
        "TUB.MC", "OHLA.MC", "FCC.MC", "A3M.MC", "LDA.MC", "DOM.MC", "NTH.MC", # Corregido NRE.MC -> NTH.MC (Naturhouse)
        "MVC.MC", "AZK.MC", "EZE.MC", "AMP.MC", "MDF.MC", "PRS.MC",
        "R4.MC", "ADX.MC", "ECO.MC", "CLEO.MC", "TRG.MC", "OLE.MC", # Corregido AUD.MC -> ADX.MC, CLE.MC -> CLEO.MC
        "AI.MC", "ORY.MC", "RLIA.MC", "ALNT.MC", "LGT.MC", "DIA.MC", # Corregido NLG.MC -> AI.MC
        "MEL.MC", "VIS.MC", "PHM.MC", "CAF.MC", "EBRO.MC",
    ]
    return _validate_format(_dedupe(tickers), "España")


# --- RUSSELL 2000 (dinámico, ~1900 tickers) ------------------------------
# La versión anterior de esta lista tenía 90 tickers duplicados y toda la
# pinta de haberse generado a mano/con un LLM sin verificación real — no
# es fiable. Aquí se sustituye por una descarga en vivo de las holdings
# públicas del ETF IWM (iShares Russell 2000 ETF), que reproduce el
# índice. Esa fuente puede tener protección anti-bot que bloquee
# `requests` en algunos entornos; si eso ocurre en el tuyo, la opción más
# robusta es descargar tú mismo el CSV una vez al mes desde
# https://www.ishares.com/us/products/239710/ishares-russell-2000-etf
# (botón "Download Holdings CSV") y guardarlo como russell2000_holdings.csv
# junto a este script — la función lo detecta y lo usa sin tocar la red.

_RUSSELL2000_URL = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/latest-holdings.csv"
_RUSSELL2000_LOCAL_CACHE = "russell2000_holdings.csv"

_RUSSELL2000_FALLBACK_NOTE = (
    "⚠️  Usando la lista estática de Russell 2000 heredada del script original. "
    "No ha sido posible verificarla ticker a ticker (son ~1500 nombres); se sabe "
    "que tenía decenas de duplicados, que ya se han eliminado aquí, pero pueden "
    "quedar tickers incorrectos o descatalogados. Trátala como último recurso."
)


def get_russell2000_tickers():
    # 1) Fichero local descargado a mano (más fiable, sin depender de la red)
    try:
        with open(_RUSSELL2000_LOCAL_CACHE, "r", encoding="utf-8") as f:
            text = f.read()
        marker = "Ticker,Name"
        if marker in text:
            text = text[text.index(marker):]
        reader = csv.DictReader(io.StringIO(text))
        tickers = _dedupe([
            row["Ticker"].strip().replace(".", "-")
            for row in reader
            if row.get("Asset Class") == "Equity" and row.get("Ticker", "").strip() not in ("-", "")
        ])
        print(f"✅ Russell 2000 leído de {_RUSSELL2000_LOCAL_CACHE} ({len(tickers)} tickers).")
        return _validate_format(tickers, "Russell 2000")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  Error leyendo {_RUSSELL2000_LOCAL_CACHE} ({e}), se intentará descarga en vivo.")

    # 2) Descarga en vivo desde iShares
    try:
        tickers = _fetch_csv_tickers(
            _RUSSELL2000_URL, ticker_col="Ticker", header_marker="Ticker,Name",
            asset_class_col="Asset Class", keep_asset_class="Equity",
        )
        print(f"✅ Russell 2000 descargado en vivo ({len(tickers)} tickers).")
        return _validate_format(tickers, "Russell 2000")
    except Exception as e:
        print(f"⚠️  No se pudo descargar el Russell 2000 en vivo ({e}).")
        print(_RUSSELL2000_FALLBACK_NOTE)
        return _validate_format(_dedupe(_RUSSELL2000_FALLBACK), "Russell 2000")


# Lista heredada del script original, solo como último recurso. Se ha
# deduplicado (tenía 90 tickers repetidos) pero NO se ha verificado
# individualmente contra una fuente actual.
_RUSSELL2000_FALLBACK = [
    "AAL", "AAON", "AAT", "AAWW", "ABCB", "ABG", "ABM", "ACAD", "ACDC", "ACLS",
    "ACMR", "ACRE", "ADTN", "ADNT", "AEIS", "AEO", "AAN", "AMTB", "AEL", "AGO",
    "AGYS", "AHCO", "AIRC", "AKR", "ALRM", "ALTR", "AMBA", "AMBC", "AMN", "AMPH",
    "AMR", "AMRC", "AMSF", "AMWD", "ANGO", "ANIK", "ANIP", "AOSL", "APAM", "APOG",
    "APPF", "APPN", "ARDX", "AROC", "ARR", "ARVN", "ARWR", "ASGN", "BHE", "ASIX",
    "ASB", "ASTE", "ATEN", "ATGE", "ATKR", "ATNI", "ATRC", "ATRI", "ATRO", "AUB",
    "AVA", "AVAV", "AVDL", "AVNS", "AVNT", "AVNW", "AVO", "AVT", "AXL", "AXSM",
    "AYI", "AZZ", "ACER", "ACET", "ACHV", "ACIU", "ACNB", "ACOR", "ACR", "ACTG",
    "ACU", "ACVA", "ADAG", "ADAP", "ADCT", "ADMA", "ADMP", "ADRO", "ADSE", "ADSK",
    "ADTH", "ADUS", "ADVM", "AEHR", "AEY", "AEYE", "AEVA", "AFBI", "AFCG", "AFG",
    "AFIB", "AFMD", "AFRM", "AFYA", "AGBA", "AGCO", "AGEN", "AGFS", "AGIL", "AGL",
    "AGLE", "AGM", "AGMH", "AGRI", "AGRO", "AGRX", "AGS", "AGTC", "AGTI", "AGX",
    "AHG", "AHH", "AHT", "AI", "AIFU", "AIG", "AIH", "AIHS", "AIM", "BANC",
    "BANF", "BANR", "BZH", "BCOR", "BDC", "BEAM", "BELFA", "BHB", "BJRI", "BKU",
    "BLKB", "BLMN", "BMBL", "BME", "BMI", "BNL", "BOC", "BOOT", "BOX", "BRKL",
    "BSRR", "BABY", "BAC", "BACK", "BAFN", "BAND", "BANX", "BAOS", "BASE", "BATL",
    "BBAR", "BBCP", "BGI", "BBIO", "BBLG", "BBSI", "BCAB", "BCAN", "BCBP", "BCC",
    "BCDA", "BCEI", "BCEL", "BCML", "BCRX", "BCSF", "BCTF", "BCTX", "BDFC", "BDRX",
    "BFC", "BFAM", "BFI", "BFH", "BFRG", "BFST", "BGB", "BGCP", "BGFV", "BGNE",
    "BGRY", "BHAL", "BHAT", "BHF", "BHIL", "BHR", "BHVN", "BIDU", "BIG", "BIGC",
    "BILL", "BIMI", "BIOA", "BIOC", "BIOL", "BIOR", "BIOS", "BIOT", "BIPL", "BIRD",
    "BITF", "BIVI", "BJDX", "BKCC", "BKD", "BKE", "BKEP", "BKH", "BKKT", "BKNG",
    "BKR", "BKSC", "BKTI", "BKYI", "BL", "BLBD", "BLBX", "BLCM", "CBL", "CBT",
    "CBU", "CCB", "CCF", "CCNE", "CCOI", "CDLX", "CEIX", "CENT", "CFFN", "CGNT",
    "CHCO", "CHEF", "CHFC", "CHMG", "CHS", "CIEN", "CIVB", "CLBK", "CLFD", "CLW",
    "CMRX", "CNMD", "CNNE", "CNO", "CNX", "COCH", "COHU", "COKE", "COLB", "COLL",
    "CONN", "CORT", "CPRX", "CRAI", "CRGY", "CRK", "CRL", "CRMD", "CRS", "CRUS",
    "CRVL", "CSGS", "CSR", "CSTM", "CSV", "CTBI", "CTRE", "CTRN", "CVBF", "CVCO",
    "CVGI", "CVGW", "CVLT", "CWCO", "CWEN", "CWT", "CXW", "CYRX", "CYTK", "CABO",
    "CAC", "CACC", "CADE", "CADL", "CAE", "CAG", "CAKE", "CAL", "CALA", "CALB",
    "CALM", "CALX", "CAMP", "CAMT", "CAN", "CAPR", "CARA", "CARE", "CARG", "CARR",
    "CARS", "CARV", "CASA", "CASH", "CASI", "CASS", "CASY", "CATC", "CATH", "CATY",
    "CBAN", "CBAT", "CBAY", "CBFV", "CBIO", "CBLY", "CBNK", "CBON", "CBRE", "CBRG",
    "CBRL", "CBSH", "CBTX", "CBYL", "CCAP", "CCBG", "DAR", "DAN", "DCI", "DENN",
    "DFIN", "DGII", "DHC", "DHIL", "DHT", "DIOD", "DLX", "DNB", "DNLI", "DORM",
    "DRH", "DRQ", "DRS", "DTE", "DY", "DAIO", "DAKT", "DAL", "DARE", "DASH",
    "DATS", "DAVE", "DAWN", "DBGI", "DBVT", "DCO", "DCP", "DDD", "DDS", "DECK",
    "DEN", "DERM", "DFH", "DGICA", "DGICB", "DHCV", "DINO", "DISA", "DIT", "DJCO",
    "DK", "DKL", "DKS", "DLHC", "DLPN", "DLTH", "DMAC", "DMTK", "DNMR", "DNUT",
    "DOCN", "DOCU", "DOMO", "DOLE", "DOOR", "DOUA", "DOX", "DPZ", "DQ", "DRD",
    "DRI", "DRIO", "DRRX", "DRVN", "DSGN", "DSGR", "DSP", "DSS", "DSWL", "DT",
    "DLA", "DTIL", "EAT", "EBC", "EBF", "EGB", "EGP", "EIG", "EIX", "ELF",
    "EME", "ENR", "ENS", "ENV", "ENVA", "EPC", "EPRT", "ESE", "ESGR", "ESNT",
    "EVTC", "EWA", "EXPO", "EXTN", "EAF", "EAGL", "EBTC", "ECPG", "EDIT", "EDR",
    "EDRY", "EDTX", "EEFT", "EEX", "EEXC", "EEXS", "EFSC", "EFX", "EGAN", "EGBN",
    "EGHT", "EGLX", "EIGR", "EIM", "EKSO", "ELAL", "ELAN", "ELBM", "ELC", "ELDN",
    "ELEV", "ELMD", "ELOX", "ELPK", "ELSE", "ELTK", "ELYM", "EMBC", "EMCF", "EMKR",
    "EML", "EMLD", "EMN", "EMR", "EMX", "ENB", "ENFN", "ENG", "ENIC", "ENLV",
    "ENOB", "ENPH", "ENSG", "ENSV", "ENTG", "ENVB", "ENX", "ENZ", "EOC", "EOD",
    "EOG", "EOLS", "EOSE", "EPAM", "FANH", "FBK", "FBNC", "FBP", "FBY", "FCBC",
    "FCF", "FCFS", "FDBC", "FELE", "FFBC", "FFIC", "FFIN", "FFNW", "FHI", "FIBK",
    "FINV", "FISI", "FIVE", "FLIC", "FLNG", "FLO", "FLR", "FLY", "FMAO", "FNB",
    "FNCB", "FNLC", "FNTG", "FOR", "FORWARD", "FSLR", "FSM", "FTAI", "FTDR", "FUL",
    "FULT", "FACT", "FAII", "FALN", "FANG", "FARO", "FAST", "FATE", "FATP", "FBC",
    "FBIZ", "FBMS", "FBRT", "FCAP", "FCCO", "FCOA", "FCRD", "FCX", "FDEF", "FDS",
    "FDUS", "FERG", "FFBW", "FFC", "FFHG", "FFIV", "FGBI", "FGEN", "FGF", "FGLD",
    "FGMC", "FHN", "FHS", "FIAC", "FICO", "FIII", "FITB", "FIVN", "FIXX", "FIZZ",
    "FJP", "GATX", "GBCI", "GBX", "GCBC", "GCO", "GENC", "GEOS", "GERN", "GHC",
    "GHL", "GIII", "GKOS", "GLDD", "GLP", "GLRE", "GLT", "GNE", "GPMT", "GPRE",
    "GRNT", "GTLS", "GTY", "GWB", "GATO", "GAU", "GBAB", "GBIO", "GBLI", "GBNH",
    "GBNY", "GBS", "GCI", "GCMG", "GCOT", "GCP", "GCV", "GDEN", "GDEV", "GDL",
    "GDRX", "GDYN", "GECC", "GEF", "GEG", "GEO", "GEVO", "GFED", "GFFF", "GFGD",
    "GFL", "GGE", "GGG", "GH", "GHAC", "GHIX", "GHIY", "GHRS", "GIB", "GIC",
    "GIFI", "GIGM", "GIL", "GILD", "GILT", "GIPR", "GLAD", "GLEO", "GLMD", "GLNG",
    "GLOB", "GLOP", "HAFC", "HAIN", "HALO", "HBB", "HBCP", "HBNC", "HCA", "HCSG",
    "HEES", "HFWA", "HI", "HIBB", "HIG", "HIW", "HLIT", "HLX", "HMST", "HOPE",
    "HP", "HPK", "HR", "HRI", "HRMY", "HTH", "HUBG", "HWC", "HWKN", "HY",
    "HAYN", "HBAN", "HBI", "HBIO", "HCAT", "HCC", "HCCI", "HCKT", "HCM", "HCTI",
    "HDG", "HDSN", "HE", "HEAR", "HEI", "HELE", "HEP", "HEPA", "HEQ", "HERA",
    "HERO", "HEWI", "HFBL", "HFFG", "HGBL", "HGEN", "HGLB", "HHH", "HIFS", "HIHO",
    "HII", "HIIN", "HIMS", "HIPO", "HIX", "HKIT", "HL", "HLF", "HLGN", "HLI",
    "HLNE", "HLT", "IART", "IBOC", "IBTX", "ICFI", "ICUI", "IESC", "IGMS", "IGT",
    "IHRT", "IIPR", "ILLM", "IMAX", "INDB", "INGR", "INN", "INOV", "INSG", "INSM",
    "INSW", "INT", "INVA", "INVE", "IONR", "IOSP", "IPAR", "IPGP", "IPI", "IRDM",
    "IRMD", "IROQ", "IRT", "ITCI", "ITGR", "ITRI", "ITT", "IAC", "IBA", "IBCP",
    "IBEX", "IBP", "ICCC", "ICCM", "ICD", "ICHR", "ICLK", "ICLR", "ICMB", "ICPT",
    "ICU", "IDA", "IDAI", "IDCC", "IDN", "IDT", "IDYA", "IEC", "IEX", "IFF",
    "IFGL", "IFRX", "IFV", "IGA", "IGC", "IGD", "IGIC", "IGNY", "IGSB", "IHD",
    "IIGD", "III", "IIIN", "IIIV", "JACK", "JBSS", "JELD", "JJSF", "JKHY", "JOUT",
    "JRNA", "JRVR", "KALU", "KAR", "KBH", "KFRC", "KLIC", "KNSA", "KRO", "KTB",
    "KTOS", "JAG", "JAKK", "JAMF", "JAN", "JBLU", "JCE", "JCG", "JCH", "JCTCF",
    "JD", "JDEP", "JFIN", "JFU", "JG", "JILL", "JKS", "JLL", "JMD", "JMM",
    "JMS", "JNCE", "JNJ", "JNPR", "JOB", "JOE", "JOF", "JOYY", "JPHY", "JRSH",
    "KA", "KAFM", "KAMN", "KATE", "KBAL", "KBDC", "KBNT", "KBR", "KC", "KDI",
    "KDNY", "KE", "KELYA", "KEM", "KEN", "KEP", "KEX", "LAD", "LADR", "LMAT",
    "LMNR", "LNTH", "LOB", "LOM", "LOPE", "LPI", "LPSN", "LQDT", "LTC", "LTRPA",
    "LUMN", "LUNA", "LXU", "LAAC", "LAB", "LABP", "LAKE", "LAMR", "LANC", "LAND",
    "LARK", "LASR", "LAUR", "LAW", "LAZR", "LAZY", "LBA", "LBRA", "LBRDA", "LBRDK",
    "LBRT", "LC", "LCAC", "LCI", "LCNB", "LCUT", "LDHA", "LDOS", "LE", "LEA",
    "LEAP", "LECO", "LEDS", "LEE", "LEG", "LEGH", "LEGN", "LEJU", "LELV", "LEMD",
    "LMDX", "LMFA", "LOAN", "LNC", "LNG", "LNN", "LNSR", "LNW", "LOCO", "LOD",
    "MATX", "MAXN", "MBWM", "MCB", "MCRI", "MDC", "MDGL", "MDRX", "MDU", "MEDP",
    "MEI", "MFA", "MFRM", "MGPI", "MGRC", "MHO", "MIME", "MMS", "MMSI", "MNDO",
    "MNRO", "MOD", "MODN", "MOV", "MPLN", "MPWR", "MRCY", "MRTN", "MRUS", "MSA",
    "MSBI", "MSCI", "MSM", "MSTR", "MTDR", "MGEE", "MTH", "MTN", "MTRN", "MWA",
    "MXL", "MYGN", "MYRG", "MAA", "MAC", "MACK", "MACU", "MAG", "MAGS", "MAIA",
    "MAIN", "MAN", "MANH", "MANU", "MAPS", "MARA", "MARK", "MARPS", "MASI", "MATW",
    "MAX", "MBIN", "MBIO", "MBNKP", "MBOT", "MBRX", "MBUU", "MC", "MCBC", "MCBS",
    "MCC", "MCD", "MCFT", "MCG", "MCHX", "MCI", "MCK", "MCN", "NAPA", "NATH",
    "NAVI", "NBHC", "NBN", "NC", "NCLH", "NCNO", "NDSN", "NEU", "NEOG", "NESR",
    "NET", "NEWR", "NEX", "NEXT", "NFBK", "NGVT", "NHC", "NJR", "NKLA", "NLOK",
    "NMIH", "NNN", "NODK", "NOVT", "NPO", "NRP", "NSIT", "NSP", "NSS", "NTB",
    "NTCT", "NTHS", "NTLA", "NTRA", "NTUS", "NUV", "NVEC", "NVMI", "NVRI", "NVRO",
    "NVT", "NWBI", "NWFL", "NWN", "NX", "NXGN", "NXRT", "NXST", "NYCB", "NYMT",
    "NAAS", "NABL", "NARI", "NAT", "NATR", "NAVB", "NBEV", "NBR", "NBRV", "NBTB",
    "NCBS", "NMM", "NMRK", "OAX", "OBK", "OCFC", "OCN", "OCUL", "ODC", "OEC",
    "OFLX", "OFG", "OII", "OIS", "OLN", "OMCL", "ONB", "ONEM", "ONTF", "OOMA",
    "OPCH", "OPLN", "OPY", "ORA", "ORC", "ORRF", "OSCR", "OSIS", "OSK", "OSPN",
    "OTTR", "OUT", "OZK", "PACB", "PAG", "PAR", "PARR", "PASG", "PATK", "PB",
    "PBA", "PBC", "PBI", "PBF", "PBH", "PBPB", "PBYI", "PCBK", "PCF", "PCRX",
    "PCTY", "PDS", "PDCE", "PEBO", "PECO", "PENN", "PEPG", "PFBC", "PFC", "PFIS",
    "PFMT", "PGC", "PGTI", "PHIN", "PII", "PINE", "PING", "PLAB", "PLAY", "PLOW",
    "PLSE", "PLUS", "PLXS", "PNTG", "PNFP", "POL", "POR", "POWI", "PPBI", "PRAA",
    "PRAX", "PRFT", "PRG", "QCRH", "RDC", "RDNT", "RGNX", "RGR", "RHI", "RHP",
    "QADB", "QD", "QDEL", "QFIN", "QIWI", "QLGN", "QLYS", "QNST", "QPAC", "QTRX",
    "RACC", "RAD", "RADA", "RAMP", "RARE", "RAVE", "RBC", "RBCAA", "RBCN", "RCEL",
    "RCKT", "RCKY", "RCL", "RCM", "RCUS", "RDVT", "REAX", "REE", "REFI", "REFR",
    "REI", "RELI", "RELL", "RENE", "REPL", "REPX", "RES", "RETA", "REVG", "REX",
    "REXR", "REZI", "RFIL", "RGA", "RGCO", "RGEN", "RGLD", "RGLS", "RGP", "RIG",
    "SABR", "SAFT", "SAGE", "SAH", "SAM", "SANM", "SASR", "SBBP", "SBGI", "SBH",
    "SBNY", "SBOW", "SBRA", "SBR", "SBS", "SBUX", "SCAC", "SCHN", "SCHL", "SCOR",
    "SCPH", "SCSC", "SCVL", "SD", "SDGR", "SEAC", "SEAS", "SEB", "SEE", "SELB",
    "SEM", "SEMR", "SENEA", "SENS", "SF", "SFBS", "SFNC", "SFST", "SGA", "SGC",
    "SGEN", "SGH", "SGMO", "SGMS", "SGRY", "SGU", "SHAK", "SHBI", "SHEN", "SHLO",
    "SHOO", "SHM", "SHYF", "SI", "SIBN", "SIEN", "SIG", "SIGA", "SIGI", "SILK",
    "TACT", "TAIT", "TAL", "TALO", "TALK", "TAP", "TARS", "TAST", "TBBK", "TBI",
    "TCBK", "TCBI", "TCBP", "TCBX", "TCFC", "TCI", "TCMD", "TCNB", "TCRX", "TCS",
    "TDF", "TDUP", "TECD", "TECH", "TTEC", "TGEN", "TGH", "TGI", "TGNA", "TGR",
    "TH", "THC", "THFF", "THG", "THO", "THRM", "TIG", "TIPT", "TISI", "TITN",
    "TKO", "TKR", "TLRY", "TMBR", "TMCI", "TMDX", "TNET", "TNGO", "TNK", "TNL",
    "UBSI", "UCBI", "UDR", "UE", "UEIC", "UFCS", "UFI", "UFPI", "UGI", "UHAL",
    "UI", "ULCC", "ULTA", "UMBF", "UMH", "UNF", "UNFI", "UNIT", "UNM", "UNVR",
    "URBN", "URG", "URGN", "URI", "USAC", "USAP", "USCB", "USEG", "USLM", "USM",
    "USNA", "USPH", "UTI", "UTL", "UTMD", "UTRS", "UTZ", "UVE", "UVSP", "VAX",
    "VAXX", "VBTX", "VC", "VCEL", "VCTR", "VECO", "VFF", "VGR", "VIA", "VIAC",
    "VICI", "VIDE", "VIE", "VINC", "VIP", "VIR", "VIRT", "VISL", "VLO", "VLY",
    "VMC", "VMEO", "VNDA", "VNOM", "VNT", "VOPN", "VOXX", "VPG", "VRA", "VRAY",
    "VRCA", "VRDN", "VMD", "VRE", "VRML", "VRNS", "VRNT", "VRRM", "VRS", "VSEC",
    "VSH", "VSTA", "VSTM", "VTC", "VTGN", "VTLE", "VTOL", "VTRU", "VTYX", "VUZI",
    "VVNT", "VVOS", "VVV", "VXRT", "VYGR", "VYNE", "WAB", "WAC", "WABC", "WAFU",
    "WAFD", "WAL", "WLD", "WNC", "WOOD", "WOR", "WRAP", "WRLD", "WSBC", "WSC",
    "WSFS", "WSR", "WST", "WTBA", "WTFC", "WTI", "WTM", "TR", "WWD", "WW",
    "XEC", "XERS", "XFLT", "XFOR", "XGN", "XHR", "XNCR", "XOG", "XOM", "XOMA",
    "XPEL", "XPER", "XPL", "XPO", "XPRO", "XRAY", "XRM", "XTLB", "XTSL", "XXII",
    "XYL", "Y", "YELL", "YETI", "YETN", "YEXT", "YGYI", "YMAB", "YORW", "YPF",
    "YTRA", "ZEUS", "ZGNX", "ZIM", "ZIMV", "ZION", "ZIP", "ZIXI", "ZNTL", "ZOM",
    "ZUMZ", "ZURA", "ZVO", "ZYME", "ZYXI",
]


# --- CONSOLIDACIÓN --------------------------------------------------------

def get_all_tickers():
    """Consolida universos evitando duplicados según orden de prioridad."""
    universo = {}
    fuentes = [
        (get_dowjones_tickers, "Dow Jones Composite"),
        (get_sp500_tickers, "S&P 500"),
        (get_nasdaq100_tickers, "NASDAQ 100"),
        (get_russell2000_tickers, "Russell 2000"),
    ]
    for func, nombre in fuentes:
        for t in func():
            universo.setdefault(t, nombre)

    # España se añade/sobrescribe siempre con su propia etiqueta, como en el original
    for t in get_spain_tickers():
        universo[t] = "España"

    return universo


# --- EXTRACCIÓN Y PROCESAMIENTO (sin cambios respecto al original) ------

def fetch_single_ticker(ticker, max_retries=3):
    """Obtiene datos de yfinance con reintentos para controlar el Rate Limit."""
    for attempt in range(max_retries):
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if not info or ("regularMarketPrice" not in info and "currentPrice" not in info):
                hist = t.history(period="1d")
                if hist.empty:
                    return None
            return info
        except Exception as e:
            err_str = str(e)
            if "Rate" in err_str or "Too Many Requests" in err_str or "429" in err_str:
                wait_time = (attempt + 1) * 3 + random.uniform(1, 3)
                print(f"  [Rate Limit] Esperando {wait_time:.1f}s para {ticker}...")
                time.sleep(wait_time)
            else:
                return None
    return None


def extract_metrics(ticker, index_name, info):
    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    mcap = info.get("marketCap")
    mcap_b = (mcap / 1e9) if mcap else None
    
    # Cálculo de P/FCF usando el freeCashflow si está disponible
    fcf = info.get("freeCashflow")
    p_fcf = (mcap / fcf) if (mcap and fcf and fcf > 0) else None

    rev_growth = info.get("revenueGrowth")
    eps_growth = info.get("earningsGrowth")

    # PEG: si Yahoo no lo da (~42% de los casos), lo calculamos con PE / crecimiento EPS,
    # que es la propia definición de PEG. Solo si el crecimiento es positivo (si no, PEG no
    # tiene lectura útil).
    peg = info.get("pegRatio")
    if peg is None:
        pe_for_peg = info.get("forwardPE") or info.get("trailingPE")
        if pe_for_peg and eps_growth and eps_growth > 0:
            peg = pe_for_peg / (eps_growth * 100)

    # ROIC aproximado: el campo que se usaba antes ("returnOnCapitalEmployed") no existe en
    # yfinance y siempre devolvía None. Esta es una aproximación con datos que SÍ vienen en
    # .info (sin llamadas de red extra): EBIT ~ margen operativo x ingresos, Equity ~ book
    # value x acciones. Es una estimación para poder ordenar/filtrar el universo completo —
    # el ROIC preciso (con EBIT y patrimonio neto reales del balance) se calcula solo para
    # las empresas seleccionadas, en el Análisis Profundo de app.py.
    roic_approx = None
    op_margin = info.get("operatingMargins")
    revenue = info.get("totalRevenue")
    book_value = info.get("bookValue")
    shares_out_bs = info.get("sharesOutstanding")
    total_debt_bs = info.get("totalDebt") or 0
    total_cash_bs = info.get("totalCash") or 0
    if op_margin is not None and revenue and book_value and shares_out_bs:
        ebit_approx = op_margin * revenue
        equity_approx = book_value * shares_out_bs
        invested_capital_approx = total_debt_bs + equity_approx - total_cash_bs
        if invested_capital_approx > 0:
            nopat_approx = ebit_approx * (1 - 0.21)  # tasa fija de aproximación
            roic_approx = (nopat_approx / invested_capital_approx) * 100
            if roic_approx < -100 or roic_approx > 200:  # ruido numérico, no un ROIC real
                roic_approx = None

    # Debt/Equity: yfinance lo da en escala porcentual (ej. 59.4 = 59.4%), pero el resto de la
    # app (presets, filtros) asume escala ratio (0.5 = 50%). Se convierte ÷100 y se recortan
    # valores fuera de un rango razonable (probable artefacto numérico por equity ~0).
    de_raw = info.get("debtToEquity")
    debt_equity = None
    if de_raw is not None:
        de_ratio = de_raw / 100
        if 0 <= de_ratio <= 50:
            debt_equity = de_ratio

    return {
        "Ticker": ticker,
        "Nombre": info.get("shortName") or info.get("longName") or ticker,
        "Índice": index_name,
        "Precio": price,
        "Market Cap (B)": mcap_b,
        "PER (Trailing)": info.get("trailingPE"),
        "PER (Forward)": info.get("forwardPE"),
        "PEG": peg,
        "EV/EBITDA": info.get("enterpriseToEbitda"),
        "EV/Sales": info.get("enterpriseToRevenue"),
        "P/S": info.get("priceToSalesTrailing12Months"),
        "P/B": info.get("priceToBook"),
        "P/FCF": p_fcf, # ¡Columna arreglada!
        "Crec. Ventas YoY (%)": (rev_growth * 100) if rev_growth is not None else None,
        "Crec. EPS YoY (%)": (eps_growth * 100) if eps_growth is not None else None,
        # Crec. Ventas/EPS a 3 años: se ha quitado de aquí (siempre daba None — nunca se llegó a
        # calcular). El CAGR real a 3-4 años se calcula ahora en el Análisis Profundo de app.py,
        # reutilizando el income_stmt que ya se descarga ahí para el ROIC y el PER histórico
        # (coste de red ≈ 0 extra), en vez de duplicar aquí ~2.500 llamadas más.
        "ROIC Aprox. (%)": roic_approx,  # ROIC exacto: solo en el Análisis Profundo (app.py)
        "ROE (%)": (info.get("returnOnEquity") * 100) if info.get("returnOnEquity") is not None else None,
        "ROA (%)": (info.get("returnOnAssets") * 100) if info.get("returnOnAssets") is not None else None,
        "Margen Bruto (%)": (info.get("grossMargins") * 100) if info.get("grossMargins") is not None else None,
        "Margen Operativo (%)": (info.get("operatingMargins") * 100) if info.get("operatingMargins") is not None else None,
        "Margen Neto (%)": (info.get("profitMargins") * 100) if info.get("profitMargins") is not None else None,
        "Debt/Equity": debt_equity,
        "Current Ratio": info.get("currentRatio"),
        "Payout Ratio (%)": (info.get("payoutRatio") * 100) if info.get("payoutRatio") is not None else None,
    }


def main():
    print("🚀 Iniciando descarga de datos...")
    universo = get_all_tickers()
    total = len(universo)
    print(f"📊 Total tickers a procesar: {total}")

    data = []
    failed = []

    for i, (ticker, idx) in enumerate(universo.items(), start=1):
        print(f"[{i}/{total}] Procesando {ticker} ({idx})...", end="", flush=True)
        info = fetch_single_ticker(ticker)

        if info:
            data.append(extract_metrics(ticker, idx, info))
            print(" ✅ OK")
        else:
            failed.append(ticker)
            print(" ❌ Sin datos / Omitido")

        time.sleep(0.2)

    df = pd.DataFrame(data)
    df.to_csv("market_data.csv", index=False)
    print(f"\n🎉 Guardado 'market_data.csv' con {len(df)} empresas.")
    if failed:
        print(f"⚠️  {len(failed)} tickers sin datos (revisar si son errores puntuales de yfinance o tickers inválidos): {failed}")


if __name__ == "__main__":
    main()
