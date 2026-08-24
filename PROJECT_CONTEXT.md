# Essentials — PROJECT CONTEXT

Актуальность: документ составлен по локальному состоянию проекта на 2026-08-24. Источник фактов — текущие `src/`, `tests/`, `scripts/`, `deploy/`, `pyproject.toml`, `Dockerfile`, `compose.yaml`, `README.md` и имена переменных конфигурации. Значения секретов не читались и не включены. Если утверждение нельзя подтвердить кодом, оно помечено «НЕ НАЙДЕНО В КОДЕ».

## 1. Общая информация о проекте

Essentials — асинхронный Telegram-бот для поиска и анализа новых Pump.fun-токенов в Solana через официальный `gmgn-cli`. Он фильтрует поток токенов по market/holder/Smart Money признакам, отправляет прошедшие сигналы в Telegram-форум, сохраняет delivery state в SQLite, отслеживает последующий максимум market cap и отвечает на `/stats`.

Это аналитический alerting bot. Автоматическая торговля, swap, order placement, custody средств и управление позициями **НЕ НАЙДЕНЫ В КОДЕ**.

Основные сценарии:

1. Непрерывный scanner ищет только токены, появившиеся после запуска процесса.
2. Последовательные fail-closed фильтры отбрасывают неподходящие токены или оставляют их на retry при неполных данных.
3. Успешный alert состоит из token card и ответного сообщения с analytics/Smart Money.
4. Results tracker периодически проверяет market cap ранее отправленных токенов и публикует milestones.
5. Пользователь Telegram вызывает `/stats [1..365]` и получает агрегированную статистику.

Текущее состояние:

- entry point, scanner, delivery, Results и `/stats` реализованы;
- полный test suite: **228 passed** на дату документа;
- рабочее дерево содержит множество незакоммиченных и untracked пользовательских файлов;
- production scanner в рамках составления документа не запускался;
- README синхронизирован с порогами Top10 `35%` и MVP `$19,000`;
- текущий backlog приведён в разделе 12 и не следует считать реализованным.

### QUICK PROJECT SUMMARY

- Что это: Telegram alert bot для раннего отбора Pump.fun/Solana токенов.
- Данные: GMGN Trenches, token info, holders, wallet profits/holdings; Solana RPC и Pump.fun metadata для изображений; Telegram Bot API для доставки.
- Главные функции: discovery, freshness/dedup, Top10 concentration, Top30 Smart Money, Lightning/MVP gate, двухсообщенческий alert, Results tracking, `/stats`.
- Главная текущая линия развития: согласно переданному backlog — дополнительные KOL/dev/migration/community/price-drop проверки, изменение alert UI и новый price scanner. Эти изменения пока не подтверждены production-кодом.

## 2. Структура проекта

```text
essentials/
├── src/essentials/           production package
├── tests/                    pytest suite
├── scripts/                  manual diagnostics/benchmarks/live checks
├── assets/results/           PNG templates and fonts for Results/Stats
├── deploy/essentials.service systemd unit
├── data/                     SQLite and runtime caches
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── README.md
├── .env.example
└── PROJECT_CONTEXT.md
```

### Production-модули

| Файл | Ответственность | Основные зависимости |
|---|---|---|
| `main.py` | Создание компонентов и параллельный запуск scanner, Results, Telegram receiver | почти все production-модули |
| `config.py` | Чтение/валидация environment, defaults | stdlib |
| `gmgn.py` | Trenches discovery и startup baseline | `models`, `gmgn_rate`, `retry` |
| `models.py` | `Token`, GMGN parsing, defensive Stage 1 | `token_age` |
| `analytics.py` | token info, holders, holder metrics, KOL display, caches | `gmgn_rate`, `retry`, `models`, `httpx` |
| `smart_money.py` | meaningful Top30, wallet classification, portfolio/MVP enrichment | `analytics`, `gmgn_rate`, `gmgn` |
| `service.py` | Полный alert pipeline и порядок gates | discovery, analytics, Smart Money, delivery, DB |
| `delivery.py` | Атомарная card/reply state machine | Telegram, DB |
| `telegram.py` | Telegram HTML, buttons, send/get/delete API | `httpx`, `retry`, image/model/formatting |
| `second_message.py` | Формат analytics, Smart и KOL блока | analytics, Smart Money, formatting |
| `db.py` | SQLite schema, dedup, delivery, Results, runtime offset | `sqlite3`, formatting |
| `results.py` | MC tracking, milestones, images, `/stats`, update consumer | DB, Telegram, GMGN rate |
| `image_resolver.py` | Pump.fun/Metaplex/GMGN/IPFS image resolution | `httpx`, Pillow, solders |
| `gmgn_rate.py` | Process-wide weighted pacing и cooldown | asyncio |
| `retry.py` | Exponential retry с jitter | asyncio |
| `formatting.py` | `format_ticker()` — удаляет все ведущие `$` из ticker | stdlib |
| `token_age.py` | Безопасное преобразование timestamps и age | stdlib |

