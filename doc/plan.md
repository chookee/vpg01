## Общие принципы

- Все этапы реализуются последовательно.
- После каждого этапа код должен оставаться работоспособным (запускаться без ошибок).
- Каждый этап добавляет не более 150 строк нового кода (суммарно изменений).
- Используется строгая типизация (PEP 484).
- Тесты пишутся сразу после реализации функциональности (unit/integration).

---

### **Milestone 1: Базовый скелет проекта**

**Описание:** Создание структуры директорий, настройка виртуального окружения, базового файла конфигурации `.env`, логирования и точки входа (CLI-заглушки).

**Файлы:**
- `.env.example` – шаблон переменных окружения.
- `pyproject.toml` / `requirements.txt` – зависимости (asyncio, python-dotenv, loguru).
- `src/__init__.py`
- `src/main.py` – точка входа (выводит "Hello, World!" и загружает конфиг).
- `src/infrastructure/config.py` – загрузка и валидация переменных через pydantic-settings.
- `src/infrastructure/logging/__init__.py` – настройка логгера (заглушка).
- `tests/__init__.py`

**Критерий готовности:**
- Запуск `python -m src.main` выводит "Hello, World!".
- Переменные из `.env` загружаются и логируются.
- Логгер пишет в консоль.

---

### **Milestone 2: Доменные сущности и перечисления**

**Описание:** Создание базовых сущностей домена (User, Session, Message) и перечисления MemoryMode.

**Файлы:**
- `src/domain/enums.py` – `MemoryMode` (IntEnum).
- `src/domain/entities/user.py` – класс User (dataclass): `user_id`, `telegram_id` (опционально), `default_mode`.
- `src/domain/entities/session.py` – класс Session (dataclass): `session_id`, `user_id`, `memory_mode`, `created_at`, `last_activity`.
- `src/domain/entities/message.py` – класс Message (dataclass): `message_id`, `session_id`, `role`, `content`, `timestamp`, `model_used`, `memory_mode_at_time`.

**Критерий готовности:**
- Написаны простые тесты в `tests/unit/test_domain.py`, проверяющие создание объектов.
- Импорты работают.

---

### **Milestone 3: Интерфейсы (порты) домена**

**Описание:** Определение абстрактных базовых классов для репозиториев, LLM-сервиса и логгера. Добавлен порт для UserRepository.

**Файлы:**
- `src/domain/interfaces/repositories.py` – ABC: `MessageRepository`, `SessionRepository`, `UserRepository` (асинхронные методы).
- `src/domain/interfaces/llm_service.py` – ABC: `LLMService` с методом `generate`.
- `src/domain/interfaces/logger.py` – ABC: `Logger` (info, error, debug).

**Критерий готовности:**
- Все абстрактные классы корректно определены.
- Модули импортируются.

---

### **Milestone 4: Настройка тестовой инфраструктуры**

**Описание:** Конфигурация pytest, создание фикстур для временной БД и моков.

**Файлы:**
- `tests/conftest.py` – фикстуры: `temp_db` (создание и удаление тестовой БД), `message_repo`, `session_repo`, `user_repo` (моки или реальные репозитории).
- `pytest.ini` (опционально).

**Критерий готовности:**
- `pytest` находит и выполняет тесты (хотя бы один пустой тест проходит).

---

### **Milestone 5: Инфраструктура – настройка базы данных (SQLite)**

**Описание:** Реализация подключения к SQLite, создание таблиц через миграции (простой скрипт инициализации).

**Файлы:**
- `src/infrastructure/database/__init__.py`
- `src/infrastructure/database/connection.py` – асинхронное подключение через aiosqlite, функция `get_db`.
- `src/infrastructure/database/schema.py` – SQL для создания таблиц users, sessions, messages.
- `scripts/init_db.py` – скрипт для инициализации БД (создание таблиц).

**Критерий готовности:**
- Запуск `python scripts/init_db.py` создаёт файл БД с нужными таблицами.
- В тестах можно получить подключение и выполнить простой запрос.

---

### **Milestone 6: Репозиторий сообщений (SQLite)**

**Описание:** Реализация `SQLiteMessageRepository`, реализующего порт `MessageRepository`. Методы: `add`, `get_by_session`.

**Файлы:**
- `src/infrastructure/repositories/sqlite_message_repo.py`
- `tests/integration/test_sqlite_message_repo.py` – интеграционные тесты.

**Критерий готовности:**
- Тесты проходят: можно добавить сообщение и получить его по сессии.

---

### **Milestone 7: Репозиторий сессий (SQLite)**

**Описание:** Реализация `SQLiteSessionRepository` с методами `create`, `get`, `update_mode`.

