<answer>
# Архитектурный документ (arch.md) – улучшенная версия

## 1. Обзор архитектуры

Приложение строится на принципах **чистой архитектуры (Clean Architecture)** с использованием **асинхронного программирования** (asyncio) для обеспечения неблокирующего взаимодействия с пользовательскими интерфейсами и внешними сервисами. Чёткое разделение на слои гарантирует независимость бизнес-логики от фреймворков, баз данных и LLM-провайдеров, упрощает тестирование и поддержку.

**Слои:**

- **Доменный слой (Domain)** – сущности бизнес-логики и интерфейсы (порты) для внешних зависимостей.
- **Слой приложения (Application)** – варианты использования (use cases), сервисы приложения (например, сборщик контекста), DTO.
- **Слой интерфейсов (Interfaces)** – адаптеры для Telegram-бота и десктопного приложения (PyQt).
- **Слой инфраструктуры (Infrastructure)** – реализации портов: репозитории базы данных, клиенты LLM, хранилище сессий, логгеры.

Все зависимости направлены внутрь. Для связывания используется **внедрение зависимостей (DI)**.

## 2. Компоненты и их зоны ответственности

### 2.1. Доменный слой (Domain)

**Сущности (Entities):**

- `User` – содержит `user_id` (уникальный идентификатор в рамках системы, например, Telegram ID или внутренний UUID), настройки по умолчанию.
- `Session` – диалоговая сессия: `session_id`, `user_id`, `memory_mode` (перечисление `MemoryMode`), время создания, время последней активности.
- `Message` – сообщение: `message_id`, `session_id`, `role` (user/assistant), `content`, `timestamp`, `model_used` (опционально), `memory_mode_at_time` (режим, действовавший при создании).

**Перечисления (Enums):**

- `MemoryMode` – `NO_MEMORY`, `SHORT_TERM`, `LONG_TERM`, `BOTH`.

**Интерфейсы (порты):**

- `MessageRepository` – асинхронные методы: `add`, `get_by_session`, `update`, `delete`, `delete_by_session`.
- `SessionRepository` – асинхронные методы: `create`, `get`, `update_mode`, `delete`.
- `LLMService` – асинхронный метод `generate(prompt: str, context: list[Message], model_params: dict) -> str`.
- `Logger` – абстракция для логирования (info, error, debug).

### 2.2. Слой приложения (Application)

**DTO (Data Transfer Objects):**

- `MessageDTO`, `SessionDTO`, `UserDTO` – для обмена данными между слоями.

**Сервисы приложения:**

- `ContextBuilder` – отвечает за сбор контекста в соответствии с режимом памяти и форматирование его для конкретной LLM. Использует стратегии форматирования (например, `PlainTextFormatter`, `ChatMLFormatter`), выбираемые на основе конфигурации модели.

**Варианты использования (Use Cases) – все асинхронные:**

- `ProcessMessage` – основной сценарий:
  1. Получает `user_id`, `session_id` (или создаёт новую сессию), текст сообщения, опциональный режим.
  2. Определяет действующий режим (из сессии или из аргумента).
  3. Через `ContextBuilder` собирает историю сообщений из соответствующих источников (in-memory store для краткосрочной, БД для долгосрочной) и форматирует их.
  4. Вызывает `LLMService.generate`.
  5. Сохраняет сообщения пользователя и ассистента в хранилища в зависимости от режима.
  6. Возвращает ответ.
- `ViewHistory` – возвращает историю сообщений сессии (объединяя из обоих хранилищ с сортировкой).
- `EditMessage` – изменяет текст сообщения в обоих хранилищах (если сообщение есть в краткосрочной памяти, обновляет и там).
- `DeleteHistory` – удаляет сообщения сессии из обоих хранилищ.
- `ExportHistory` – экспортирует историю в JSON/CSV.
- `ImportHistory` – импортирует историю (с проверкой целостности).

### 2.3. Слой инфраструктуры (Infrastructure)

**Реализации репозиториев:**

- `SQLiteMessageRepository` / `PostgreSQLMessageRepository` – асинхронные драйверы (aiosqlite, asyncpg).
- `RedisSessionStore` (опционально) – для краткосрочной памяти с автоматическим удалением по TTL; если Redis не используется, применяется `InMemorySessionStore` с ограничением по размеру.

**Реализации LLM-сервисов:**

- `OllamaService` – асинхронный HTTP-клиент (aiohttp) для общения с локальным сервером Ollama.
- `GenApiService` – асинхронный клиент для gen-api.ru (с обработкой rate limiting и повторными попытками).

**Конфигурация:**

- `Settings` (pydantic-settings) – загружает переменные из `.env`, проводит валидацию.

**Логирование:**

