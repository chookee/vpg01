# VPg01 — Smart LLM Chat Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Асинхронный чат-ассистент с поддержкой **локальных (Ollama)** и **облачных (gen-api.ru)** LLM-моделей, четырьмя режимами памяти и двумя интерфейсами: **Telegram-бот** и **PyQt-приложение**.

---

## 🚀 Возможности

| Функция | Описание |
|---------|----------|
| **4 режима памяти** | `NO_MEMORY`, `SHORT_TERM`, `LONG_TERM`, `BOTH` |
| **Краткосрочная память** | In-memory хранилище с ограничением по размеру (или Redis с TTL) |
| **Долгосрочная память** | SQLite/PostgreSQL с полной историей диалогов |
| **LLM-провайдеры** | Ollama (локально), gen-api.ru (облако) |
| **Telegram-бот** | Команды: `/start`, `/mode`, `/history`, `/edit`, `/delete` |
| **Десктопное приложение** | PyQt5 интерфейс с виджетом истории и контекстным меню |
| **Экспорт/импорт** | Резервное копирование истории в JSON |
| **Чистая архитектура** | Domain → Application → Infrastructure → Interfaces |

---

## 📦 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/chookee/vpg01.git
cd vpg01
```

### 2. Создание виртуального окружения

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```ini
# Общие настройки
APP_NAME=VPg01
DEBUG=true

# База данных
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# LLM настройки
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Telegram Bot (получить у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 5. Запуск приложения

```bash
python -m src.main
```

**Ожидаемый вывод:**
```
2026-03-15 12:00:00 | INFO     | app:main:19 | Hello, World!
2026-03-15 12:00:00 | INFO     | app:main:20 | Application: VPg01
2026-03-15 12:00:00 | DEBUG    | app:main:21 | Debug mode: True
2026-03-15 12:00:00 | INFO     | app:main:22 | LLM Provider: ollama
```

---

## 🏗️ Архитектура

Проект следует принципам **Clean Architecture** с асинхронной обработкой данных.

```
┌─────────────────────────────────────────────────────────┐
│                     INTERFACES                          │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │   Telegram Bot      │  │   Desktop App (PyQt)    │  │
│  │   (aiogram)         │  │   (qasync)              │  │
│  └─────────────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                   APPLICATION LAYER                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Use Cases    │  │ Context      │  │ DTOs         │  │
│  │ ProcessMsg   │  │ Builder      │  │ MessageDTO   │  │
│  │ ViewHistory  │  │              │  │ SessionDTO   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     DOMAIN LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Entities     │  │ Interfaces   │  │ Enums        │  │
│  │ User         │  │ MessageRepo  │  │ MemoryMode   │  │
│  │ Session      │  │ SessionRepo  │  │              │  │
│  │ Message      │  │ LLMService   │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  INFRASTRUCTURE LAYER                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ SQLite Repo  │  │ Ollama       │  │ Config       │  │
│  │ PostgreSQL   │  │ GenApi       │  │ Logging      │  │
│  │ In-Memory    │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Слои

| Слой | Ответственность |
|------|-----------------|
| **Domain** | Сущности (User, Session, Message), интерфейсы (порты) |
| **Application** | Use Cases, сервисы (ContextBuilder), DTO |
| **Infrastructure** | Реализации репозиториев, LLM-клиенты, конфиг |
| **Interfaces** | Telegram-бот (aiogram), Desktop (PyQt5) |

---

## 📊 Режимы памяти

| Режим | Описание | Хранение |
|-------|----------|----------|
| `NO_MEMORY` | Без сохранения контекста | — |
| `SHORT_TERM` | Только активная сессия | In-memory |
| `LONG_TERM` | Полная история | SQLite/PostgreSQL |
| `BOTH` | Активная сессия + история | In-memory + БД |

---

## 🛠️ Разработка

### Запуск тестов

```bash
pytest tests/ -v
```

### Проверка типов

```bash
mypy src/ --strict --ignore-missing-imports
```

### Форматирование кода

```bash
black src/ tests/
isort src/ tests/ --profile black
flake8 src/ tests/
```

### Структура проекта

```
project/
├── .env.example          # Шаблон переменных окружения
├── .gitignore            # Git ignore rules
├── README.md             # Этот файл
├── requirements.txt      # Python зависимости
├── doc/
│   ├── arch.md           # Архитектурный документ
│   └── plan.md           # План разработки (32 milestones)
├── src/
│   ├── __init__.py
│   ├── main.py           # Точка входа
│   ├── domain/           # Доменный слой
│   │   ├── entities/     # User, Session, Message
│   │   ├── enums.py      # MemoryMode
│   │   └── interfaces/   # Порты (репозитории, LLM)
│   ├── application/      # Слой приложения
│   │   ├── dtos.py       # DTO
│   │   ├── services/     # ContextBuilder
│   │   └── use_cases/    # ProcessMessage, ViewHistory...
│   └── infrastructure/   # Инфраструктура
│       ├── config.py     # Настройки (pydantic)
│       ├── logging/      # Логгер
│       ├── repositories/ # SQLite, PostgreSQL, In-Memory
│       └── llm/          # Ollama, GenApi
└── tests/
    ├── unit/             # Unit-тесты
    ├── integration/      # Интеграционные тесты
    └── e2e/              # E2E тесты
```

---

## 📈 План разработки

Проект разбит на **32 этапа** (milestones). Текущий статус:

| Этап | Описание | Статус |
|------|----------|--------|
| **Milestone 1** | Базовый скелет проекта | ✅ |
| **Milestone 2** | Доменные сущности и перечисления | ✅ |
| **Milestone 3** | Интерфейсы (порты) домена | 🔄 В работе |
| **Milestone 4-32** | Репозитории, Use Cases, интерфейсы | ⏳ Ожидает |

Полный план доступен в [doc/plan.md](doc/plan.md).

---

## 🔐 Безопасность

- **Секреты:** Токены и ключи хранятся в `.env` (не коммитить!)
- **Валидация:** Все входные данные валидируются через Pydantic
- **SQL Injection:** Используются параметризованные запросы (aiosqlite, asyncpg)

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE) файл.

---

## 🤝 Контрибьюция

1. Fork репозиторий
2. Создайте ветку (`git checkout -b feature/amazing-feature`)
3. Commit изменений (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## 📞 Контакты

- **GitHub:** [@chookee](https://github.com/chookee)
- **Issues:** [GitHub Issues](https://github.com/chookee/vpg01/issues)
