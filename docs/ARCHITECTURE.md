# ARCHITECTURE.md

## 1. Назначение проекта

Разработать модульного Telegram-бота для управления VPN-сервисами, серверными действиями, клиентскими конфигурациями и пользовательской статистикой трафика.

Бот должен:

- работать даже без подключённых VPN-провайдеров;
- поддерживать несколько серверов;
- поддерживать локальные и удалённые серверы;
- динамически строить интерфейс из JSON-конфига;
- разделять доступ для администраторов и обычных пользователей;
- поддерживать расширение через provider modules;
- собирать и хранить статистику по VPN-клиентам в едином формате для разных провайдеров;
- выдавать конфиги и статистику как администраторам, так и пользователям по правилам доступа.

---

## 2. Основная архитектурная модель

### 2.1. Центральная сущность — Server

Система строится вокруг списка серверов.

Каждый сервер описывает:

- как к нему подключаться;
- какие host/system actions доступны;
- какие provider modules на нём развернуты;
- как он должен отображаться в Telegram UI.

### 2.2. Разделение ответственности

#### Server
Описывает конкретный хост.

Содержит:
- `key`
- `title`
- `enabled`
- `connection`
- `host_actions`
- `providers`
- `ui`
- `tags` (опционально)

#### Transport / Executor
Описывает, как выполняются действия на сервере.

Типы:
- `local`
- `ssh`

Это не VPN-провайдер, а механизм доступа.

#### Host/System Actions
Операции уровня хоста:
- `server_status`
- `speedtest`
- `vnstat_week`
- `healthcheck`
- в будущем: `uptime`, `disk_usage`, `docker_ps`, `public_ip` и т.д.

#### Provider Modules
Логика конкретных сервисов:
- `wireguard`
- `3xui`
- в будущем: `openvpn`, `outline`, `amnezia` и др.

#### Client Inventory Layer
Единый слой клиентских сущностей поверх разных провайдеров.

Нужен для унификации:
- списка клиентов;
- выдачи конфигов;
- привязки клиентов к Telegram-пользователям;
- отображения агрегированной статистики.

#### Traffic Statistics Layer
Отдельный слой периодического сбора статистики по клиентам.

Нужен для:
- периодического опроса провайдеров;
- нормализации статистики в общий формат;
- хранения дневных срезов и сырой истории;
- выборки за произвольный период;
- экспорта в CSV.

#### Telegram Layer
Интерфейс взаимодействия:
- inline-клавиатуры;
- callback handlers;
- states/FSM для многошаговых действий;
- права доступа;
- форматирование ответов;
- редактирование сообщений вместо захламления чата там, где это возможно.

---

## 3. Принципы проектирования

1. **Server-first model** — сервер является центральной сущностью.
2. **SSH — не provider**. SSH является transport/executor-слоем.
3. **Host actions отделены от provider actions**.
4. **Telegram UI не содержит бизнес-логики провайдеров**.
5. **Конфиг декларативный**: он описывает, что доступно, а не как это реализовано.
6. **Бот должен работать без серверов и без VPN-провайдеров**.
7. **Все права проверяются не только в UI, но и на уровне handlers/actions**.
8. **Статистика клиентов должна быть унифицирована для всех провайдеров**.
9. **Основной UI строится на inline-клавиатурах; reply keyboard не используется как основной механизм навигации**.
10. **Любое входящее сообщение пользователя вне специальных сценариев пересылается администраторам**.

---

## 4. Предлагаемый стек

- Python 3.12+
- `aiogram` — Telegram bot framework
- `pydantic` — модели и валидация конфига
- `SQLAlchemy` + `aiosqlite` или `sqlite3`/`aiosqlite` — БД
- `httpx` — HTTP API
- `asyncio` — orchestration и background tasks
- `asyncssh` или системный `ssh` — SSH transport
- `APScheduler` либо фоновые asyncio tasks — мониторинг и периодический сбор статистики
- `csv` / `pandas` опционально — экспорт табличных отчётов
- `pytest` — тестирование

---

## 5. Предлагаемая структура проекта

```text
project/
├─ app/
│  ├─ bot/
│  │  ├─ handlers/
│  │  ├─ keyboards/
│  │  ├─ middlewares/
│  │  ├─ filters/
│  │  ├─ states/
│  │  ├─ formatters/
│  │  └─ callbacks/
│  ├─ core/
│  │  ├─ config/
│  │  ├─ registry/
│  │  ├─ permissions/
│  │  ├─ executors/
│  │  └─ exceptions/
│  ├─ domain/
│  │  ├─ models/
│  │  ├─ enums/
│  │  └─ dto/
│  ├─ services/
│  │  ├─ users/
│  │  ├─ broadcasts/
│  │  ├─ host_actions/
│  │  ├─ providers/
│  │  ├─ client_inventory/
│  │  ├─ traffic_stats/
│  │  ├─ config_delivery/
│  │  └─ monitoring/
│  ├─ providers/
│  │  ├─ base/
│  │  ├─ wireguard/
│  │  └─ x3ui/
│  ├─ infrastructure/
│  │  ├─ db/
│  │  ├─ ssh/
│  │  ├─ shell/
│  │  ├─ http/
│  │  ├─ docker/
│  │  ├─ logging/
│  │  └─ exports/
│  └─ main.py
├─ configs/
│  └─ config.json
├─ stuff/
│  ├─ logs/
│  └─ multitool.db
└─ tests/
```