- `AsyncLogger` – реализация через стандартный `logging` с асинхронным обработчиком (или через очередь).

### 2.4. Слой интерфейсов (Interfaces)

**Telegram-бот (aiogram или python-telegram-bot с поддержкой asyncio):**

- `handlers/` – обработчики команд и сообщений, каждый вызывает соответствующий контроллер.
- `controllers/` – адаптеры, преобразующие входные данные в вызовы use cases и отправляющие ответы.
- `keyboards.py` – inline-клавиатуры для выбора режима, просмотра истории.

**Десктопное приложение (PyQt с асинхронными вызовами через QThreadPool или asyncio + qasync):**

- `main_window.py` – графический интерфейс.
- `controllers.py` – связывают сигналы UI с асинхронными use cases (через `QThread` или `async`-слоты с использованием `qasync`).
- `widgets/` – переиспользуемые компоненты (например, виджет истории с возможностью редактирования).

## 3. Потоки данных (с учётом асинхронности)

### 3.1. Обработка сообщения (ProcessMessage)

1. Интерфейс получает событие (сообщение от Telegram или действие в GUI).
2. Контроллер создаёт DTO и вызывает `ProcessMessage.execute(...)` (await).
3. **Use case**:
   - Получает сессию из `SessionRepository` или создаёт новую.
   - Определяет режим памяти.
   - Вызывает `ContextBuilder.build_context(session_id, mode)` – метод асинхронно получает сообщения из нужных хранилищ и форматирует их.
   - Вызывает `LLMService.generate` с промптом и контекстом.
   - Сохраняет сообщения (асинхронно) в `MessageRepository` и/или `SessionStore` (краткосрочное хранилище).
   - Возвращает ответ.
4. Контроллер отправляет ответ пользователю.

### 3.2. Редактирование сообщения

- `EditMessage.execute(message_id, new_text)`:
  - Обновляет сообщение в `MessageRepository`.
  - Если сессия активна в краткосрочном хранилище, обновляет сообщение и там (поиск по `message_id`).
- При успехе интерфейс может обновить отображение истории.

### 3.3. Обработка ошибок

- Все use cases оборачивают вызовы инфраструктуры в try-except, преобразуя исключения в доменные ошибки (например, `LLMServiceError`, `RepositoryError`).
- Интерфейсы ловят эти ошибки и показывают пользователю понятное сообщение (Telegram – текстом, PyQt – всплывающим окном).

## 4. Особенности

1. **Полная асинхронность** – все компоненты (репозитории, LLM-клиенты, use cases) работают асинхронно, что повышает отзывчивость интерфейсов и эффективно использует ресурсы.
2. **Выделенный сервис `ContextBuilder`** – инкапсулирует логику сборки контекста и его форматирования, упрощая тестирование и замену стратегий форматирования.
3. **Синхронизация краткосрочной и долгосрочной памяти** – при редактировании/удалении изменения применяются к обоим хранилищам, обеспечивая консистентность.
4. **Расширенная модель данных** – сообщения хранят метаинформацию (использованную модель, режим памяти), что позволяет анализировать качество ответов и воспроизводить диалоги.
5. **Экспорт/импорт истории** – добавлены use cases для резервного копирования и переноса данных.
6. **Улучшенная обработка ошибок и логирование** – введены доменные исключения, абстрактный логгер, что упрощает мониторинг и отладку.
7. **Гибкая конфигурация** – использование Pydantic Settings для валидации и типизации переменных окружения.
8. **Поддержка Redis для краткосрочной памяти** – опционально, позволяет масштабировать горизонтально и автоматически удалять устаревшие сессии.

## 5. Предлагаемая структура директорий