**Файлы:**
- `src/infrastructure/repositories/sqlite_session_repo.py`
- `tests/integration/test_sqlite_session_repo.py`

**Критерий готовности:**
- Тесты на создание, получение и обновление сессии проходят.

---

### **Milestone 8: Репозиторий пользователей (SQLite)**

**Описание:** Реализация `SQLiteUserRepository` с методами `create`, `get_by_telegram_id` (или `get_by_id`).

**Файлы:**
- `src/infrastructure/repositories/sqlite_user_repo.py`
- `tests/integration/test_sqlite_user_repo.py`

**Критерий готовности:**
- Тесты на создание и получение пользователя проходят.

---

### **Milestone 9: Хранилище краткосрочной памяти (in-memory)**

**Описание:** Реализация `InMemorySessionStore` для хранения активных сессий и их сообщений (dict + asyncio.Lock).

**Файлы:**
- `src/infrastructure/repositories/inmemory_session_store.py` – класс с методами: `add_message`, `get_messages`, `clear_session`.
- `tests/unit/test_inmemory_store.py`

**Критерий готовности:**
- Методы корректно сохраняют и возвращают сообщения; тесты проходят.

---

### **Milestone 10: Клиент Ollama (заглушка)**

**Описание:** Базовая реализация `OllamaService`, возвращающая фиктивный ответ.

**Файлы:**
- `src/infrastructure/llm/ollama_service.py` – метод `generate` возвращает `"Echo: {prompt}"`.
- `tests/unit/test_ollama_service.py`

**Критерий готовности:**
- Сервис возвращает предсказуемую строку.

---

### **Milestone 11: DTO и сервис ContextBuilder (базовый)**

**Описание:** Создание DTO для сообщений и сессий, реализация `ContextBuilder` с поддержкой режимов (возвращает список сообщений).

**Файлы:**
- `src/application/dtos.py` – `MessageDTO`, `SessionDTO` (можно использовать те же dataclasses).
- `src/application/services/context_builder.py` – класс с методом `build_context(session_id, mode, long_term_repo, short_term_store)`, возвращающий список Message объектов.
- `tests/unit/test_context_builder.py` – мокаем репозитории.

**Критерий готовности:**
- Для каждого режима возвращается правильный набор сообщений.

---

### **Milestone 12: Use Case ProcessMessage (базовый)**

**Описание:** Реализация `ProcessMessage` с минимальной логикой: получает сообщение, собирает контекст через `ContextBuilder`, вызывает LLM-заглушку, сохраняет сообщения в долгосрочный репозиторий.

**Файлы:**
- `src/application/use_cases/process_message.py` – класс `ProcessMessage` с методом `execute`.
- `tests/unit/test_process_message.py` – моки всех зависимостей.

**Критерий готовности:**
- Use case корректно вызывает зависимости и возвращает ответ; тесты проходят.

---

### **Milestone 13: ProcessMessage с сохранением в краткосрочное хранилище**

**Описание:** Доработка `ProcessMessage` для сохранения сообщений также в краткосрочное хранилище, если режим включает `SHORT_TERM` или `BOTH`.

**Файлы:**
- Изменения в `process_message.py`.
- Тесты обновлены.

**Критерий готовности:**
- При режиме `SHORT_TERM` сообщения сохраняются in-memory и извлекаются при следующем запросе.

---

### **Milestone 14: Use Case ViewHistory**

**Описание:** Реализация `ViewHistory` – получение истории сессии из обоих хранилищ (объединение и сортировка).

**Файлы:**
- `src/application/use_cases/view_history.py`
- `tests/unit/test_view_history.py`

**Критерий готовности:**
- Возвращает корректный список сообщений.

---

### **Milestone 15: Use Case EditMessage**

**Описание:** Реализация `EditMessage` – изменение текста сообщения в обоих хранилищах.

**Файлы:**
- `src/application/use_cases/edit_message.py`
- `tests/unit/test_edit_message.py`

**Критерий готовности:**
- Сообщение обновляется в БД и in-memory (если присутствует).

---

### **Milestone 16: Use Case DeleteMessage**

**Описание:** Реализация `DeleteMessage` – удаление сообщения (или нескольких) из обоих хранилищ.

**Файлы:**
- `src/application/use_cases/delete_message.py`
- `tests/unit/test_delete_message.py`

**Критерий готовности:**
- Сообщение удаляется из БД и in-memory.

---

### **Milestone 17: Обработка ошибок и доменные исключения**

**Описание:** Введение классов исключений (например, `MessageNotFoundError`, `SessionNotFoundError`). Обёртка вызовов репозиториев и LLM в use cases с преобразованием в доменные ошибки.