---

## 6. Структура конфигурации

### 6.1. Верхний уровень

```json
{
  "config_version": 1,
  "logging": {},
  "telegram": {},
  "database": {},
  "transports": {},
  "statistics": {},
  "servers": [],
  "features": {},
  "defaults": {}
}
```

### 6.2. Общие разделы

#### logging
- `logs_dir`
- `base_log_filename`
- `max_log_length`
- `level`

#### telegram
- `token` или `token_env`
- `admin_ids`
- `max_concurrent_messages`
- `max_message_length`
- `system_monitor`
- `ui_mode` со значением `inline`

#### database
- `sqlite_path`

#### transports
Глобальные параметры transport-слоя:

```json
"transports": {
  "local": {
    "enabled": true
  },
  "ssh": {
    "enabled": true,
    "use_system_ssh_config": true,
    "connect_timeout_seconds": 10,
    "command_timeout_seconds": 30
  }
}
```

#### statistics
Глобальные параметры статистики:

```json
"statistics": {
  "enabled": true,
  "collect_interval_minutes": 15,
  "store_raw_samples": true,
  "daily_rollup_timezone": "Europe/Moscow",
  "csv_delimiter": ","
}
```

---

## 7. Структура одного сервера

```json
{
  "key": "wg-main",
  "title": "WireGuard Main",
  "enabled": true,
  "connection": {
    "mode": "ssh",
    "ssh_alias": "wg-main"
  },
  "host_actions": {
    "server_status": true,
    "speedtest": true,
    "vnstat_week": true,
    "healthcheck": true
  },
  "providers": [
    {
      "type": "wireguard",
      "enabled": true,
      "settings": {}
    }
  ],
  "ui": {
    "icon": "🛡",
    "sort_order": 10
  }
}
```

---

## 8. Новый обязательный доменный блок: клиенты и статистика

### 8.1. Унифицированная модель клиента

Нужно ввести внутреннюю сущность `VpnClient`, которая не зависит от конкретного провайдера.

Минимальные поля:
- `provider_type`
- `server_key`
- `provider_client_id`
- `display_name`
- `telegram_user_id` — опциональная привязка
- `status`
- `created_at`
- `updated_at`
- `metadata`

Примеры:
- у WireGuard `provider_client_id` может быть peer name или public key;
- у 3xUI — UUID или email/remark;
- у Outline — access key id.

### 8.2. Привязка VPN-клиентов к Telegram-пользователю

Нужен отдельный слой связей:
- один Telegram-пользователь может иметь несколько VPN-клиентов;
- эти клиенты могут быть на разных серверах и у разных провайдеров;
- пользовательские команды должны агрегировать всё, что к нему привязано.

### 8.3. Унифицированная модель статистики

Нужна нормализованная запись статистики, например `TrafficStatSample`.

Минимальные поля:
- `server_key`
- `provider_type`
- `provider_client_id`
- `telegram_user_id` — если привязка существует
- `captured_at`
- `rx_bytes_total`
- `tx_bytes_total`
- `rx_bytes_delta`
- `tx_bytes_delta`
- `period_type`
- `metadata`

### 8.4. Дневная статистика

Должна вестись как минимум агрегированная дневная статистика по каждому клиенту.

Нужны значения:
- за сегодня;
- за вчера;
- за любой выбранный период;
- по одному клиенту;
- по одному пользователю;
- по одному серверу;
- по одному провайдеру.

### 8.5. Частота обновления статистики

Частота задаётся конфигом через `statistics.collect_interval_minutes`.

Периодический сборщик должен:
1. опрашивать каждый enabled provider;
2. запрашивать статистику по клиентам;
3. нормализовать данные;
4. сохранять сырые срезы;
5. рассчитывать дельты;
6. обновлять дневные агрегаты.

---

## 9. Provider contract

Каждый provider module должен реализовать унифицированный контракт.

Минимально:
- `healthcheck()`
- `list_clients()`
- `get_client(client_id)`
- `create_client(payload)`
- `enable_client(client_id)` — если поддерживается
- `disable_client(client_id)` — если поддерживается
- `delete_client(client_id)`
- `export_client_config(client_id)`
- `collect_client_stats()`