```
project/
├── .env.example
├── pyproject.toml / requirements.txt
├── README.md
├── docs/
│   └── arch.md
├── src/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── session.py
│   │   │   └── message.py
│   │   ├── enums.py
│   │   └── interfaces/
│   │       ├── __init__.py
│   │       ├── repositories.py
│   │       ├── llm_service.py
│   │       └── logger.py
│   ├── application/
│   │   ├── __init__.py
│   │   ├── dtos.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── context_builder.py
│   │   └── use_cases/
│   │       ├── __init__.py
│   │       ├── process_message.py
│   │       ├── view_history.py
│   │       ├── edit_message.py
│   │       ├── delete_history.py
│   │       ├── export_history.py
│   │       └── import_history.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── logging/
│   │   │   ├── __init__.py
│   │   │   └── async_logger.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── sqlite_message_repo.py
│   │   │   ├── postgres_message_repo.py
│   │   │   ├── redis_session_store.py
│   │   │   └── inmemory_session_store.py
│   │   └── llm/
│   │       ├── __init__.py
│   │       ├── base.py                 # базовый класс с общими методами
│   │       ├── ollama_service.py
│   │       └── genapi_service.py
│   └── interfaces/
│       ├── __init__.py
│       ├── telegram_bot/
│       │   ├── __init__.py
│       │   ├── bot.py
│       │   ├── handlers/
│       │   │   ├── __init__.py
│       │   │   ├── common.py
│       │   │   ├── messages.py
│       │   │   └── admin.py
│       │   ├── controllers/
│       │   │   ├── __init__.py
│       │   │   └── message_controller.py
│       │   └── keyboards.py
│       └── desktop_app/
│           ├── __init__.py
│           ├── main.py
│           ├── main_window.py
│           ├── controllers.py
│           ├── widgets/
│           │   ├── __init__.py
│           │   ├── history_widget.py
│           │   └── settings_widget.py
│           └── resources/                # иконки, стили
└── tests/
    ├── unit/
    │   ├── test_domain.py
    │   ├── test_use_cases.py
    │   └── test_context_builder.py
    ├── integration/
    │   ├── test_repositories.py
    │   ├── test_llm_services.py
    │   └── test_telegram_bot_integration.py
    └── e2e/
        ├── test_full_scenario.py
        └── test_desktop_app.py
```

## 6. Соответствие требованиям

- [x] Четыре режима памяти: реализованы через `MemoryMode` и логику `ContextBuilder`.
- [x] Краткосрочная память: in-memory store (или Redis) с TTL.
- [x] Долгосрочная память: SQLite/PostgreSQL с полной историей.
- [x] Интерфейсы: Telegram-бот (асинхронный) и PyQt-приложение (с асинхронными вызовами).
- [x] Возможность просмотра, редактирования, удаления истории.
- [x] Поддержка локальных (Ollama) и облачных (gen-api.ru) моделей.
- [x] Чистая архитектура со строгой типизацией и DI.
- [x] Модульность, тестируемость, документирование.


### 7. ER-диаграмма базы данных

**Таблицы и связи**

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     users       │       │    sessions     │       │    messages     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ user_id (PK)    │───────│ user_id (FK)    │       │ message_id (PK) │
│ telegram_id     │  1:N  │ session_id (PK) │───────│ session_id (FK) │
│ default_mode    │       │ memory_mode     │  1:N  │ role            │
│ created_at      │       │ created_at      │       │ content         │
└─────────────────┘       │ last_activity   │       │ timestamp       │
                           └─────────────────┘       │ model_used      │
                                                      │ memory_mode_at  │
                                                      └─────────────────┘
```

#### **Описание полей**

**Таблица `users`**
- `user_id` – INTEGER, PRIMARY KEY, автоинкремент
- `telegram_id` – INTEGER, UNIQUE NOT NULL (идентификатор пользователя в Telegram)
- `default_mode` – TEXT, NOT NULL (значение из перечисления `MemoryMode`: `no_memory`, `short_term`, `long_term`, `both`)
- `created_at` – TIMESTAMP, DEFAULT CURRENT_TIMESTAMP

**Таблица `sessions`**
- `session_id` – INTEGER, PRIMARY KEY, автоинкремент
- `user_id` – INTEGER, FOREIGN KEY REFERENCES `users(user_id)` ON DELETE CASCADE
- `memory_mode` – TEXT, NOT NULL (текущий режим сессии)
- `created_at` – TIMESTAMP, DEFAULT CURRENT_TIMESTAMP
- `last_activity` – TIMESTAMP, DEFAULT CURRENT_TIMESTAMP (обновляется при каждом сообщении)

**Таблица `messages`**
- `message_id` – INTEGER, PRIMARY KEY, автоинкремент
- `session_id` – INTEGER, FOREIGN KEY REFERENCES `sessions(session_id)` ON DELETE CASCADE
- `role` – TEXT, NOT NULL (`user` или `assistant`)
- `content` – TEXT, NOT NULL
- `timestamp` – TIMESTAMP, DEFAULT CURRENT_TIMESTAMP
- `model_used` – TEXT (опционально, какая модель сгенерировала ответ)
- `memory_mode_at_time` – TEXT (значение `MemoryMode` на момент отправки сообщения)

#### **Индексы**
- Индекс на `users.telegram_id` для быстрого поиска.
- Индекс на `sessions.user_id` и `sessions.last_activity` для фильтрации активных сессий.
- Индекс на `messages.session_id` и `messages.timestamp` для выборки истории.

---

### 8. Диаграммы последовательности для ключевых сценариев

#### **Сценарий 1: Обработка входящего сообщения**

```
User -> TelegramBot: /start или текст сообщения
TelegramBot -> MessageController: handle_message(update)
MessageController -> UserRepository: get_or_create_user(telegram_id)
UserRepository --> MessageController: user
MessageController -> SessionRepository: get_or_create_session(user_id)
SessionRepository --> MessageController: session
MessageController -> ProcessMessageUseCase: execute(session, text, mode)
    ProcessMessageUseCase -> ContextBuilder: build_context(session_id, mode)
        ContextBuilder -> MessageRepository: get_messages(session_id) [если режим LONG_TERM/BOTH]
        ContextBuilder -> InMemoryStore: get_messages(session_id) [если режим SHORT_TERM/BOTH]
        MessageRepository --> ContextBuilder: long_term_msgs
        InMemoryStore --> ContextBuilder: short_term_msgs
        ContextBuilder --> ProcessMessageUseCase: combined context
    ProcessMessageUseCase -> LLMService: generate(prompt, context)
        LLMService --> ProcessMessageUseCase: response_text
    ProcessMessageUseCase -> MessageRepository: add(user_message, assistant_message)
    ProcessMessageUseCase -> InMemoryStore: add(user_message, assistant_message) [если режим SHORT_TERM/BOTH]
    ProcessMessageUseCase --> MessageController: response_text
