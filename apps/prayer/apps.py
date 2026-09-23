from django.apps import AppConfig


class PrayerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.prayer'
    verbose_name = 'Время намаза'

    # Отдельный блок на главной больше не регистрируется: расписание, текущий
    # намаз и отсчёт живут в карточке «Сегодня» (core/includes/today.html).
    # Шаблон prayer/blocks/widget.html оставлен для других страниц.