Важный принцип:
- если provider не умеет включение/выключение, он должен явно это объявлять через capabilities;
- Telegram UI строится по capabilities, а не по жёстко зашитому списку кнопок.

---

## 10. Пользовательские функции

### 10.1. Обязательное пользовательское меню

Меню пользователя должно быть минимальным и строиться на inline-клавиатурах.

Базовые пункты:
- `Получить мой Telegram ID`
- `Получить мою статистику`
- `Получить мои конфигурационные файлы`
- `Запросить конфиг`
- `Помощь`

### 10.2. Связь с администраторами

Отдельная кнопка “Связаться с администратором” не нужна.

Любое входящее сообщение пользователя, если оно не относится к специальному FSM-сценарию, должно пересылаться администраторам.

Нужно поддерживать пересылку:
- текста;
- фото;
- документов;
- видео;
- голосовых;
- стикеров;
- прочих обычных типов пользовательского контента.

### 10.3. Получение моей статистики

При нажатии на кнопку бот должен:
1. найти все VPN-клиенты, привязанные к Telegram-пользователю;
2. собрать агрегированную статистику по всем серверам и провайдерам;
3. сгруппировать её в удобный формат;
4. отправить сводку сообщением;
5. при необходимости предложить выгрузку файлом.

Пользователь не должен выбирать сервер вручную для этой операции.

### 10.4. Получение моих конфигурационных файлов

При нажатии на кнопку бот должен:
1. найти все VPN-клиенты пользователя;
2. запросить у соответствующих provider modules конфиги;
3. отправить пользователю все доступные конфиги;
4. где нужно — отправлять как файл, где нужно — как текст/ссылку/архив.

### 10.5. Запросить конфиг

Эта команда должна запускать сценарий запроса нового подключения.

Поток:
1. пользователь нажимает кнопку;
2. бот может запросить комментарий;
3. запрос пересылается администраторам;
4. администратор обрабатывает его вручную или через будущую автоматизацию.

---

## 11. Администраторские функции по статистике

Администратор должен иметь возможность:
- получить статистику по конкретному пользователю;
- получить статистику по конкретному клиенту;
- получить статистику по конкретному серверу;
- получить статистику по конкретному провайдеру;
- выбрать период `from/to`;
- выбрать сортировку `по возрастанию/по убывания трафика`
- выбрать сортировку по агрегации трафика `дневному/недельному/месячному/за всё время`
- получить результат как сообщение;
- получить результат как CSV-файл.

### 11.1. Форматы выдачи

#### Inline summary
Для коротких выборок.

#### Detailed text report
Для просмотра в Telegram.

#### CSV export
Для больших выборок и внешней аналитики.

CSV должен содержать минимум:
- date/time
- telegram_user_id
- username
- server_key
- provider_type
- provider_client_id
- display_name
- rx_bytes
- tx_bytes
- total_bytes

---

## 12. База данных

На старте SQLite подходит.

Нужно предусмотреть таблицы:
- `telegram_users`
- `vpn_clients`
- `vpn_client_user_links`
- `traffic_stat_samples`
- `traffic_stat_daily`
- `ban_records`
- `broadcasts`
- `broadcast_deliveries`
- `admin_action_logs`
- `message_links`
- `monitor_alerts` — опционально

---

## 13. Telegram UI

### 13.1. Основной подход

Основной UX должен быть построен на:
- `InlineKeyboardMarkup`;
- callback data;
- редактировании текста и клавиатуры существующего сообщения;
- минимизации обычных reply-клавиатур.

### 13.2. Требования к навигации

- каждое меню должно иметь кнопки `Назад` и `Домой`, где это уместно;
- длинные списки должны иметь пагинацию;
- опасные действия должны иметь шаг подтверждения;
- callback data должны быть компактными, но структурированными;
- FSM использовать только там, где реально нужен многошаговый ввод.

### 13.3. Reply keyboard policy

Reply keyboard не использовать как основной механизм.

Допускается только в исключительных случаях, если позже появится особый UX-сценарий. По умолчанию проект реализуется через inline-кнопки.

---

## 14. Безопасность

### 14.1. Секреты
Лучше хранить отдельно от JSON-конфига:
- Telegram token
- 3xUI credentials
- другие чувствительные данные

Через:
- env
- `.env`
- либо `*_env` поля в конфиге

### 14.2. Shell safety
Все системные команды должны идти через:
- безопасную сборку аргументов;
- whitelist допустимых операций;
- запрет прямой подстановки пользовательского текста в shell.

### 14.3. Telegram security
Проверка роли должна быть не только на уровне меню, но и на уровне каждого handler/callback.

### 14.4. Logging hygiene
Нельзя логировать:
- пароли
- токены
- приватные ключи
- приватные клиентские конфиги
- чувствительные заголовки запросов