### Точки входа и запуск

- Python console script: `essentials = essentials.main:main`.
- Локально: `.venv/bin/essentials`.
- Docker: `CMD ["/opt/venv/bin/essentials"]`, Compose монтирует `./data:/app/data`.
- systemd: `/opt/essentials/.venv/bin/essentials`, environment из `/opt/essentials/.env`.
- `scripts/bootstrap.sh`: создаёт `.venv`, устанавливает editable package/dev extras и global `gmgn-cli`.

### Tests

`tests/` зеркалирует production areas: analytics, DB, delivery, discovery, images, models, Results, formatting, service, Smart Money, Telegram и diagnostics.

### Scripts

- `test_alert.py`, `test_live_alert.py`, `test_concurrent_alerts.py` могут отправлять реальные Telegram-сообщения.
- `watch_live_alert.py`, `watch_smart_alert.py`, `watch_smart_money.py` ждут live candidates и диагностируют pipeline.
- `audit_smart_requests.py`, `benchmark_two_stage_smart.py`, `live_latency.py` измеряют request pattern/latency.
- `probe_*`, `control_hide_abnormal.py`, `debug_wallet_portfolio.py` — read-only research probes.
- `test_results.py`, `test_stability.py`, `test_telegram_startup.py`, `test_freshness_format.py` — offline smoke simulations.
- `render_previews.py` — локальная генерация preview assets.

## 3. Технический стек

| Компонент | Реализация |
|---|---|
| Язык | Python `>=3.9` |
| Async runtime | `asyncio` |
| HTTP | `httpx>=0.27,<1` |
| Telegram framework | Отдельный framework **НЕ НАЙДЕН В КОДЕ**; прямые Bot API POST через `httpx` |
| Изображения | `Pillow>=11,<12` |
| Solana public keys/PDA | `solders>=0.26,<1` |
| GMGN client | Global Node CLI `gmgn-cli`; версия не закреплена |
| Database | SQLite через stdlib `sqlite3`, WAL mode |
| ORM | **НЕ НАЙДЕН В КОДЕ** |
| Scheduler | Отдельная библиотека **НЕ НАЙДЕНА В КОДЕ**; asyncio forever loops/sleeps |
| Packaging | hatchling, `pyproject.toml` |
| Tests | `pytest>=8,<9`, `pytest-asyncio>=0.23,<1` |
| Container | Node 22 Bookworm slim + Python venv + global gmgn-cli |
| Deployment | Docker Compose или hardened systemd unit |

`requirements.txt` и `package.json`: **НЕ НАЙДЕНЫ В КОДЕ**. Python dependencies определены в `pyproject.toml`. Версия `gmgn-cli` не pinned ни в Dockerfile, ни в bootstrap.

Хранение данных:

- SQLite database, default `data/essentials.db`;
- holder cache: `data/cache/holders/<mint>.json`;
- token info cache: `data/cache/token_info/<mint>.json`;
- in-memory caches/locks/sets для текущего процесса;
- environment для config и credentials;
- GMGN credential/signing config вне repository.

## 4. GMGN API и получение данных

Production обращается к GMGN только через команды официального CLI. Реальные HTTP endpoint URLs внутри CLI **НЕ НАЙДЕНЫ В КОДЕ**.

| CLI operation | Параметры production | Назначение |
|---|---|---|
| `market trenches` | `chain=sol`; types new_creation/near_completion/completed; Pump.fun; limit 80 | startup universe и discovery |
| filtered `market trenches` | дополнительно MC 50k–250k, min fee 5, min renowned 3 | дешёвый первичный отбор |
| `token info` | chain sol, token address, raw | creation time, price/stat/dev fields, Results MC, SOL price |
| `token holders` | chain sol, address, percentage desc, limit 100, raw | concentration, Top30, KOL, dev holder position |
| `portfolio profits` | batch wallets, period 7d | buy+sell count для bot threshold |
| `portfolio profits` | batch wallets, period all | `total_realized_profit` |
| `portfolio holdings` | wallet, pages 50, USD desc, hide closed/abnormal, keep airdrops | current SPL portfolio |
| `portfolio holdings` MVP | wallet, closed included, realized profit desc, limit 50 | historical winners/MVP |

### Поле GMGN → использование

