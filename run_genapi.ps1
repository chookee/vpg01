# Запуск VPg01 Desktop с GenAPI
# Явная установка переменных окружения для текущей сессии

$env:GENAPI_KEY = "sk-hkVE5hQVWZ07ZX4j0oQhC1nyso2SsuWNNY7IWqdlXqlTz4Xrtp7jwDLRFhOx"
$env:LLM_PROVIDER = "genapi"

Write-Host "Starting VPg01 Desktop with GenAPI..." -ForegroundColor Green
Write-Host "GENAPI_KEY: configured" -ForegroundColor Cyan
Write-Host "LLM_PROVIDER: genapi" -ForegroundColor Cyan
Write-Host ""

python -m src.main --desktop