MessageController --> TelegramBot: send_message(response_text)
TelegramBot -> User: ответ
```

#### **Сценарий 2: Смена режима памяти**

```
User -> TelegramBot: /mode long
TelegramBot -> ModeController: change_mode(chat_id, new_mode)
ModeController -> SessionRepository: get_current_session(user_id)
SessionRepository --> ModeController: session
ModeController -> SessionRepository: update_mode(session_id, new_mode)
SessionRepository --> ModeController: success
ModeController --> TelegramBot: "Режим изменен на долгосрочный"
TelegramBot -> User: "Режим изменен на долгосрочный"
```

#### **Сценарий 3: Редактирование сообщения**

```
User -> TelegramBot: /edit 42 "Новый текст"
TelegramBot -> EditController: edit_message(chat_id, message_id, new_text)
EditController -> EditMessageUseCase: execute(message_id, new_text)
    EditMessageUseCase -> MessageRepository: update(message_id, new_text)
    EditMessageUseCase -> InMemoryStore: update(message_id, new_text) [если сообщение в активной сессии]
    MessageRepository --> EditMessageUseCase: success
    InMemoryStore --> EditMessageUseCase: success (если применимо)
    EditMessageUseCase --> EditController: success
EditController --> TelegramBot: "Сообщение обновлено"
TelegramBot -> User: "Сообщение обновлено"
```

---

### 9. Стандарты кодирования

#### **Инструменты форматирования и линтинга**

- **Black** – основной форматтер кода.  
  Конфигурация: длина строки 88 символов (по умолчанию).  
  Запуск: `black src/ tests/`

- **isort** – сортировка импортов.  
  Конфигурация: совместимость с Black (профиль `black`).  
  Пример `.isort.cfg`:
  ```ini
  [settings]
  profile = black
  line_length = 88
  ```
  Запуск: `isort src/ tests/`

- **flake8** – линтер для проверки стиля.  
  Игнорируемые ошибки:  
  - `E501` (line too long) – обрабатывается Black.  
  - `W503` (line break before binary operator) – конфликтует с Black.  
  Пример `.flake8`:
  ```ini
  [flake8]
  max-line-length = 88
  extend-ignore = E501, W503
  exclude = .git,__pycache__,build,dist
  ```

- **mypy** – статическая проверка типов.  
  Конфигурация: строгий режим, проверка всех модулей.  
  Пример `mypy.ini`:
  ```ini
  [mypy]
  python_version = 3.10
  warn_return_any = True
  warn_unused_configs = True
  ignore_missing_imports = True
  disallow_untyped_defs = True
  ```

#### **Pre-commit хуки**

Файл `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.10

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        additional_dependencies: [flake8-bugbear]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports]
```

#### **Соглашения по именованию**

- **Классы**: `CamelCase` (например, `ProcessMessageUseCase`).
- **Функции и методы**: `snake_case` (например, `get_user_by_id`).
- **Переменные**: `snake_case`.
- **Константы**: `UPPER_SNAKE_CASE`.
- **Приватные атрибуты/методы**: с префиксом `_` (например, `_internal_helper`).

#### **Документирование**

- **Docstrings** для всех публичных классов, методов и функций в формате Google или Sphinx.  
  Пример:
  ```python
  def process_message(user_id: int, text: str) -> str:
      """Обрабатывает сообщение пользователя и возвращает ответ.

      Args:
          user_id: Идентификатор пользователя.
          text: Текст сообщения.

      Returns:
          Ответ от ассистента.
      """
  ```