| Поле | Где используется | Зачем |
|---|---|---|
| `address` | Token/parser/service | mint/CA, dedup, links, downstream requests |
| `symbol`, `name` | Telegram/Results | отображение; ticker нормализуется |
| `market_cap` | Stage 1 | inclusive 50k–250k и called MC |
| `total_fee` | Stage 1 | минимум 5 |
| `renowned_count` | Stage 1/KOL display | минимум 3 entered; display total entered |
| `launchpad_platform` | Stage 1 | строго Pump.fun |
| `twitter`, `website`, `telegram` | Stage 1/card | наличие хотя бы одного social; X button использует `twitter` |
| `market_address`/`pair_address`/`pool_address` | Telegram keyboard | Axiom link, CA не подставляется вместо market address |
| `creation_timestamp` | freshness | canonical pre/post-start boundary |
| `logo`, `logo_small_base64` | image metadata/model | GMGN logo fallback; small base64 хранится, прямое использование в resolver **НЕ НАЙДЕНО** |
| `price.price` | analytics/Results | current MC calculation, SOL/USD |
| `circulating_supply` | Results | current MC = price × circulating supply |
| price volume/change fields | second message | 5m/1h/24h display, не gate |
| `holder_count` | second message | display, не gate |
| `dev.creator_address` | analytics | поиск creator среди holders |
| creator balance/status fields | analytics | dev hold display, не gate |
| holder `amount_percentage` | Top1/10/70, Top30 | concentration/ranking |
| holder `addr_type`, tags | meaningful holders | исключение system/burn/pool |
| holder `native_balance` | portfolio | lamports→SOL, затем USD |
| holder `usd_value` | candidate restoration | вернуть candidate position, если hidden portfolio её пропустил |
| wallet `buy_count`/`sell_count` | Smart prefilter | 7d transaction count |
| `total_realized_profit` | Smart | positive all-time PnL |
| holding `usd_value` | portfolio/Lightning/MVP | portfolio sum/current position/remaining value |
| holding `unrealized_profit` | Lightning | other holding требует PnL ≥0 |
| holding token address/symbol | dedup/exclusions/display | stable/WSOL/candidate exclusions |
| `realized_profit` | MVP | минимум `$19,000` |
| response `next` | portfolio crawl | cursor pagination |

### Частота, limits и errors

- Scanner interval: `POLL_INTERVAL_SECONDS`, code default 60 s.
- Results loop: 30 s; отдельный age-based interval на call.
- Global coordinator сериализует request starts: `0.3 s × weight`.
- Weight: market/token info/batch profits = 1; holders/portfolio page/MVP = 5.
- Holders дополнительно serialized lock + минимум 1.5 s между запросами.
- Generic retry: exponential 1/2/4… s, cap 15 s + jitter 0–0.25, число attempts из `MAX_RETRIES`.
- `RATE_LIMIT_BANNED`/`RATE_LIMIT_EXCEEDED` создают process-wide cooldown до parsed reset; fallback 60 s.
- Rate limit/cooldown не ретраятся немедленно.
- Token info/holder cache TTL 60 s; Smart/portfolio 300 s; MVP 900 s.
- Stale holder cache production default выключен.
- CLI timeout default 45 s; MVP max 15 s.
- Timeout, malformed JSON, CLI error, missing page or repeated cursor fail closed.

## 5. Логика сканеров

### 5.1 Production token scanner

- Название: `AlertService`.
- Файл/функция: `service.py`, `run_forever()` → `run_once()`.
- Период: env-configurable, default 60 s после каждого цикла.
- Universe: Solana Pump.fun, GMGN groups new creation/near completion/completed.

```text
startup baseline
↓
filtered Trenches discovery
↓
batch/startup/pre-start/SQLite/in-flight dedup
↓
defensive Stage 1
↓
token info + holders
↓
Top10 meaningful ≤35%
↓
Top30 Smart analysis
↓
≥5 SMART wallets
↓
Lightning/MVP marker exists
↓
image best effort
↓
Telegram card + reply
↓
completed delivery + Results registration
```

Любой failed hard filter прекращает текущую обработку. Недоступные critical data дают retry в следующем scan. Permanent dedup появляется только после completed delivery.

### 5.2 Results price scanner

- Название: `ResultsTracker`.
- Файл: `results.py`.
- Outer loop: каждые 30 s.
- Обрабатывает due rows из `results_calls`, limit 100, concurrency 2.
- Current MC получает через `token info` как price × circulating supply.
- Active schedule: 60 s до 6h; 3m до 1d; 10m до 7d; затем 30m.
- После 24h отсутствующего MC → inactive, recheck 6h.
- Первый result при max X ≥2; следующий при max X ≥1.5 × previous published X.

### 5.3 Telegram command receiver

- Название: `StatsReceiver`.
- Файл: `results.py`.
- Long poll `getUpdates`, timeout 30 s.
- Исполняет только `/stats` в configured chat/topic; старый startup backlog подтверждает, но не выполняет.
- Persisted offset обеспечивает at-most-once command handling.

