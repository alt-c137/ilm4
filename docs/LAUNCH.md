# ilm4 — запуск: ПК, сервер, подключения

Коротко: сайт готов к запуску на одном VPS через Docker. Без внешних ключей
работает всё, кроме входа через Google, писем, пополнения баланса и надёжных
звонков через мобильный интернет. Ниже — что и где подключить.

---

## 1. Запуск на своём ПК (Windows + WSL)

```bash
cd ~/projects/ilm4
source .venv/bin/activate
pip install -r requirements/dev.txt      # один раз / после обновлений
python manage.py migrate                 # применить новые миграции
python manage.py runserver               # http://127.0.0.1:8000
```

База на ПК — файл `db.sqlite3` (SQLite), ничего ставить не нужно.
Камера и микрофон (голосовые, кружки, звонки) работают только на
`localhost` или по https (ngrok).

### Вход в админку (`/admin/`)

Суперпользователь уже есть: логин **isa** (вход по его email).
Пароль забыт — задать новый:

```bash
python manage.py changepassword isa
```

После пароля админка попросит **код 2FA** из приложения-аутентификатора
(Google Authenticator и т. п.), куда был добавлен «ilm4». Если телефона с этим
кодом нет — сбросить 2FA (при следующем входе покажет новый QR):

```bash
python manage.py shell -c "from django_otp.plugins.otp_totp.models import TOTPDevice; TOTPDevice.objects.filter(user__username='isa').delete()"
```

Новый админ: `python manage.py createsuperuser`.

---

## 2. Запуск на сервере

**Сервер:** любой VPS с Ubuntu 22/24, 2 vCPU / 4 ГБ RAM / 40+ ГБ диска
(Hetzner CX22 ≈ 4–5 €/мес, Timeweb/Aeza ≈ 5–8 $/мес). Подробнее о росте и
цене — `docs/ROADMAP.md`.

```bash
# 1) Docker на сервере
curl -fsSL https://get.docker.com | sh

# 2) Код и настройки
git clone <ссылка-на-репозиторий> ilm4 && cd ilm4
cp .env.example .env && nano .env
```

В `.env` обязательно:

| Переменная | Что вписать |
|---|---|
| `SECRET_KEY` | `python3 -c "import secrets;print(secrets.token_urlsafe(50))"` |
| `POSTGRES_PASSWORD` | длинный случайный пароль |
| `ALLOWED_HOSTS` | `ilm4.com,www.ilm4.com,<IP сервера>` |
| `CSRF_TRUSTED_ORIGINS` | `https://ilm4.com,https://www.ilm4.com` |
| `CHAT_ENCRYPTION_KEY` | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — **сохранить копию**, без ключа переписку не прочитать |
| `SECURE_SSL` | `True` — после подключения Cloudflare (шаг 3) |

```bash
# 3) Старт (БД, Redis, сайт, nginx, фоновые задачи)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec app python manage.py createsuperuser

# Обновление после git push
git pull && docker compose -f docker-compose.prod.yml up -d --build

# Логи, если что-то не так
docker compose -f docker-compose.prod.yml logs -f app
```

Что поднимается: `db` (PostgreSQL 16 + PostGIS), `redis` (чат/звонки, кэш,
лимиты), `app` (daphne: страницы + WebSocket), `nginx` (порт 80, статика,
медиа), `jobs` (раз в час автопринятие сделок, раз в 6 ч курсы валют).
Миграции и сборка статики выполняются автоматически при старте.

**Бэкапы** — обязательно с первого дня:

```bash
sh scripts/backup.sh          # вручную
crontab -e                    # каждую ночь:
# 30 3 * * * cd /root/ilm4 && sh scripts/backup.sh >> backups/backup.log 2>&1
```

Раз в неделю скачивайте свежую копию с сервера (или в облако).

---

## 3. Что подключить

