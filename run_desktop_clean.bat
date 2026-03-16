@echo off
REM Очистка переменных окружения и запуск приложения
set GENAPI_KEY=
set LLM_PROVIDER=
set TELEGRAM_BOT_TOKEN=

REM Запуск приложения
python -m src.main --desktop
