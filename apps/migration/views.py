from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import module_required
from apps.core.models import Moderation

from .models import Story


@module_required('migration')
def story_list(request):
    return render(request, 'migration/list.html', {
        'stories': Story.objects.filter(status=Moderation.APPROVED)[:50],
    })


@module_required('migration')
def story_detail(request, pk):
    story = get_object_or_404(Story, pk=pk, status=Moderation.APPROVED)
    return render(request, 'migration/detail.html', {'story': story})


@login_required
@module_required('migration')
def story_create(request):
    """Форма — прямо в шаблоне (полей всего четыре)."""
    if request.method == 'POST':
        story = Story.objects.create(
            title=request.POST.get('title', '').strip()[:200],
            country_from=request.POST.get('country_from', '').strip()[:60],
            country_to=request.POST.get('country_to', '').strip()[:60],
            body=request.POST.get('body', ''),
            author=request.user,
        )
        if story.title and story.body:
            messages.success(request, 'История отправлена — после проверки появится в разделе.')
            return redirect('migration:list')
        story.delete()
        messages.error(request, 'Заполните заголовок и текст истории.')
    return render(request, 'migration/create.html')
