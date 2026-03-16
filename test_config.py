from src.infrastructure.config import get_settings

s = get_settings()
print(f'LLM Provider: {s.llm_provider}')
print(f'GenAPI Model: {s.genapi_model}')
print(f'GenAPI Key: {s.genapi_key}')
print(f'GenAPI configured: {s.is_genapi_configured()}')
