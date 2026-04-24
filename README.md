# multi-vpn-bot

Каркас модульного Telegram-бота для управления VPN-серверами, провайдерами, клиентскими конфигами и статистикой трафика.

Текущее состояние:

- реализованы этапы 0-13 из `docs/IMPLEMENTATION_TASKS.md` в базовом виде;
- этап 14 начат: добавлен executor-backed `WireGuardProvider` для healthcheck,
  списка peers, peer stats, экспорта клиентского `.conf`, создания и удаления peers;
- собран базовый каркас проекта;
- добавлены строгие pydantic-модели JSON-конфига;
- добавлены базовое логирование и безопасный bootstrap;
- подключена SQLite через `SQLAlchemy` и подготовлены стартовые репозитории;
- подключён `aiogram` runtime, inline-меню, роли, авто-регистрация пользователей
  и пересылка сообщений администраторам;
- добавлены `ServerRegistry`, executor layer, host actions и админский Telegram UI
  для просмотра серверов и запуска системных действий;
- добавлены provider base layer, unified client inventory и traffic statistics layer
  с raw samples, delta calculation и daily aggregates.

## Быстрый старт

1. Создать виртуальное окружение и установить зависимости:

```bash
pip install -e .[dev]
```

2. Скопировать пример конфига и заполнить секреты:

```bash
cp configs/config.example.json configs/config.json
```

3. Провалидировать конфиг и инициализировать БД:

```bash
python -m app.main --config configs/config.json --validate-config
python -m app.main --config configs/config.json
```

## Что уже есть

- `app/core/config`: модели и загрузка конфига;
- `app/infrastructure/logging`: логирование в консоль, application log и audit log;
- `app/infrastructure/db`: async SQLite engine, ORM-модели и стартовые repositories;
- `app/core/registry`: базовый `ServerRegistry` поверх enabled-серверов;
- `app/core/executors`: единый local/SSH executor contract;
- `app/services/host_actions`: запуск системных действий независимо от провайдеров;
- `app/services/client_inventory`: единый реестр VPN-клиентов и связи с Telegram users;
- `app/services/traffic_stats`: нормализация статистики, raw samples,
  delta calculation и дневные агрегаты;
- `app/providers`: базовый provider contract, capabilities, factory, registry
  и первый WireGuard provider slice;
- `app/bot`: aiogram runtime, inline navigation, admin user management,
  message bridge и server UI;
- `app/main.py`: bootstrap конфига, логирования, БД, registry и Telegram runtime.

## Стиль миграций

На текущем этапе схема создаётся через `SQLAlchemy.metadata.create_all()` при старте. Это даёт быстрый старт для пустого проекта. Для последующих изменений схемы рекомендуется перейти на явные миграции через Alembic, не ломая уже подготовленный ORM-слой.

## Следующий шаг

Следующий логичный блок — продолжение `WireGuard provider`: генерация клиентских
ключей и `.conf`, синхронизация inventory после provider actions и подключение
этих действий к Telegram UI.
