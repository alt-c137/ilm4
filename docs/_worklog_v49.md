# Рабочий журнал v49 (для себя; пользователь читает ГОТОВНОСТЬ.md и ЧТО_ДОДЕЛАТЬ.md)

Запрос пользователя (3 октября 2026): «сыро, даже близко не Telegram» — изучить механику Telegram и VK и повторить;
свои папки чатов; больше нижних кнопок; просмотр аватарок; основа под сторис / шортсы / подарки; лента на главной
(не ломая главную); трекер до идеала; дизайн «как у команды» + бэкап; карта; чат с ИИ (мнение); файл «что есть /
что работает / что тестить / когда запускаться»; честно — что НЕ сделано.

Бэкап до начала: `backups/ilm4_2026-10-02_before_v49.tar.gz`.

Источники по Telegram: telegram.org/faq, telegram.org/evolution, telegram.org/blog/folders, core.telegram.org (ChatFolder).

## Порядок (отмечать по мере готовности)

### A. Мессенджер — механика Telegram
- [ ] A1 модели: ChatFolder, ChatState (закреп, архив, «не прочитано», черновик, очистка истории), Message.reply_to /
      forward / edited_at / pinned_at, Reaction, HiddenMessage, ProfilePhoto; миграции
- [ ] A2 services: папки (правила как в Telegram: типы + свои чаты, исключить «без звука / прочитанные / архив»,
      10 папок, 100 чатов), архив (всплывает при новом сообщении, если не «без звука»), закреп (5 в общем списке),
      ответ, пересылка, правка (48 ч), удалить у себя / у всех, закреп сообщений, реакции, «печатает…», Избранное,
      поиск по чату, упоминания @имя
- [ ] A3 сайт: список чатов (вкладки-папки, архив, меню чата), настройка папок, чат (ответ, реакции, меню, закреп,
      пересылка, правка, поиск, «печатает…»)
- [ ] A4 API + приложение: то же
- [ ] A5 просмотр аватарок (история фото профиля, листание)
- [ ] A6 опросы; комментарии к постам канала (если останется время — иначе честно в «не сделано»)

### B. Нижние кнопки: до 6, свой порядок (вместе с «Профилем»), больше разделов
### C. Лента (как ВК) на главной: переключатель «Главная · Лента», лайки, комментарии, репост
### D. Основа: сторис, короткие видео, подарки — модели, API, выключатели «скоро»
### E. Трекер: календарь-теплокарта, шаблоны, время дня, цель «N раз в неделю», пауза/архив, заметки, чат трекера
### F. Карта: интерфейс
### G. ИИ-помощник: мнение + основа
### H. Дизайн: проход по ключевым экранам, снимки
### I. Документы: ГОТОВНОСТЬ.md, ЧТО_ДОДЕЛАТЬ.md, docs/MESSENGER.md, память; тесты, переводы, tsc, lint

## Заметки по ходу
- A1–A2 готовы: apps/chat/folders.py, msgops.py, models (ChatFolder, ChatState, Reaction, HiddenMessage, Message.reply_to/
  fwd_enc/edited_at/pinned_at/comment_of), accounts.ProfilePhoto + photo_signals.py, User.forward_privacy/invite_privacy.
  Тесты: apps/chat/tests/test_telegram_core.py (20), apps/api/tests/test_chat_tg.py (7).
- A3 сайт готов: _threads.html (вкладки tgtabs, архив), static/js/chatlist.js (меню чата), static/css/tg.css,
  chat.js (ответ, правка, реакции, закреп, пересылка, поиск, «печатает…», черновик), folders.html, folder_form.html, post.html.
- API готов: /chat/folders/, /chat/<id>/state/<action>/, /chat/<id>/draft/, /chat/msg/<id>/<edit|raw|pin|unpin|react|hide|delete>/,
  /chat/forward/, /chat/<id>/search/, /chat/saved/, /chat/<id>/post/<msg>/, /me/photos/; /chat/ отдаёт tabs.
- Скриншоты: старый scratchpad 81a27327… (env.sh, site.py, flow.py, restart.sh; демо-сервер :8999 на копии базы).
  Эмодзи-шрифт для снимков поставлен в ~/.fonts.
- A полностью: сайт (photoview.js, приватность пересылки/приглашений), приложение (chats.tsx вкладки/архив/свайп, chat/[id].tsx
  ответ/правка/реакции/закреп/поиск/черновик/«печатает», forward.tsx, folders.tsx, folder/[id].tsx, post/[id].tsx, photo-viewer.tsx).
  НЕ сделано в A: опросы, переход из уведомления сразу к сообщению, выбор нескольких сообщений, просмотр медиа чата в профиле с листанием.
- B готово: tabs.SLOTS=5, новые вкладки feed/jobs/transport/forum/library (сайт и приложение).
- C+D готово: apps/social (Post, PostPhoto, Follow, Like, Comment, Story, StoryView, Short, Gift, UserGift; services, views, api views_social),
  сайт /feed/ (feed.js, feed.css, переключатель «Главная · Лента», стена и подписка в профиле), приложение ui/feed.tsx, feed/new, feed/comments,
  tab-feed, переключатель на главной, стена в профиле. Модули: feed on, stories on (фото), shorts soon, gifts soon (основа).
  Старый прототип ленты (core.feed, core/feed.html, стили в features.css) удалён.
  Демо-файлы в общем media/: avatars/demo_ava_*.jpg, posts/, stories/ (снимки) — убрать в конце.
