from django.shortcuts import get_object_or_404, render

from apps.core.decorators import module_required

from .models import NewsPost


@module_required('news')
def post_list(request):
    return render(request, 'news/list.html', {'posts': NewsPost.objects.all()[:30]})


@module_required('news')
def post_detail(request, slug):
    post = get_object_or_404(NewsPost, slug=slug)
    return render(request, 'news/detail.html', {'post': post})
