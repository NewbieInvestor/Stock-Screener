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

echo === Instalando/actualizando dependencias (solo tarda si falta algo) ===
%PYCMD% -m pip install -r requirements.txt -q

echo.
echo === Abriendo la app en el navegador ===
REM Usamos "python -m streamlit" en vez de "streamlit" a secas porque el
REM ejecutable streamlit.exe no esta en el PATH en este equipo.
%PYCMD% -m streamlit run app.py

echo.
echo === La app se ha cerrado ===
pause
