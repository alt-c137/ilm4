from django.db.models import Q
from django.shortcuts import render

from apps.core.decorators import module_required

from .models import Org


@module_required('refugee')
def index(request):
    """Справочник: чипсы стран, поиск, карточки с кнопками звонка и картой."""
    orgs = Org.objects.all()
    country = request.GET.get('country', '').strip()
    q = request.GET.get('q', '').strip()
    if country:
        orgs = orgs.filter(country=country)
    if q:
        orgs = orgs.filter(Q(name__icontains=q) | Q(city__icontains=q) |
                           Q(address__icontains=q))
    countries = (Org.objects.values_list('country', flat=True)
                 .distinct().order_by('country'))
    return render(request, 'refugee/index.html', {
        'orgs': orgs[:100],
        'countries': countries,
        'country': country,
        'q': q,
    })
