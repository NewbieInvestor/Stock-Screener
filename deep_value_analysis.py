"""
deep_value_analysis.py
Análisis profundo (ROIC y DCF) para una lista reducida de empresas Value.
"""

import yfinance as yf
import pandas as pd
import numpy as np

# 1. PON AQUÍ LOS TICKERS QUE PASARON TU FILTRO
TICKERS_VALUE = ["YELP", "PFE", "BLK", "SBC"] 

# 2. ASUNCIONES PARA EL MODELO DCF
WACC = 0.10              # Tasa de descuento (10%)
TERMINAL_GROWTH = 0.025  # Crecimiento a perpetuidad (2.5%)
PROJECTION_YEARS = 5     # Años a proyectar

def get_exact_roic(ticker_obj):
    """Calcula el ROIC usando los últimos estados financieros anuales."""
    try:
        inc_stmt = ticker_obj.income_stmt
        bal_sheet = ticker_obj.balance_sheet
        
        if inc_stmt.empty or bal_sheet.empty:
            return None
            
        # Extraer datos (último año fiscal)
        ebit = inc_stmt.loc["EBIT"].iloc[0] if "EBIT" in inc_stmt.index else inc_stmt.loc["Operating Income"].iloc[0]
        pretax_income = inc_stmt.loc["Pretax Income"].iloc[0]
        tax_provision = inc_stmt.loc["Tax Provision"].iloc[0]
        
        # Tasa impositiva efectiva
        tax_rate = tax_provision / pretax_income if pretax_income > 0 else 0.21
        nopat = ebit * (1 - tax_rate)
        
        # Capital Invertido
        total_debt = bal_sheet.loc["Total Debt"].iloc[0] if "Total Debt" in bal_sheet.index else 0
        total_equity = bal_sheet.loc["Stockholders Equity"].iloc[0]
        cash = bal_sheet.loc["Cash And Cash Equivalents"].iloc[0] if "Cash And Cash Equivalents" in bal_sheet.index else 0
        
        invested_capital = total_debt + total_equity - cash
        
        if invested_capital > 0:
            return (nopat / invested_capital) * 100
        return None
    except Exception:
        return None

def calculate_dcf(ticker_obj, current_price):
    """Calcula el Valor Intrínseco por acción usando un DCF simplificado."""
    try:
        cash_flow = ticker_obj.cash_flow
        info = ticker_obj.info
        
        if cash_flow.empty or "Free Cash Flow" not in cash_flow.index:
            return None, None
            
        # Coger el FCF histórico y calcular un promedio conservador de los últimos 3 años
        historical_fcf = cash_flow.loc["Free Cash Flow"].dropna().head(3)
        if len(historical_fcf) == 0 or historical_fcf.mean() < 0:
            return None, None # Difícil modelar DCF con FCF negativo
            
        base_fcf = historical_fcf.mean()
        
        # Proyección simple de FCF (asumimos crecimiento conservador del 5% los primeros 5 años)
        fcf_growth = 0.05 
        projected_fcf = [base_fcf * ((1 + fcf_growth) ** i) for i in range(1, PROJECTION_YEARS + 1)]
        
        # Descontar FCF proyectados
        discounted_fcf = sum([fcf / ((1 + WACC) ** i) for i, fcf in enumerate(projected_fcf, 1)])
        
        # Valor Terminal
        terminal_value = (projected_fcf[-1] * (1 + TERMINAL_GROWTH)) / (WACC - TERMINAL_GROWTH)
        discounted_tv = terminal_value / ((1 + WACC) ** PROJECTION_YEARS)
        
        # Enterprise Value a Equity Value
        enterprise_value = discounted_fcf + discounted_tv
        
        bal_sheet = ticker_obj.balance_sheet
        total_debt = bal_sheet.loc["Total Debt"].iloc[0] if "Total Debt" in bal_sheet.index else 0
        cash = bal_sheet.loc["Cash And Cash Equivalents"].iloc[0] if "Cash And Cash Equivalents" in bal_sheet.index else 0
        
        equity_value = enterprise_value - total_debt + cash
        
        shares_out = info.get("sharesOutstanding")
        if not shares_out:
            return None, None
            
        intrinsic_value = equity_value / shares_out
        margin_of_safety = ((intrinsic_value - current_price) / intrinsic_value) * 100 if intrinsic_value > 0 else 0
        
        return intrinsic_value, margin_of_safety
        
    except Exception:
        return None, None

def main():
    print("👑 Iniciando análisis profundo (Cálculo de ROIC y DCF)...")
    results = []
    
    for ticker in TICKERS_VALUE:
        print(f"Analizando {ticker}...", end=" ", flush=True)
        t = yf.Ticker(ticker)
        info = t.info
        
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        
        if not current_price:
            print("❌ Sin precio de mercado.")
            continue
            
        roic = get_exact_roic(t)
        intrinsic_value, mos = calculate_dcf(t, current_price)
        
        results.append({
            "Ticker": ticker,
            "Precio Actual": round(current_price, 2),
            "Valor Intrínseco (DCF)": round(intrinsic_value, 2) if intrinsic_value else "N/A",
            "Margen de Seguridad (%)": round(mos, 2) if mos else "N/A",
            "ROIC Exacto (%)": round(roic, 2) if roic else "N/A",
            "PER (Forward)": info.get("forwardPE")
        })
        print("✅ Completado")
        
    df_results = pd.DataFrame(results)
    print("\n--- RESULTADOS DEL ANÁLISIS ---")
    print(df_results.to_string(index=False))
    df_results.to_csv("deep_value_results.csv", index=False)
    print("\n💾 Guardado en 'deep_value_results.csv'")

if __name__ == "__main__":
    main()