### 5.4 Manual scanners

Watch/probe scripts не запускаются `main.py` и не являются отдельными production scanners. Некоторые отправляют реальные сообщения; назначение указано в разделе 2.

## 6. Smart Money / Smart Holders

### Meaningful holders

Исключаются holder rows с `addr_type` 1 (burn/dead) или 2 (DEX/pool), а также tags из точного набора:

`burn`, `burn_address`, `dead`, `dead_address`, `dex`, `dex_pool`, `pool`, `liquidity_pool`, `bonding_curve`, `system`, `system_address`.

Tags читаются из `tag`, `tags`, `maker_token_tags`. Creator/dev с `addr_type=0` сохраняется. Blacklist адресов **НЕ НАЙДЕН В КОДЕ**.

### Top30

Meaningful rows сортируются по `amount_percentage` убыванию. Выбираются до 30 уникальных непустых wallet addresses с percentage >0. Исходный rank сохраняется; display name берётся из name/twitter/label, иначе `wallet`. `native_balance` трактуется как lamports.

### SMART classification

| Условие | Значение |
|---|---:|
| 7d transactions | `<1600` |
| all-time realized PnL | `>0` |
| current portfolio | `≥$5,000` |
| SMART wallets для token | `≥5` |
| portfolio concurrency | `1` |

Сначала batch 7d/all profits отсеивает bot/PnL failures, затем только prequalified wallets получают дорогой full portfolio crawl. Current total = unique SPL USD values + native SOL × SOL/USD. Candidate USD position восстанавливается один раз из authoritative holder row, если `hide_abnormal=true` её скрыл.

Статусы:

- `BOT`: transactions ≥1600;
- `NOT_SMART`: PnL ≤0 или известный portfolio <5000;
- `SMART`: все три условия выполнены;
- `UNKNOWN`: отсутствуют transactions, PnL или итоговый portfolio.

Token Smart gate: True при ≥5 SMART; None при меньшем числе и хотя бы одном UNKNOWN; иначе False. И False, и None не записываются в permanent dedup, поэтому token может проверяться повторно.

### KOL calls

Token-level `renowned_count >=3` — обязательный Stage 1 filter и отображается как `total kols entered`. Current KOL holders выбираются из meaningful holders с `kol`/`renowned` tag, percentage >0 и ненулевым current amount, затем показываются с rank/name/address. Отдельная проверка количества current KOL holders как alert gate **НЕ НАЙДЕНА В КОДЕ**.

### Молнии

- `⚡`: SMART wallet держит другой token (не candidate, WSOL или stablecoin) стоимостью ≥`$4,900` с unrealized/current PnL ≥0.
- `⚡⚡`: SMART wallet имеет MVP position с realized profit ≥`$19,000`, remaining value ≤`$100` и valid token address.
- До двух other holdings и до двух MVP отображаются.
- MVP не меняет wallet SMART, но token-level `lightning_gate` требует хотя бы один `⚡`/`⚡⚡`.
- Если markers отсутствуют и enrichment complete → reject. Если MVP enrichment недоступен → UNKNOWN/retry.

## 7. Фильтры токенов

| Фильтр | Файл / функция | Текущее значение | Что делает |
|---|---|---:|---|
| Chain | `gmgn.py:GmgnClient.command` | `sol` | Ограничивает discovery |
| Launchpad | `gmgn.py`, `models.py:passes_stage1` | `Pump.fun` | Server + defensive local check |
| GMGN type | `gmgn.py` | new/near/completed | Discovery categories |
| Market cap | `models.py:passes_stage1` | 50k–250k inclusive | Hard gate |
| Total fee | там же | ≥5 | Hard gate |
| KOL entered | там же | renowned ≥3 | Hard gate |
| Social presence | `models.py:has_social_from_gmgn` | ≥1 field | twitter/website/telegram |
| Startup freshness | `service.py` | creation ≥ scanner start | Не алертить pre-start tokens |
| Persistent dedup | `db.py:contains` | completed CA | Не отправлять повторно |
| In-flight/batch dedup | `service.py` | unique mint | Конкурентная защита |
| Meaningful holders | `analytics.py` | exclude system/burn/pool | Очищает holder universe |
| Top10 | `analytics.py:top10_gate` | ≤35% | Hard concentration gate |
| Smart transaction | `smart_money.py` | <1600/7d | Anti-bot |
| Smart PnL | там же | >0 all-time | Wallet quality |
| Smart portfolio | там же | ≥$5,000 | Wallet quality |
| Smart count | `SmartAnalysis.gate` | ≥5 | Token gate |
| Lightning holding | `other_token_positions` | ≥$4,900; PnL ≥0 | Marker/quality gate |
| MVP | `best_mvps` | realized ≥$19k; remainder ≤$100 | Double marker/quality gate |

