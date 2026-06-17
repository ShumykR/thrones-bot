# ThroneChat — Telegram-бот у стилі "Гри престолів"

Ігровий Telegram-бот для закритого чату (10–15 осіб), що перетворює звичайний груповий чат на живу стратегічну гру з Королями, Лордами, арміями, замками та коаліціями.

---

## Стек технологій

| Шар | Технологія |
|---|---|
| Мова | Python 3.11+ |
| Telegram Framework | aiogram 3.x (async) |
| База даних | SQLite (SQLAlchemy ORM) — для малої групи достатньо |
| Планувальник | APScheduler (asyncio-native) |
| WebApp Frontend | Single-file HTML + Vanilla CSS + Vanilla JS |
| Веб-сервер для WebApp | aiohttp або FastAPI (мінімальний REST API) |
| Розгортання | VPS або локальний сервер (звичайний Python процес) |

---

## Запропоновані механіки (розв'язання відкритих питань)

### 👑 Скидання Короля — "Велика Змова"
1. Будь-який Лорд таємно надсилає `/conspiracy` боту в ПП (через Deep Link)
2. Бот постить в чат одне **живе повідомлення** з таймером 4 години та інлайн-кнопками
3. Гравці обирають позицію через кнопки (вибір видимий за лічильниками, але не за іменами)
4. Бот рахує: `армія_повстанців × rand(0.8–1.2)` vs `армія_короля + армія_лоялістів × rand(0.8–1.2)`
5. **Якщо повстанці перемогли** → новим Королем стає той повстанець з найбільшим особистим внеском армії
6. **Якщо Король вистояв** → повстанці –50% армії; Король може `/punish @user` — відібрати замки або /mute на 24г

### ⛓️ Маріонетки — шлях до свободи
- **Підстава**: захоплено останній замок гравця → він стає Маріонеткою
- **Шлях до свободи**: +10 БН/день + +1 БН за кожні 50 повідомлень
- **Таємна диверсія** `/sabotage`: –X воїнів/год у Власника, +15 БН Маріонетці (можна раз на 24г)
- **Повстання маріонетки** `/rebel` (при 100 БН): якщо армія Маріонетки > гарнізон Власника — свобода
- **Власник**: `/mercy @puppet` → –20 БН маріонетки; `/garrison N @castle` → заморожує приріст БН

### ⚔️ Тривалість гри
- Гра **нескінченна** — постійний перерозподіл сил без фінальної точки
- Сезонні рандомні події раз на добу підтримують динаміку

---

## Поетапний план реалізації

---

### Етап 0 — Ініціалізація проекту
- [ ] Створити структуру папок `bot/`, `webapp/`, `config/`
- [ ] `requirements.txt` з aiogram, sqlalchemy, apscheduler, aiohttp
- [ ] `.env` для токена бота та SECRET_KEY WebApp
- [ ] `config.py` — зчитування env-змінних
- [ ] `bot/main.py` — точка входу, запуск бота + APScheduler

---

### Етап 1 — База даних (SQLAlchemy + SQLite)

#### Таблиці:

**users** — профіль кожного Лорда
| Поле | Тип | Опис |
|---|---|---|
| user_id | INTEGER PK | Telegram User ID |
| username | TEXT | @нікнейм |
| role | TEXT | 'lord' / 'king' / 'puppet' |
| army_size | INTEGER | Поточна армія |
| master_id | INTEGER FK | ID власника (для маріонетки) |
| independence_points | INTEGER | БН (0–100, тільки для маріонеток) |
| alliance_id | INTEGER FK | ID коаліції |
| last_activity_count | INTEGER | Лічильник повідомлень (для БН) |
| muted_until | DATETIME | Час зняття темниці |

**castles** — замки у грі
| Поле | Тип | Опис |
|---|---|---|
| castle_id | INTEGER PK | ID замку |
| name | TEXT | Назва (Уінтерфелл, тощо) |
| owner_id | INTEGER FK | Поточний власник |
| garrison | INTEGER | Гарнізон Власника (для маріонеток) |
| army_per_hour | INTEGER | Приріст воїнів/год (базово 10) |

**alliances** — коаліції
| Поле | Тип | Опис |
|---|---|---|
| alliance_id | INTEGER PK | ID альянсу |
| name | TEXT | Назва коаліції |
| leader_id | INTEGER FK | Лідер |
| member_ids | TEXT | JSON-список учасників |