**Файлы:**
- `src/domain/exceptions.py` – базовые исключения.
- Обновление use cases (добавление try/except, поднятие доменных исключений).
- Обновление тестов для проверки ошибок.

**Критерий готовности:**
- Use cases корректно обрабатывают ситуации отсутствия данных и выбрасывают специфичные исключения.

---

### **Milestone 18: Абстрактная фабрика репозиториев**

**Описание:** Создание фабрики, которая по типу БД (из конфига) возвращает нужные репозитории. Реализация для SQLite.

**Файлы:**
- `src/infrastructure/repositories/factory.py` – класс `RepositoryFactory` с методами `create_message_repo`, `create_session_repo`, `create_user_repo`.
- Конфигурация: добавление переменной `DATABASE_TYPE` в `.env`.
- Тесты фабрики.

**Критерий готовности:**
- Фабрика возвращает экземпляры SQLite-репозиториев.

**Примечание (Stages 12-16):**
- Репозитории уже поддерживают опциональное внешнее подключение (`connection` параметр).
- `UnitOfWork` имеет методы `create_*_repo()` для создания репозиториев в транзакции.
- Полная интеграция с фабрикой и DI будет выполнена на этом этапе.

---

### **Milestone 19: Настройка DI-контейнера / фабрики зависимостей**

**Описание:** Создание функции или класса для сборки всех зависимостей приложения (use cases, сервисы, репозитории) на основе конфигурации.

**Файлы:**
- `src/main.py` – функция `build_app` или `create_application`, которая инициализирует:
  - репозитории через фабрику,
  - in-memory store,
  - LLM-сервис (пока заглушку),
  - use cases,
  - логгер.
- Передача зависимостей в use cases через конструктор.

**Критерий готовности:**
- Вызов `build_app()` возвращает объект с полями `process_message`, `view_history` и т.д., готовыми к использованию.

**Примечание (Stages 12-16):**
- Use cases сейчас работают с репозиториями напрямую (без UnitOfWork).
- Для транзакционных операций контроллеры должны использовать `UnitOfWork` явно.
- На этом этапе будет добавлена автоматическая инъекция зависимостей и интеграция с UnitOfWork.

**TODO: Интеграция с UnitOfWork**
```python
# Пример использования в контроллере (этап 20-21)
async with UnitOfWork(settings.db_path).transaction() as uow:
    msg_repo = uow.create_message_repo()
    sess_repo = uow.create_session_repo()
    process_message = ProcessMessage(msg_repo, sess_repo, ...)
    result = await process_message.execute(...)
# Автоматический коммит
```

---

### **Milestone 20: Интерфейс – Telegram-бот (базовый эхо)**

**Описание:** Создание минимального Telegram-бота с помощью `aiogram`, обрабатывающего команду `/start` и текстовые сообщения (эхо).

**Файлы:**
- `src/interfaces/telegram_bot/bot.py` – инициализация бота, запуск polling.
- `src/interfaces/telegram_bot/handlers/common.py` – `/start`.
- `src/interfaces/telegram_bot/handlers/messages.py` – обработчик текстовых сообщений (эхо).
- Настройка `.env` с токеном бота.

**Критерий готовности:**
- Бот отвечает на сообщения пользователя "Вы сказали: {text}".

---

### **Milestone 21: Telegram-бот – интеграция с ProcessMessage**

**Описание:** Подключение use case `ProcessMessage` в обработчике сообщений. Создание контроллера.

**Файлы:**
- `src/interfaces/telegram_bot/controllers/message_controller.py` – функция, принимающая `telegram_id`, текст, вызывает use case.
- Изменение обработчика для вызова контроллера.
- Использование `UserRepository` для получения/создания пользователя по `telegram_id`.
- Использование `SessionRepository` для получения/создания сессии.

**Критерий готовности:**
- Бот отвечает через заглушку LLM, сохраняет сообщения в БД (если режим долгосрочной).

---

### **Milestone 22: Telegram-бот – команды выбора режима**

**Описание:** Добавление команд `/mode no_memory`, `/mode short`, `/mode long`, `/mode both`. Обновление режима сессии.

**Файлы:**
- `src/interfaces/telegram_bot/handlers/mode.py` – обработчики.
- Обновление `controllers` для передачи режима в use case.
- Возможно, inline-клавиатура.

**Критерий готовности:**
- После команды режим меняется, и последующие сообщения обрабатываются согласно выбранному режиму.

---

### **Milestone 23: Telegram-бот – просмотр истории**

**Описание:** Команда `/history` – выводит последние N сообщений сессии, используя `ViewHistory`.

**Файлы:**
- `src/interfaces/telegram_bot/handlers/history.py`
- Контроллер вызывает `ViewHistory` и форматирует ответ.

