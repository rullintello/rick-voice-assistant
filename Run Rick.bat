@echo off
setlocal
cd /d "%~dp0Programma"

rem --- Avvio veloce ------------------------------------------------------
rem Se Rick e' gia' configurato su questo PC, le sue librerie sono ancora
rem quelle installate l'ultima volta e il suo Python risponde, parte subito:
rem niente ricerca di Python e niente controllo delle librerie con pip
rem (erano quelli i secondi di attesa a ogni avvio).
if not exist ".venv\Scripts\pythonw.exe" goto setup
fc /b "requirements.txt" ".venv\rick-installed.txt" >nul 2>&1
if errorlevel 1 goto setup
".venv\Scripts\python.exe" -c "" >nul 2>&1
if errorlevel 1 goto setup
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

rem --- Prima configurazione, o librerie da aggiornare --------------------
:setup
rem Un ambiente rimasto senza il suo Python (disinstallato, o sostituito da
rem un'altra versione) non si ripara: si ricrea da zero.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "" >nul 2>&1
    if errorlevel 1 rmdir /s /q ".venv"
)
if exist ".venv\Scripts\python.exe" goto install

rem Primo avvio: un avviso chiede di installare Python dal sito ufficiale.
rem Quando l'utente spunta "Ho scaricato e installato Python", ce lo
rem ricordiamo e l'avviso non compare piu'.
if not exist ".python-installed" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "assets\python_notice.ps1"
    if errorlevel 1 exit /b 1
    type nul > ".python-installed"
)

echo Prima configurazione in corso, un attimo di pazienza... / First-time setup in progress, please wait...
py -3 -m venv .venv >nul 2>&1 || python -m venv .venv >nul 2>&1
if exist ".venv\Scripts\python.exe" goto install

rem Python non c'e' davvero: al prossimo avvio l'avviso ricompare.
del ".python-installed" >nul 2>&1
echo.
echo Python non risulta installato. Installalo dal sito ufficiale, poi rilancia questo file.
echo Python doesn't seem to be installed. Install it from the official site, then rerun this file.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:install
echo Installazione librerie in corso... / Installing libraries...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo Errore durante l'installazione delle librerie necessarie a Rick. / Error installing the libraries Rick needs.
    echo Controlla la connessione a internet e rilancia questo file. / Check your internet connection and rerun this file.
    pause
    exit /b 1
)
copy /y "requirements.txt" ".venv\rick-installed.txt" >nul
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0
