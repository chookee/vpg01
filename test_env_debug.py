import os
from dotenv import dotenv_values

# Проверяем, что читается из .env
print("=== OS Environment Variables ===")
for key in ['GENAPI_KEY', 'LLM_PROVIDER', 'TELEGRAM_BOT_TOKEN']:
    val = os.environ.get(key, 'NOT SET')
    print(f"{key}: {val[:50]}..." if val != 'NOT SET' and len(val) > 50 else f"{key}: {val}")

print("\n=== Values from .env file ===")
env_values = dotenv_values('.env')
for key in ['GENAPI_KEY', 'LLM_PROVIDER', 'TELEGRAM_BOT_TOKEN']:
    val = env_values.get(key, 'NOT IN .env')
    print(f"{key}: {val[:50]}..." if val != 'NOT IN .env' and len(val) > 50 else f"{key}: {val}")
