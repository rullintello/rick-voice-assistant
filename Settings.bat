@echo off
setlocal
cd /d "%~dp0Programma"

if not exist ".venv\Scripts\python.exe" (
    echo Avvia prima "Run Rick.bat" almeno una volta, poi riprova. / Run "Run Rick.bat" at least once first, then try again.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" settings.py