| Что | Зачем | Где взять | Куда вписать | Статус кода |
|---|---|---|---|---|
| **Домен + Cloudflare** | https, защита от атак, CDN | регистратор домена → DNS на Cloudflare, A-запись на IP сервера, SSL «Flexible» (позже «Full») | `.env`: `SECURE_SSL=True`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | ✅ готов |
| **Вход через Google** | регистрация в 1 клик | Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web). Redirect URI: `https://ilm4.com/accounts/google/callback/` | `.env`: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | ✅ готов |
| **Почта (SMTP)** | «Забыли пароль?» | Brevo (300 писем/день бесплатно), Mailgun, Яндекс 360 | `.env`: `EMAIL_URL=smtp+tls://логин:пароль@smtp-relay.brevo.com:587`, `DEFAULT_FROM_EMAIL` | ✅ готов |
| **TURN-сервер** | звонки через мобильный интернет | coturn на этом же VPS или Metered.ca (есть бесплатный лимит) | админка → Настройки сайта → `webrtc_turn_*` | ✅ готов |
| **Карта** | карта халяль/мечетей | Leaflet + OpenStreetMap, ключ не нужен | — | ✅ готов; при большом трафике OSM просит свой тайл-сервис (MapTiler/Stadia, бесплатный тариф) — замена одной строки |
| **Пополнение: карты UZ** | баланс кошелька | Payme Business / Click — нужен ИП/ООО и договор мерчанта | `.env`: `PAYME_MERCHANT_ID`, `PAYME_SECRET` | ⚠️ только заготовка: обмен с Payme и вебхук надо дописать (~2–3 дня) |
| **Пополнение: Visa/MC** | международные карты | Stripe — только на компанию в поддерживаемой стране (не UZ) | `.env`: `STRIPE_*` | ⚠️ заготовка |
| **Пополнение: крипта** | USDT/BTC | NOWPayments, CryptoCloud | `.env`: `CRYPTO_GATEWAY_*` | ⚠️ заготовка |
| **SMS** | подтверждение телефона | Eskiz.uz / Play Mobile (UZ), Twilio (мир) | — | ❌ нет в коде: сейчас телефон не подтверждается |
| **Мониторинг** | узнать, что сайт упал | UptimeRobot (бесплатно), Sentry (ошибки) | — | по желанию |

Пока ключей нет, соответствующая кнопка просто не показывается или пишет
«скоро» — сайт не падает.

**Деньги.** Хранение чужих денег (эскроу, вывод) юридически требует
лицензии/партнёра-банка. Поэтому `escrow_enabled` и `wallet_payouts_enabled`
по умолчанию выключены: баланс тратится только на услуги платформы.

---

## 4. База данных

- **Сервер:** PostgreSQL 16 + PostGIS 3.4 (образ `postgis/postgis`), всё
  настроено в `docker-compose.prod.yml`. Подключение — `DATABASE_URL` в compose,
  руками ничего настраивать не нужно. В образ приложения добавлены GDAL/GEOS
  (без них Django не подключится к PostGIS).
- **PostGIS сейчас установлен, но не используется**: «мечеть рядом» считает
  расстояние в Python — для тысяч мест этого хватает. Когда мест станет
  десятки тысяч, переведём координаты в `PointField` с гео-индексом.
- **На ПК:** SQLite. Миграции проверены на SQLite; на PostgreSQL их первым
  прогонит сервер. Чтобы проверить заранее: Docker Desktop → Settings →
  Resources → WSL Integration → Ubuntu, затем `docker compose up -d` и в `.env`
  раскомментировать `DATABASE_URL`.
- **Redis** — в compose; держит чат, звонки, кэш и лимиты попыток.

---

## 5. Аудит безопасности (23.09.2026) — что исправлено

| Было | Исправлено |
|---|---|
| В никахе и библиотеке фото/обложки сохранялись без проверки: можно было загрузить HTML со скриптом и выполнить его на нашем домене | Проверка Pillow + расширение; nginx отдаёт `/media/` с `nosniff` и CSP `sandbox` |
| Платные книги скачивались прямой ссылкой `/media/books/files/…` | Прямой доступ закрыт, файл — только после проверки оплаты |
| Буст, контакт в никахе, покупка книги срабатывали по GET — чужой сайт мог списать деньги картинкой | Только POST с CSRF-токеном |
| Не было защиты от подбора пароля | 8 ошибок на логин / 30 на IP за 15 минут; пароли — минимум 8 символов, не из списка популярных |
| Не было восстановления пароля | «Забыли пароль?» по email, лимит 5 писем в час с IP |
| Выключатели звонков скрывали кнопки, но сервер всё равно пересылал сигналы | Проверка на сервере; лимит сообщений в WebSocket (анти-флуд) |
| Диалог грузил всю историю | Последние 300 сообщений |
| В зависимостях не было `django-taggit` и `praytimes` — на сервере сайт бы не стартовал | Добавлены, проверено чистой установкой |
| Образ без GDAL при `postgis://` — сайт бы не стартовал | GDAL в Dockerfile |
| За Cloudflare при `SECURE_SSL=True` — бесконечный редирект | nginx передаёт протокол и реальный IP от Cloudflare |
| Недоступный сервис погоды тормозил главную на 3 с каждый раз | Сбой кэшируется на 5 минут |
| Автопринятие сделок и курсы не запускались по расписанию | Сервис `jobs` в compose |
| Не было бэкапов | `scripts/backup.sh` + cron |

**Известно, не критично к запуску:**

- Нет подтверждения email при регистрации и капчи. Боты могут
  регистрироваться, а чужой email можно «занять» заранее. Рекомендуем
  Cloudflare Turnstile и письмо-подтверждение.
- Отзывы может оставить любой вошедший пользователь, без сделки. Накрутку
  разбирает модерация.
- TURN-логин виден участникам чата; при росте перейти на временные логины.
- Переписка шифруется в базе (Fernet), это **не** сквозное шифрование
  (E2E). Администратор сервера с ключом может её прочитать.