---

## 15. Startup flow

При старте приложения должно происходить:
1. загрузка конфига;
2. валидация;
3. инициализация логирования;
4. подключение БД;
5. построение `ServerRegistry`;
6. инициализация `ExecutorFactory`;
7. инициализация `ProviderRegistry`;
8. запуск Telegram handlers;
9. запуск мониторинга;
10. запуск периодического сборщика статистики.

---

## 16. Полный пример базового JSON-конфига

```json
{
  "config_version": 1,
  "logging": {
    "logs_dir": "stuff/logs",
    "base_log_filename": "telegram_bot",
    "max_log_length": 5000,
    "level": "INFO"
  },
  "telegram": {
    "token_env": "TELEGRAM_BOT_TOKEN",
    "admin_ids": [111111111],
    "max_concurrent_messages": 5,
    "max_message_length": 4000,
    "ui_mode": "inline",
    "system_monitor": {
      "enabled": true,
      "interval_seconds": 60,
      "cpu_threshold_percent": 90.0,
      "cpu_duration_minutes": 3,
      "ram_threshold_percent": 90.0,
      "ram_duration_minutes": 3
    }
  },
  "database": {
    "sqlite_path": "stuff/multivpn.db"
  },
  "transports": {
    "local": {
      "enabled": true
    },
    "ssh": {
      "enabled": true,
      "use_system_ssh_config": true,
      "connect_timeout_seconds": 10,
      "command_timeout_seconds": 30
    }
  },
  "statistics": {
    "enabled": true,
    "collect_interval_minutes": 15,
    "store_raw_samples": true,
    "daily_rollup_timezone": "Europe/Moscow",
    "csv_delimiter": ","
  },
  "servers": [
    {
      "key": "vps-nl",
      "title": "Нидерланды",
      "enabled": true,
      "connection": {
        "mode": "ssh",
        "ssh_alias": "vps-nl"
      },
      "host_actions": {
        "server_status": true,
        "speedtest": true,
        "vnstat_week": true,
        "healthcheck": true
      },
      "providers": [
        {
          "type": "wireguard",
          "enabled": true,
          "settings": {
            "local_ip": "10.0.0.",
            "server_ip": "",
            "server_port": "51820",
            "dns_server_name": "adguardhome",
            "is_dns_server_in_docker": true,
            "wireguard_folder": "/home/user/wireguard",
            "wireguard_config_filepath": "/home/user/wireguard/config/wg_confs/wg0.conf",
            "docker_container_name": "wireguard",
            "docker_service_name": "wireguard",
            "wireguard_interface": "wg0",
            "system_names": [
              "logs",
              "coredns",
              "server",
              "templates",
              "wg_confs",
              "wg_confs_backup",
              ".donoteditthisfile"
            ],
            "allowed_username_pattern": "a-zA-Z0-9_"
          }
        }
      ],
      "ui": {
        "icon": "🛡",
        "sort_order": 10
      }
    },
    {
      "key": "vps-de",
      "title": "Германия",
      "enabled": true,
      "connection": {
        "mode": "ssh",
        "ssh_alias": "vps-de"
      },
      "host_actions": {
        "server_status": true,
        "speedtest": true,
        "vnstat_week": true,
        "healthcheck": true
      },
      "providers": [
        {
          "type": "3xui",
          "enabled": false,
          "settings": {
            "panel_url": "https://panel.example.com",
            "username_env": "X3UI_USERNAME",
            "password_env": "X3UI_PASSWORD",
            "xray_api_port": 62789,
            "xray_api_listen": "127.0.0.1"
          }
        }
      ],
      "ui": {
        "icon": "🚀",
        "sort_order": 20
      }
    }
  ],
  "features": {
    "broadcasts_enabled": true,
    "csv_export_enabled": true,
    "user_config_request_enabled": true
  },
  "defaults": {
    "speedtest_timeout_seconds": 180
  }
}
```

---

## 17. Архитектурные решения, которые обязательны для реализации

1. Сервер является центральной конфигурационной сущностью.
2. SSH не рассматривается как VPN-провайдер.
3. Host/system actions реализуются отдельным сервисом.
4. Каждый provider реализует единый контракт по работе с клиентами и статистикой.
5. Вводится отдельный слой унификации VPN-клиентов и их связи с Telegram-пользователями.
6. Вводится отдельный слой периодического сбора статистики и дневных агрегатов.
7. Пользовательские команды “Получить мою статистику” и “Получить мои конфиги” должны агрегировать данные автоматически со всех серверов и провайдеров.
8. Основной UI реализуется на inline-клавиатурах.
9. Любое входящее сообщение пользователя пересылается администраторам, если не относится к специальному сценарию.
10. Администратор должен иметь возможность выгружать статистику в CSV за произвольный период.