- E (трекер), F (карта) готовы. G (ИИ-помощник): apps/assistant (models, tools.py, services.py — Claude Opus 5.5,
  ручной цикл инструментов, история только дописывается, fallbacks='default'), сайт /assistant/, API /assistant/…,
  приложение app/assistant.tsx, ссылка в Профиле и в каталоге. Тесты apps/assistant/tests (6, с подменой клиента).
- H: правки по снимкам (форма ключа помощника, лишняя полоса разделов над лентой на телефоне, «прыжок» сердечка
  в ленте приложения). Бэкап дизайна: backups/design_2026-10-03_before_polish.tar.gz.
- I: переводы uz/en 100% (сайт 2843, приложение 913; JS-строки T('…') теперь тоже собираются), ГОТОВНОСТЬ.md,
  ЧТО_ДОДЕЛАТЬ.md, docs/MESSENGER.md §6.2, ПОДКЛЮЧЕНИЯ.md §5 (помощник). Демо-файлы из media/ удалены.
  Старая галочка SiteSettings.feed_enabled спрятана в админке (поле оставлено, чтобы не делать миграцию).
- Итог: все пункты A–I закрыты; что не сделано — список в ГОТОВНОСТЬ.md «Чего НЕТ».

## v50 (3 октября 2026, вечер) — по замечаниям пользователя
- Главная «слиплась»: класс .hb трекера (tracker.css грузится на всех страницах) задел блоки главной .hb → в трекере теперь .hbt.
- Эмодзи → SVG: apps/core/icons_lucide.py (собирает scripts/icons_build.py из lucide-static, ISC), теги {% ico %} / {% hicon %};
  привычки хранят ключ значка (tracker 0003_icon_keys), карта — ключи категорий; приложение — MaterialCommunityIcons (HabitIcon, PlaceIcon).
- Чаты: вкладок нет, пока нет папок; значки папок убраны. Лента без вкладок. counts_privacy (accounts 0016).
- Редактор фото v2: static/js/photoedit.js (canvas) и mobile/src/ui/photo-editor.tsx (SVG + FeColorMatrix, expo-image-manipulator);
  useAvatarPick — свой кадр аватара вместо системного.
- persona.py — маска никяха в чате; spaces.py — сообщества (chat 0015_spaces, core 0041_module_communities).
- Помощник: providers.py (Claude / OpenAI-совместимые, список адресов — защита от SSRF), briefing() без ИИ, AssistantPlan,
  read_chats по разрешению (assistant 0002).
- Скорость: на сенсорных экранах без backdrop-filter у шапок, content-visibility у списков.
- Снимки: инструменты пересозданы в scratchpad этой сессии (env.sh, site.py, appshot.py, pedit.py, apped.py, restart.sh).

## v51 (3 октября 2026, ночь) — «по факту как в Telegram», Discord, аккаунты, аналитика
- Источник поведения — код telegram-tt (calculateDimensions, структура настроек, галочки, разделы поиска), не память.
  В аккаунт Telegram пользователя не входим.
- Чаты: размеры фото в meta (w, h) → пропорции без обрезки; галочки в группах (events.decorate `_room_read`, chat.read `until`);
  finder.py — единый поиск; accounts.Contact (0017) — «Контакты»; время у фото — поверх/в конце подписи (chat.css, :has()).
- Настройки сайта: core/settings.html — список разделов + ?s=…; профиль ?s=edit|privacy|links. tabs.py: SLOTS=20, START, start_url.
- Мультиаккаунт: accounts/multi.py, DeviceAccount (0018), кука ilm4_accts; приложение — lib/storage getAccounts/setAccounts.
- Сообщества: chat 0016_discord — SpaceRole/SpaceInvite/SpaceLog/SpaceTask, Thread.space_private/space_topic; spaces.py переписан
  (perms_of/can, _sync_member/_sync_thread); voice.py + static/js/voice.js (mesh, MAX_PEERS=8), проверено в двух браузерах.
- Лента: social.Saved (0002), репост одной кнопкой, rank() — перестановка внутри страницы по интересам; на ПК .feedwrap2 + .feedside.
- apps/metrics: Use, /m/ (sendBeacon), /moderation/stats/; приложение lib/metrics.ts.
- static/js/select.js — свои выпадающие списки на ПК (data-native — оставить системный).
- conftest.py: MEDIA_ROOT в тестах — временная папка (раньше тесты никяха копили файлы в media/nikah_private; сегодняшние убраны,
  ~610 старых безвредных остались — на них нет ссылок в базе).
- Переводы 100% (сайт 3060, приложение 1010). pytest: 373 passed, 1 skipped. Ничего не закоммичено.
- Что осталось — ПЛАН.md, раздел «G».

