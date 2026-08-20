@echo off
cd /d "%~dp0"

REM Detecta si "python" existe en el PATH; si no, usa "py" (launcher de Windows).
where python >nul 2>nul
if %errorlevel%==0 (
    set PYCMD=python
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set PYCMD=py
    ) else (
        echo No se ha encontrado "python" ni "py" en el PATH.
        echo Instala Python o revisa tu instalacion.
        pause
        exit /b 1
    )
)

echo === Actualizando market_data.csv desde Yahoo Finance ===
echo (esto puede tardar varios minutos, es normal)
%PYCMD% fetch_data.py

echo.
echo === Hecho. Ya puedes abrir run_app.bat para explorar los datos actualizados ===
pause
