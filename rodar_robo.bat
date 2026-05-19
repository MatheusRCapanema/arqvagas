@echo off
echo Iniciando o Buscador de Vagas...
call .\.venv\Scripts\activate.bat
python scraper.py
pause
