from django.db.models import Q
from django.shortcuts import render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required

from .models import Org

# регионы, которые показываются всегда (даже пустыми); остальные — если есть записи
ALWAYS_REGIONS = ('asia', 'europe')


@module_required('refugee')
def index(request):
    """Справочник помощи беженцам.

    Вкладки: обзор · международные · регионы (Азия, Европа, …) → страны · адвокаты.
    Поиск — по всему справочнику.
    """
    region_names = dict(Org.REGIONS)
    tab = request.GET.get('tab', '').strip()
    country = request.GET.get('country', '').strip()
    q = request.GET.get('q', '').strip()

    present = set(Org.objects.exclude(region='').values_list('region', flat=True))
    regions = [(k, v) for k, v in Org.REGIONS
               if k != 'intl' and (k in ALWAYS_REGIONS or k in present)]
    valid_tabs = {'', 'intl', 'lawyer'} | {k for k, _ in regions}
    if tab not in valid_tabs:
        tab = ''
    if country and not tab:
        # старые ссылки ?country=… — открываем регион этой страны
        found = (Org.objects.filter(country=country).exclude(region='')
                 .exclude(region='intl').values_list('region', flat=True).first())
        if found in valid_tabs:
            tab = found

    local = Org.objects.exclude(kind__in=('intl', 'lawyer'))
    ctx = {
        'tab': tab, 'country': country, 'q': q,
        'regions': regions,
        'tab_name': region_names.get(tab, ''),
        'lawyers_count': Org.objects.filter(kind='lawyer').count(),
    }

    if q:
        ctx['results'] = Org.objects.filter(
            Q(name__icontains=q) | Q(city__icontains=q) | Q(country__icontains=q)
            | Q(address__icontains=q) | Q(notes__icontains=q))[:100]
    elif tab == 'intl':
        ctx['intl'] = Org.objects.filter(kind='intl').order_by('id')
    elif tab == 'lawyer':
        lawyers = Org.objects.filter(kind='lawyer')
        ctx['countries'] = lawyers.values_list('country', flat=True).distinct().order_by('country')
        ctx['orgs'] = lawyers.filter(country=country) if country else lawyers
    elif tab:
        in_region = local.filter(region=tab)
        ctx['countries'] = in_region.values_list('country', flat=True).distinct().order_by('country')
        ctx['orgs'] = in_region.filter(country=country) if country else in_region
    else:
        # обзор: международные + по регионам (сгруппировано)
        ctx['intl'] = Org.objects.filter(kind='intl').order_by('id')[:6]
        ctx['intl_total'] = Org.objects.filter(kind='intl').count()
        groups = []
        for key, name in regions:
            items = list(local.filter(region=key))
            if items:
                groups.append({'key': key, 'name': name, 'items': items})
        other = list(local.filter(region=''))
        if other:
            groups.append({'key': '', 'name': _('Другие страны'), 'items': other})
        ctx['groups'] = groups
    return render(request, 'refugee/index.html', ctx)