Проверка обязательных категорий:

- Volume: собирается и показывается, **не filter**.
- Liquidity: **НЕ НАЙДЕНО В КОДЕ как filter**.
- Holder count: показывается, **не filter**.
- Top holders: Top10 filter и Top30 Smart universe реализованы.
- KOL: renowned count ≥3 реализован; current holdings только display.
- Dev wallet: holds вычисляется/показывается, **не filter**.
- Migration: **НЕ НАЙДЕНО В КОДЕ**.
- Blacklist: **НЕ НАЙДЕНО В КОДЕ**.
- Mint authority/freeze/network attachment validation: **НЕ НАЙДЕНО В КОДЕ**.
- Price drop/dead token filter до alert: **НЕ НАЙДЕНО В КОДЕ**.
- Community existence beyond generic social presence: **НЕ НАЙДЕНО В КОДЕ**.
- Social updates monitoring: **НЕ НАЙДЕНО В КОДЕ**.
- Token age numeric cutoff: **НЕ НАЙДЕНО**; есть только process-start freshness.

## 8. Telegram bot

Один Bot API token (`TELEGRAM_BOT_TOKEN`) и один configured chat используются для alerts, Results и commands. Дополнительные боты **НЕ НАЙДЕНЫ В КОДЕ**.

Topics:

- alerts: `TELEGRAM_ALERTS_THREAD_ID`, optional;
- Results: `TELEGRAM_RESULTS_THREAD_ID`, default 4, required main wiring;
- Chat/commands: `TELEGRAM_CHAT_THREAD_ID`, default 88;
- chat/supergroup: `TELEGRAM_CHAT_ID`.

Команды:

- `/stats` → 7 days;
- `/stats N`, `1≤N≤365`;
- другие bot commands и callbacks **НЕ НАЙДЕНЫ В КОДЕ**.

Alert card HTML:

```text
🧠 smarts detected

TICKER - Token Name - $MarketCap

🪙 ca - <full CA as code>

⬇️ holders distribution and info
```

Ticker проходит через общий `format_ticker()` и отображается без ведущего `$`; поэтому cashtag word joiner больше не нужен. Все external metadata HTML-escaped.

Buttons:

- optional wide X button;
- Axiom only with GMGN-provided market/pair/pool address;
- GMGN token page;
- Padre token page;
- optional custom emoji IDs.

Первое сообщение отправляется как `sendPhoto`, если resolver вернул image; при Telegram image error fallback — `sendMessage`. Второе сообщение reply содержит volume/price, dev holdings, Top1/10/70, holder count, Smart wallets, KOLs, full wallet addresses и lightning/MVP blocks.

Inline callback handlers **НЕ НАЙДЕНЫ В КОДЕ**; кнопки URL-only.

Dedup защищён DB state machine и in-memory guard. Telegram 5xx/429 и transport errors ретраятся. Логи `httpx` выставляются на WARNING, потому что Bot API URL содержит token.

Results публикуются в отдельный topic, сначала как cross-topic reply к original card. При отказе Telegram используется clickable private message link. `/stats` Top10 ticker отображается без `$`, всегда bold и при valid coordinates также clickable.

## 9. Database

SQLite без ORM. Connection: timeout 10 s, WAL mode, busy timeout 10 s. Foreign keys и explicit relations **НЕ НАЙДЕНЫ В КОДЕ**; связи логические по mint/token CA.

### `alerted_tokens` (legacy-compatible)

| Поле | Тип | Назначение |
|---|---|---|
| `ca` | TEXT PK | token address |
| `alerted_at` | TEXT NOT NULL | UTC ISO timestamp |
| `telegram_message_id` | INTEGER nullable | legacy first message ID |

### `alert_deliveries`

| Поле | Назначение |
|---|---|
| `token_ca` PK | dedup key |
| `card_message_id` | first token card |
| `data_message_id` | second analytics reply |
| `telegram_chat_id` | original chat |
| `telegram_thread_id` | original topic |
| `delivery_status` | `pending`, `card_sent`, `completed` |
| `updated_at` | UTC ISO timestamp |

Только completed участвует в `contains()`. Это позволяет повторно завершить partial delivery.

### `results_calls`

Хранит: mint PK, normalized ticker, called MC/time, original chat/thread/card coordinates, current/max MC, max X, first 2x time, last check/valid/missing times, active/inactive state, last published milestone, next due time, pending publication state, Results message ID, created/updated timestamps. Decimal хранится как TEXT для точности.

Indexes: `(tracking_state,next_due_at)` и `called_at`.

### `runtime_state`

Key/value/timestamp. Production use — persisted `telegram_next_update_id`; advance монотонный (`max`).

