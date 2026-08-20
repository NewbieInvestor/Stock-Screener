@echo off
cd /d "%~dp0"
echo === Paso 1: Descargando datos (fetch_data.py) ===
python fetch_data.py
if errorlevel 1 (
    echo Fallo en fetch_data.py
    pause
    exit /b 1
)

echo.
echo === Paso 2: Aplicando filtros del screener ===
python filter_screener.py

echo.
echo === Hecho. Revisa screener_resultados.csv ===
pause