**Критерий готовности:**
- При вводе `/history` пользователь получает форматированный список сообщений.

---

### **Milestone 24: Telegram-бот – редактирование и удаление**

**Описание:** Команды `/edit <message_id> <new_text>` и `/delete <message_id>`. Используют `EditMessage` и `DeleteMessage`.

**Файлы:**
- `src/interfaces/telegram_bot/handlers/edit.py`
- `src/interfaces/telegram_bot/handlers/delete.py`
- Контроллеры.

**Критерий готовности:**
- Сообщение можно изменить или удалить; изменения отражаются в истории.

---

### **Milestone 25: Десктопное приложение – базовое окно**

**Описание:** Создание минимального окна PyQt с использованием `qasync`. Окно содержит поле ввода и кнопку "Отправить", которая пока выводит текст в консоль.

**Файлы:**
- `src/interfaces/desktop_app/main.py` – запуск приложения.
- `src/interfaces/desktop_app/main_window.py` – класс главного окна.
- Добавление `qasync` в зависимости.

**Критерий готовности:**
- Приложение запускается, окно отображается, кнопка реагирует на нажатие.

---

### **Milestone 26: Десктоп – интеграция с ProcessMessage**

**Описание:** Подключение use case `ProcessMessage` к кнопке отправки. Использование контроллера и асинхронного вызова.

**Файлы:**
- `src/interfaces/desktop_app/controllers.py` – контроллер, вызывающий use case через `async`-слот.
- Обновление `main_window.py` для отображения ответа.

**Критерий готовности:**
- При нажатии кнопки отправляется сообщение, ответ отображается в окне.

---

### **Milestone 27: Десктоп – выбор режима и отображение истории**

**Описание:** Добавление выпадающего списка для выбора режима памяти, виджета для отображения истории. Подключение `ViewHistory` для загрузки истории при старте.

**Файлы:**
- `src/interfaces/desktop_app/widgets/history_widget.py` – кастомный виджет.
- Обновление `main_window.py`.

**Критерий готовности:**
- При запуске загружается история текущей сессии; режим можно переключить, и он влияет на последующие сообщения.

---

### **Milestone 28: Десктоп – редактирование и удаление**

**Описание:** Реализация контекстного меню для сообщений в истории (редактировать, удалить). Подключение `EditMessage` и `DeleteMessage`.

**Файлы:**
- Обновление `history_widget.py` – добавление сигналов и контекстного меню.
- Контроллеры.

**Критерий готовности:**
- Правый клик на сообщении позволяет его отредактировать или удалить; изменения синхронизируются с БД.

---

### **Milestone 29: Поддержка реальных LLM (Ollama и gen-api.ru)**

**Описание:** Замена заглушек на реальные HTTP-клиенты (aiohttp) для Ollama и gen-api.ru. Выбор провайдера через конфиг.

**Файлы:**
- `src/infrastructure/llm/ollama_service.py` – реальная реализация.
- `src/infrastructure/llm/genapi_service.py` – аналогично.
- Обновление `config.py` – параметры для выбора провайдера.
- Фабрика LLM-сервиса в DI.

**Критерий готовности:**
- При установленных переменных окружения бот/приложение обращаются к реальной модели и получают ответы.

---

### **Milestone 30: Обработка ошибок сети и повторные попытки для LLM-клиентов**

**Описание:** Добавление retry-логики, таймаутов и обработки специфических ошибок (например, превышение лимитов).

**Файлы:**
- Обновление `ollama_service.py` и `genapi_service.py` – обёртка с `tenacity` или ручной retry.
- Тесты на ошибки.

**Критерий готовности:**
- При временных сбоях клиент делает несколько попыток; при фатальных ошибках выбрасывает доменное исключение.

---

### **Milestone 31: Экспорт/импорт истории**

**Описание:** Реализация use cases `ExportHistory` и `ImportHistory`. Добавление команд в Telegram и пунктов меню в десктопном приложении.

**Файлы:**
- `src/application/use_cases/export_history.py`
- `src/application/use_cases/import_history.py`
- Тесты.
- Интерфейсные дополнения.

**Критерий готовности:**
- Можно выгрузить историю в JSON, загрузить обратно с проверкой целостности.

---

### **Milestone 32: Финальное тестирование и документация**

**Описание:** Написание недостающих тестов, интеграционных и E2E. Документирование кода (docstrings), обновление README.

**Файлы:**
- `tests/e2e/test_full_scenario.py` – сквозной тест (возможно, с использованием Docker).
- Доработка `README.md` с инструкциями.
- Проверка всех модулей на соответствие PEP 484.

**Критерий готовности:**
- Все тесты проходят.
- Документация описывает, как запустить проект в разных режимах.