Schema migration framework/version table **НЕ НАЙДЕНЫ В КОДЕ**. Инициализация создаёт отсутствующие таблицы/indexes и переносит legacy alerts в completed deliveries через `INSERT OR IGNORE`.

## 10. Price tracking / Results

Tracking реализован для каждого completed alert.

- `called_mc` фиксируется при completed delivery.
- Current MC = valid positive token price × positive circulating supply.
- `max_mc = max(previous,current)`; `max_x = max_mc/called_mc`.
- `first_2x_at` ставится при первом наблюдении max X ≥2.
- Публикация: первый milestone ≥2x, затем прирост до ≥1.5× последнего published X.
- Явных отдельных rules X5/X10/X30/X50/X100 **НЕТ**; они могут быть опубликованы только если удовлетворяют общей 1.5× формуле.
- Missing MC после 24h переводит call в inactive; recheck 6h. Valid MC реактивирует.
- Pending state сохраняет публикацию между возможными сбоями.

`/stats`:

- period 1–365 days;
- alerts = число calls за period;
- hits = calls с max X ≥2;
- hit rate = hits/alerts ×100;
- median time to 2x — median только по hits с known `first_2x_at`;
- Top10 сортируется по max X descending;
- denominator — все calls периода;
- cooldown 60 s/user;
- synchronous GMGN refresh при `/stats` **не выполняется**: используется SQLite snapshot.

## 11. Current bugs / problems

Подтверждённые тестами runtime failures: **НЕ НАЙДЕНЫ**; 228 tests проходят. Ниже только наблюдаемые ограничения/риски текущей реализации, без предложения решений:

1. README раньше расходился с кодом по Top10/MVP; в текущем working tree синхронизирован.
2. Версия global `gmgn-cli` не pinned: bootstrap и Docker устанавливают latest package, поэтому поведение может измениться вне Python-кода.
3. SQLite schema version/migrations отсутствуют; `CREATE TABLE IF NOT EXISTS` не обновляет структуру уже существующей таблицы.
4. Portfolio concurrency =1 и weighted serialization делают Smart stage потенциальным latency bottleneck. Это осознанно наблюдается benchmark scripts.
5. Up to 30 wallets × multi-page portfolio + MVP calls создают значительный request volume; rate-limit path переводит данные в UNKNOWN.
6. Stale holder cache production выключен, поэтому GMGN holders outage полностью останавливает candidate на этом цикле.
7. Telegram image resolver использует несколько внешних источников; image optional, поэтому отказ меняет формат card на text fallback.
8. Results original-link builder требует private supergroup-style chat ID; malformed legacy coordinates могут приводить к повторяющейся ошибке processing конкретного call.
9. systemd unit разрешает запись только `/opt/essentials/data`; runtime caches должны находиться под этим path/default working directory.
10. Отдельный health check/metrics endpoint **НЕ НАЙДЕН В КОДЕ**; наблюдаемость основана на logs и diagnostic scripts.
11. Автоматическая проверка Telegram topic existence/permissions при startup **НЕ НАЙДЕНА В КОДЕ**.

## 12. Current TODO / planned changes

Ниже — задачи, явно переданные владельцем проекта. Это backlog, а не описание реализованного поведения.

| Задача | Текущее состояние в коде |
|---|---|
| KOL filter сделать больше 2 | Эквивалент `renowned_count >=3` уже есть; смысл отдельного изменения требует уточнения |
| Исправить проблему синтаксиса | Конкретная проблема **НЕ НАЙДЕНА В КОДЕ**; suite проходит |
| Price drop filter против мёртвых токенов | **НЕ НАЙДЕН В КОДЕ** |
| Dev holds максимум 2% | Dev percentage display есть; gate **НЕ НАЙДЕН** |
| Migration: минимум 2 запуска, минимум 1 миграция | **НЕ НАЙДЕНО В КОДЕ** |
| Для migrated token: минимум 3 fees/«взятки» | **НЕ НАЙДЕНО В КОДЕ** |
| Проверка привязанной сети к токену | Помимо chain=sol **НЕ НАЙДЕНО В КОДЕ** |
| Проверка наличия сообщества | Generic social presence есть; отдельная community validation **НЕ НАЙДЕНА** |
| Отслеживание update socials у GMGN | **НЕ НАЙДЕНО В КОДЕ** |
| Убрать картинки токенов из alert | Не выполнено; image resolver активен, text fallback существует |
| Сохранить Smart Money ⚡ | Реализовано и участвует в final quality gate; должно быть сохранено |
| Сделать новый price scanner | Есть ResultsTracker, но новый отдельный scanner **НЕ НАЙДЕН В КОДЕ** |

## Completed Changes

