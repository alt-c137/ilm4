"""robots.txt, sitemap.xml (для Google/Яндекса), service worker и офлайн-страница."""
from pathlib import Path

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_page

from .models import Moderation

PRIVATE = ['/admin/', '/accounts/', '/chat/', '/wallet/', '/payments/', '/deals/', '/my/', '/tg/', '/nikah/',
           '/notifications/', '/settings/']


@cache_page(3600)
def robots(request):
    lines = ['User-agent: *'] + [f'Disallow: {p}' for p in PRIVATE]
    lines.append(f'Sitemap: {request.build_absolute_uri("/sitemap.xml")}')
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')


def service_worker(request):
    js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'sw.js').read_text()
    resp = HttpResponse(js, content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-cache'
    return resp


def offline(request):
    from django.shortcuts import render
    return render(request, 'offline.html')


class _Approved(Sitemap):
    changefreq = 'daily'
    limit = 5000
    model_path = ''
    url_name = ''

    def items(self):
        from django.apps import apps
        return apps.get_model(self.model_path).objects.filter(status=Moderation.APPROVED).order_by('-pk')

    def location(self, obj):
        return reverse(self.url_name, args=[obj.pk])


def _sm(model_path, url_name, extra=None):
    return type(f'SM_{model_path}', (_Approved,), {'model_path': model_path, 'url_name': url_name, **(extra or {})})


class StaticSitemap(Sitemap):
    changefreq = 'weekly'

    def items(self):
        return ['/', '/prayer/', '/buy/', '/map/', '/health/', '/jobs/', '/services/', '/transport/', '/forum/',
                '/news/', '/library/', '/migration/', '/refugee/', '/catalog/', '/rules/', '/privacy/']

    def location(self, item):
        return item


class NewsSitemap(Sitemap):
    changefreq = 'daily'

    def items(self):
        from apps.news.models import NewsPost
        return NewsPost.objects.order_by('-pk')[:2000]

    def location(self, obj):
        return f'/news/{obj.slug}/'


class ListingSitemap(_Approved):
    model_path, url_name = 'market.Listing', 'market:detail'

    def items(self):
        return super().items().filter(is_active=True)


SITEMAPS = {
    'pages': StaticSitemap, 'news': NewsSitemap, 'buy': ListingSitemap,
    'jobs': _sm('jobs.Vacancy', 'jobs:detail'), 'places': _sm('maps.HalalPlace', 'maps:detail'),
    'doctors': _sm('health.Doctor', 'health:detail'), 'stories': _sm('migration.Story', 'migration:detail'),
    'forum': _sm('forum.Topic', 'forum:detail'),
}