**battles** — поточні/завершені битви
| Поле | Тип | Опис |
|---|---|---|
| battle_id | INTEGER PK | ID битви |
| attacker_id | INTEGER FK | Атакуючий |
| defender_id | INTEGER FK | Захисник |
| castle_id | INTEGER FK | Ціль |
| attacker_army | INTEGER | Армія атакуючого |
| status | TEXT | 'pending' / 'done' |
| result | TEXT | JSON результату |
| started_at | DATETIME | Час початку |

**conspiracy** — поточна змова
| Поле | Тип | Опис |
|---|---|---|
| conspiracy_id | INTEGER PK | ID змови |
| initiator_id | INTEGER FK | Ініціатор |
| status | TEXT | 'active' / 'done' |
| rebels | TEXT | JSON {user_id: army_contribution} |
| loyalists | TEXT | JSON {user_id: army_contribution} |
| message_id | INTEGER | ID live-повідомлення в чаті |
| expires_at | DATETIME | Час завершення |

---

### Етап 2 — Ядро бота (aiogram 3.x)

#### Файлова структура `bot/`:
```
bot/
├── main.py           # Запуск, dispatcher, scheduler
├── handlers/
│   ├── common.py     # /start, /help, /throne, /my_status
│   ├── war.py        # /attack, обробка битв
│   ├── conspiracy.py # /conspiracy, голосування, фінал
│   ├── puppet.py     # /rebel, /sabotage, /mercy, /garrison
│   └── alliance.py   # /alliance_create, /alliance_invite, /alliance_leave
├── middlewares/
│   └── antiflood.py  # Throttling для кнопок
├── services/
│   ├── battle.py     # Логіка розрахунку битви
│   ├── economy.py    # Щогодинний приріст, податки
│   ├── king.py       # Влада Короля (/mute, /punish)
│   └── scheduler.py  # APScheduler jobs
├── keyboards/
│   └── inline.py     # Всі InlineKeyboardMarkup
├── models/
│   └── db.py         # SQLAlchemy моделі + сесія
└── texts/
    └── messages.py   # Всі рядки повідомлень (атмосферні)
```

#### Основні хендлери:
- `/start` → реєструє Лорда у БД, видає вітальне ПП
- `/throne` → кнопка "🗺️ Відкрити Карту" (WebApp) + короткий текстовий зведення
- `/my_status` → кнопка "🛡️ Мій Профіль" (WebApp) + текстова картка в ПП
- `/attack @username [кількість]` → ініціює битву (повідомлення в чат, таймер 5 хв)
- `/conspiracy` → тільки в ПП через Deep Link; запускає "Велику Змову" в чаті
- `/mute @username` → тільки Король; бот викликає restrictChatMember на 10 хв
- `/punish @username` → тільки Король після перемоги над змовою
- `/rebel` → тільки Маріонетка з 100 БН
- `/sabotage` → тільки Маріонетка, раз на 24г
- `/mercy @puppet` → Власник знижує БН маріонетки
- `/garrison N` → Власник ставить гарнізон у замок маріонетки

---

### Етап 3 — Ігрова логіка

#### 3.1 Розрахунок битви (`services/battle.py`)
```
attack_power = attacker_army × random(0.8, 1.2)
defense_power = defender_army × random(0.8, 1.2)

if attack_power > defense_power:
    winner = attacker
    attacker_losses = int(attacker_army × 0.25)
    defender_losses = int(defender_army × 0.60)
    # замок переходить переможцю
else:
    winner = defender
    attacker_losses = int(attacker_army × 0.50)
    defender_losses = int(defender_army × 0.30)
```

#### 3.2 APScheduler Jobs (`services/scheduler.py`)
- **Кожну годину**: `economy_tick()` → нараховує `castle.army_per_hour` кожному власнику замків; стягує 30% податок від маріонеток; перевіряє ліміт армії
- **Кожні 24 години**: `daily_tick()` → +10 БН кожній маріонетці; рандомний івент у чат
- **Кожні 5 хвилин після атаки**: `resolve_battle()` → підраховує результат, постить у чат
- **APScheduler job для кожної змови**: `resolve_conspiracy()` → спрацьовує по `expires_at`