- 2026-08-24 — ticker formatting обновлён: все ведущие `$` удаляются из названий токенов во всех пользовательских сообщениях и Results/Stats.
- 2026-08-24 — из строки второго сообщения убраны визуальные дефисы: `total holders <value> | smarts <value>`.
- 2026-08-24 — `/stats` Top10 унифицирован: ticker всегда bold, а при валидных coordinates ведёт на original token card.

## 13. Code map

| Логика | Файл / функция | Что отвечает за изменение |
|---|---|---|
| App wiring | `main.py:async_main` | Компоненты, loops, topic requirements |
| Env | `config.py:Settings.from_env` | Variables/defaults/validation |
| Discovery query | `gmgn.py:GmgnClient.command` | GMGN server-side universe/filters |
| Startup baseline | `gmgn.py:fetch_startup_baseline_mints`, `service.py:prepare_startup_baseline` | Fresh-start protection |
| Token parser/Stage 1 | `models.py:Token.from_gmgn`, `passes_stage1` | MC/fee/KOL/social/launchpad |
| Alert order | `service.py:AlertService.run_once` | Gate sequence и final send |
| Meaningful holders | `analytics.py:meaningful_holders` | System/burn/pool exclusions |
| Top10 | `analytics.py:aggregate_top`, `top10_gate` | Concentration calculation/threshold |
| Holder/KOL analytics | `analytics.py:TokenAnalyticsClient.fetch`, `kol_holders` | Display metrics/KOL list |
| Top30 | `smart_money.py:_top30_holder_rows` | Wallet universe/ranking |
| SMART | `smart_money.py:classify_smart_wallet`, `analyze_holders` | Bot/PnL/portfolio logic |
| Portfolio | `smart_money.py:_current_portfolio` | Cursor crawl/cache/options |
| Lightning | `other_token_positions`, `visual_marker`, `SmartAnalysis.lightning_gate` | ⚡ logic |
| MVP | `best_mvps`, `_wallet_mvps`, `enrich_visuals` | ⚡⚡ logic |
| Alert HTML | `telegram.py:caption`, `keyboard`; `second_message.py:format_second_message` | Card/buttons/analytics text |
| Delivery/dedup | `delivery.py:send_alert_bundle`; `db.py` delivery methods | Atomic state and coordinates |
| Image | `image_resolver.py:ImageResolver.resolve` | Source order/fallback |
| Results | `results.py:ResultsTracker.process_call`, `should_publish` | MC schedule/milestones |
| `/stats` | `results.py:StatsReceiver`, `stats_summary`, `stats_caption` | Command/statistics/UI |
| Original links | `results.py:private_message_link`, `stats_ticker_html` | Telegram private links/fallback |
| GMGN throttling | `gmgn_rate.py:GmgnRateCoordinator`, `rate_limit_error` | Weight/cooldown parsing |
| Retry | `retry.py:with_retry` | Attempts/backoff/jitter |
| SQLite schema | `db.py:AlertStore._initialize` | Tables/indexes/legacy migration |

## 14. Data flow

```text
Environment + GMGN local signing config
                 ↓
Settings / component wiring
                 ↓
GMGN market trenches
                 ↓
Token.from_gmgn parser
                 ↓
freshness + dedup + defensive Stage 1
                 ↓
GMGN token info + holders
                 ↓
meaningful holders → Top10 ≤35%
                 ↓
Top30 wallet addresses
                 ↓
7d stats + all-time PnL batch prefilter
                 ↓
current portfolio pages + SOL/USD
                 ↓
SMART classification → at least 5
                 ↓
other holdings + MVP enrichment
                 ↓
Lightning quality gate
                 ↓
optional Pump.fun/Metaplex/GMGN image
                 ↓
Telegram card → analytics reply
                 ↓
SQLite completed delivery/results_calls
                 ↓
GMGN token info price tracking
                 ↓
Results milestones + /stats
```

Critical unavailable data до Telegram не создаёт alert и не создаёт completed dedup. Telegram partial delivery сохраняется как pending/card_sent. После completed call независимый Results loop работает с тем же mint.

## 15. Примеры из проекта

Все примеры ниже основаны на test fixtures/formatters; это не live recommendations.

### Пример минимального GMGN token payload

```json
{
  "address": "MINT",
  "symbol": "SNEK",
  "name": "Example Token",
  "market_cap": "50000",
  "total_fee": "5",
  "renowned_count": 3,
  "launchpad_platform": "Pump.fun",
  "twitter": "example"
}
```

Используются address/symbol/name, MC, fee, renowned count, platform и social presence. При этих boundary values Stage 1 проходит.

### Пример holder/wallet metrics

```json
{
  "address": "WALLET",
  "addr_type": 0,
  "amount_percentage": "0.02",
  "native_balance": "1000000000"
}
```

