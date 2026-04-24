# multi-vpn-bot

Каркас модульного Telegram-бота для управления VPN-серверами, провайдерами, клиентскими конфигами и статистикой трафика.

Текущее состояние:

- реализованы этапы 0-13 из `docs/IMPLEMENTATION_TASKS.md` в базовом виде;
- этап 14 начат: добавлен executor-backed `WireGuardProvider` для healthcheck,
  списка peers, peer stats, экспорта клиентского `.conf`, создания и удаления peers,
  рендера и записи клиентских `.conf`, генерации клиентских ключей и получения public key
  через executor stdin, а также service layer для синхронизации provider actions
  с client inventory;
- собран базовый каркас проекта;
- добавлены строгие pydantic-модели JSON-конфига;
- добавлены базовое логирование и безопасный bootstrap;
- подключена SQLite через `SQLAlchemy` и подготовлены стартовые репозитории;
- подключён `aiogram` runtime, inline-меню, роли, авто-регистрация пользователей
  и пересылка сообщений администраторам;
- добавлены `ServerRegistry`, executor layer, host actions и админский Telegram UI
  для просмотра серверов и запуска системных действий;
- Telegram admin UI supports listing, syncing, creating, and confirmed deletion of
  clients inventory by enabled provider;
- добавлен `ConfigDeliveryService` и пользовательская кнопка `Мои конфиги` для выдачи
  привязанных provider configs как Telegram-файлов;
- добавлены provider base layer, unified client inventory и traffic statistics layer
  с raw samples, delta calculation и daily aggregates.
- добавлена пользовательская кнопка `Моя статистика` с daily traffic summary по всем
  привязанным VPN-клиентам.
- добавлен сценарий `Запросить конфиг`: inline-кнопка, FSM для комментария
  и отправка заявки администраторам без попадания сообщения в обычный relay.
- этап 17 реализован в базовом виде: админская статистика поддерживает фильтры
  по серверу, провайдеру, пользователю, клиенту и периоду через команды `/stats`
  и `/stats_csv`, текстовую сводку, CSV export и ограничение больших CSV-выборок.
- этап 18 начат: добавлена ручная админская выдача VPN-конфигов через команду
  `/send_config user=<telegram_id> [client=<vpn_client_id>]`, отправка файлов
  выбранному пользователю, audit-log факта выдачи и запись метаданных выдачи
  в `admin_action_logs` без сохранения содержимого конфигов; при выдаче нескольких
  конфигов команда по умолчанию отправляет один zip-архив, `archive=false`
  оставляет отправку отдельными файлами.

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
- `app/services/provider_clients`: синхронизация provider actions с client inventory;
- `app/services/config_delivery`: выдача привязанных пользовательских VPN-конфигов;
- `app/services/traffic_stats`: нормализация статистики, raw samples,
  delta calculation, дневные агрегаты, пользовательская и админская сводка трафика;
- `app/providers`: базовый provider contract, capabilities, factory, registry
  и первый WireGuard provider slice;
- `app/bot`: aiogram runtime, inline navigation, admin user management,
  message bridge и server UI;
- `app/main.py`: bootstrap конфига, логирования, БД, registry и Telegram runtime.

## Стиль миграций

На текущем этапе схема создаётся через `SQLAlchemy.metadata.create_all()` при старте. Это даёт быстрый старт для пустого проекта. Для последующих изменений схемы рекомендуется перейти на явные миграции через Alembic, не ломая уже подготовленный ORM-слой.

## Следующий шаг

Следующий логичный блок — добавить inline-админский UX для выдачи конфигов:
кнопки из карточки пользователя/клиента поверх уже готовой команды и сервисного слоя.