#### 3.3 Механіка лічильника активності (для БН маріонетки)
- Middleware або message handler слухає всі повідомлення в чаті
- +1 до `last_activity_count` для Маріонеток
- Коли `last_activity_count % 50 == 0` → +1 БН

#### 3.4 Антифлуд
- Middleware `ThrottlingMiddleware`: не більше 1 обробки CallbackQuery з одного user_id на 2 секунди
- `answerCallbackQuery()` завжди викликається для підтвердження (спливаюче повідомлення)

---

### Етап 4 — WebApp (Mini App)

#### Структура `webapp/`:
```
webapp/
├── index.html        # Точка входу, роутер між "екранами"
├── style.css         # Стилі: темна тема, середньовічна палітра
├── app.js            # Логіка: ініціалізація, fetch до API, рендер
├── screens/
│   ├── map.js        # Інтерактивна SVG/сітка-карта замків
│   ├── profile.js    # Картка Лорда
│   ├── diplomacy.js  # Коаліції та Змова
│   └── attack.js     # Слайдер вибору армії для атаки
└── assets/
    └── (іконки, фони)
```

#### Авторизація WebApp:
1. `Telegram.WebApp.initData` передається з кожним запитом до API у заголовку
2. Сервер валідує підпис `initData` за допомогою `HMAC-SHA256` та токена бота
3. Витягує `user.id` → знаходить гравця в БД

#### REST API (aiohttp/FastAPI) для WebApp:
- `GET /api/state` → повний стан гри (замки, гравці, Король)
- `GET /api/me` → профіль поточного гравця
- `POST /api/attack` → `{target_id, army_amount}` → ініціює битву
- `POST /api/conspiracy/join` → `{side: 'rebel'|'loyalist'|'neutral'}` → таємний вибір
- `POST /api/alliance` → керування коаліцією

#### Карта замків (SVG-сітка):
- Проста HTML-таблиця або SVG з "клітинками"-замками
- Кожен замок має колір власника (генерується з user_id → HSL колір)
- Клік → модальне вікно із інфо + кнопка "Атакувати" (відкриває слайдер)

#### UI/UX деталі:
- Haptic feedback: `Telegram.WebApp.HapticFeedback.impactOccurred('medium')` при підтвердженні дії
- MainButton: велика нативна кнопка "ПІДТВЕРДИТИ ДІЮ" внизу
- Темна тема: `Telegram.WebApp.colorScheme` → CSS клас `dark`/`light`
- Lottie-анімація при загрузці результатів бою (опційно)

---

### Етап 5 — Безпека та Полірування

- [ ] Валідація `initData` на кожен WebApp-запит
- [ ] Перевірка прав бота в чаті при старті (`getChatMember` для self)
- [ ] Обробка `TelegramBadRequest` (наприклад, коли Король намагається замутити Creator)
- [ ] Логування всіх ключових подій (`logging` модуль)
- [ ] Перевірка, що бот є адміном перед restrictChatMember
- [ ] Захист від одночасних битв: один гравець може мати лише одну активну атаку

---

## Структура папок усього проекту

```
ThronesBot/
├── .agents/
│   ├── skills/
│   │   ├── aiogram_bot_development.md
│   │   ├── database_architecture.md
│   │   ├── telegram_webapp_integration.md
│   │   └── game_mechanics_implementation.md
│   └── rules.md
├── bot/
│   ├── handlers/
│   ├── middlewares/
│   ├── services/
│   ├── keyboards/
│   ├── models/
│   ├── texts/
│   └── main.py
├── webapp/
│   ├── screens/
│   ├── assets/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── config/
│   └── config.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Порядок реалізації для агента

1. **Спочатку** → `requirements.txt`, `.env.example`, `config.py`, структура папок
2. **Потім** → `models/db.py` (всі таблиці)
3. **Потім** → `bot/main.py` скелет + handlers/common.py
4. **Потім** → `services/battle.py` + `handlers/war.py`
5. **Потім** → `services/economy.py` + APScheduler jobs
6. **Потім** → `handlers/conspiracy.py` + FSM для змови
7. **Потім** → `handlers/puppet.py` (маріонетки)
8. **Потім** → `handlers/alliance.py`
9. **Потім** → `webapp/` (REST API + фронтенд)
10. **Наприкінці** → `middlewares/antiflood.py`, безпека, логування