Это meaningful wallet с 2% token supply и 1 native SOL до конвертации. Если 7d buy+sell =1599, all-time realized PnL >0 и current total portfolio =$5000, wallet проходит SMART ровно на границах.

### Пример принятого token

Условия из кода:

- Pump.fun, MC `$50,000`, fee `5`, renowned `3`, social present;
- создан после scanner start, отсутствует в baseline/DB;
- meaningful Top10 =35%;
- минимум 5 wallets: each tx ≤1599, positive realized PnL, portfolio ≥$5000;
- хотя бы один SMART имеет eligible other holding ≥$4900 с PnL ≥0 либо MVP ≥$19000 с remainder ≤$100;
- Telegram принимает card и reply.

Результат: delivery `completed`, coordinates сохраняются, call начинает Results tracking.

### Примеры отказа/retry

- Top10 `35.01%` → hard reject текущего цикла.
- Wallet tx `1600` → BOT, не SMART.
- Wallet realized PnL `0` → NOT_SMART.
- Wallet portfolio `$4,999.99` → NOT_SMART.
- Четыре SMART без UNKNOWN → token Smart gate False.
- Пять SMART, но ни одного `⚡/⚡⚡` и enrichment complete → Lightning reject.
- Holders/API/portfolio unavailable → UNKNOWN; no alert, no completed dedup, retry later.
- Token existed before process start → permanent in-memory pre-start skip for current process.
- Telegram card sent, reply failed → state остаётся `card_sent`, а completed dedup/Results registration не выполняются.

## Recent Changes

### 2026-08-24 — ticker и holders/smarts UI fix

Изменение:

- Удалён `$` из отображения ticker/symbol во всех пользовательских сообщениях.
- Убраны дефисы из строки `total holders | smarts`.

Файлы:

- `src/essentials/formatting.py`
- `src/essentials/telegram.py`
- `src/essentials/second_message.py`
- `tests/test_telegram.py`
- `tests/test_second_message.py`
- `tests/test_results.py`
- `scripts/render_previews.py`
- `PROJECT_CONTEXT.md`

Изменено:

- `format_ticker()` теперь обрезает whitespace и удаляет любое число ведущих `$`.
- `TelegramClient.caption()` больше не создаёт cashtag и не использует ticker word joiner.
- `format_second_message()` выводит `total holders <value> | smarts <value>`.

Проверка:

- связанные tests: 70 passed;
- полный suite: 228 passed;
- `git diff --check`: OK.

### 2026-08-24 — единый ticker style в `/stats` Top10

Изменение:

- Top10 ticker сделан bold во всех строках.
- При valid original-message coordinates ticker стал clickable; malformed/missing coordinates дают bold fallback без ссылки.

Файлы:

- `src/essentials/results.py`
- `tests/test_results.py`
- `PROJECT_CONTEXT.md`

Изменено:

- Добавлен `stats_ticker_html()` с использованием существующего `private_message_link()`.

Проверка:

- полный suite после изменения: 228 passed;
- `git diff --check`: OK.

## Context Update Protocol

После каждой задачи, изменяющей код:

1. Внести минимальное целевое изменение.
2. Запустить связанные тесты.
3. Запустить полный suite, если изменение затрагивает production behavior или общий formatter.
4. Обновить только затронутые разделы `PROJECT_CONTEXT.md`.
5. Добавить датированную запись в `Recent Changes` с изменением, файлами, функциями и проверками.
6. Подтверждённую выполненную задачу перенести из `Current TODO` в `Completed Changes`.
7. Не помечать изменение выполненным без подтверждения кодом и тестами.
8. Не удалять исторические записи; новые записи добавлять выше старых внутри `Recent Changes`.
9. Обновить `CHANGELOG_AI.md` записью с датой, задачей, файлами, изменённой логикой и результатом проверок.
10. Проверить `git status`, добавить в commit только относящиеся к задаче файлы, создать commit формата `type: краткое описание` и выполнить push в configured GitHub remote.
11. Не включать в commit `.env`, credentials или несвязанные пользовательские изменения dirty worktree.

GitHub является главным долговременным хранилищем истории. Если remote отсутствует, authentication не работает или push отклонён, это явно отмечается как `GitHub sync: FAILED`; локальные изменения и документация при этом не считаются отправленными в GitHub.

Финальный ответ по каждой code-задаче обязан содержать:

```text
PROJECT_CONTEXT UPDATED: да/нет

Updated sections:
- <список разделов>
```

Дополнительный обязательный финальный блок:

```text
GitHub sync: DONE / FAILED

Updated:
- PROJECT_CONTEXT.md
- CHANGELOG_AI.md

Commit:
- <commit name или NOT CREATED>
```

---

После каждого изменения архитектуры, фильтров, порогов, pipeline или поведения бота этот файл ОБЯЗАТЕЛЬНО обновляется.
