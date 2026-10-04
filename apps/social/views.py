"""Лента на сайте: «Для вас» и «Подписки», записи, лайки, комментарии, сторис, подписка на человека."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required

from . import services
from .models import Post
from .services import SocialError

User = get_user_model()


def _ajax(request) -> bool:
    return request.headers.get('X-Requested-With') == 'fetch'


def _fail(request, exc):
    if _ajax(request):
        return JsonResponse({'error': exc.message}, status=exc.status)
    messages.error(request, exc.message)
    return _back(request)


def _back(request, default='/feed/'):
    nxt = request.POST.get('next') or request.GET.get('next') or request.headers.get('Referer') or default
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = default
    return redirect(nxt)


@module_required('feed')
def feed(request):
    tab = request.GET.get('tab', 'for_you')
    if tab not in ('for_you', 'following') or not request.user.is_authenticated:
        tab = 'for_you'
    data = services.feed(request.user, tab, before=request.GET.get('before') or None)
    if request.GET.get('more'):
        html = render_to_string('social/_items.html', {'items': data['items'], 'user': request.user}, request=request)
        return JsonResponse({'html': html, 'next': data['next']})
    stories = services.stories_for(request.user) if services.module_on('stories') else []
    side = {}
    if request.user.is_authenticated:                       # боковая колонка на ПК: я, сохранённое, мои сообщества
        from apps.chat import spaces
        side = {'counts': services.counts(request.user, request.user), 'spaces': spaces.mine(request.user)[:6] if spaces.enabled() else []}
    from apps.core import ads
    return render(request, 'social/feed.html', {
        'side': side, 'ad': ads.pick('feed') if len(data['items']) >= 3 else None,
        'tab': tab, 'items': data['items'], 'next': data['next'], 'stories': stories,
        'stories_on': services.module_on('stories'), 'active_section': 'feed',
        'me_hue': request.user.pk % 7 if request.user.is_authenticated else 0})


@module_required('feed')
def post_detail(request, pk):
    post = services.visible_posts(request.user).filter(pk=pk).first()
    if post is None:
        raise Http404
    item = services.post_item(post, request.user)
    services.decorate([item], request.user)
    Post.objects.filter(pk=pk).update(views=post.views + 1)
    return render(request, 'social/post.html', {
        'item': item, 'comments': services.comments_for(request.user, post.key), 'target': post.key, 'active_section': 'feed'})


@module_required('feed')
def target_comments(request, target):
    """Обсуждение любой карточки ленты (объявления, новости, вакансии…)."""
    try:
        rows = services.comments_for(request.user, target)
    except SocialError:
        raise Http404 from None
    if request.GET.get('json'):
        return JsonResponse({'html': render_to_string('social/_comments.html', {'comments': rows, 'target': target}, request=request)})
    return render(request, 'social/comments.html', {'comments': rows, 'target': target, 'active_section': 'feed'})


@login_required
@module_required('feed')
@require_POST
def post_new(request):
    try:
        services.create_post(request.user, request.POST.get('text', ''), request.FILES.getlist('photos'),
                             request.POST.get('privacy', 'all'), repost_of=request.POST.get('repost_of') or None)
    except SocialError as exc:
        return _fail(request, exc)
    if _ajax(request):
        return JsonResponse({'ok': True})
    return _back(request)


@login_required
@require_POST
def post_act(request, pk, action):
    try:
        if action == 'delete':
            services.delete_post(request.user, pk)
        elif action == 'edit':
            services.edit_post(request.user, pk, request.POST.get('text', ''))
        else:
            raise Http404
    except SocialError as exc:
        return _fail(request, exc)
    return JsonResponse({'ok': True}) if _ajax(request) else _back(request)


@login_required
@require_POST
def like(request):
    try:
        return JsonResponse(services.like(request.user, request.POST.get('target', '')))
    except SocialError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)


@login_required
@require_POST
def save(request):
    try:
        return JsonResponse(services.save(request.user, request.POST.get('target', '')))
    except SocialError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)


@login_required
@module_required('feed')
def saved(request):
    """«Сохранённое»: закладки человека из ленты."""
    return render(request, 'social/saved.html', {'items': services.saved_items(request.user), 'active_section': 'feed'})


@login_required
@require_POST
def comment(request):
    target = request.POST.get('target', '')
    try:
        services.add_comment(request.user, target, request.POST.get('text', ''), request.POST.get('reply_to') or None)
        rows = services.comments_for(request.user, target)
    except SocialError as exc:
        return _fail(request, exc)
    if _ajax(request):
        return JsonResponse({'html': render_to_string('social/_comments.html', {'comments': rows, 'target': target}, request=request),
                             'count': len(rows)})
    return _back(request)


@login_required
@require_POST
def comment_delete(request, pk):
    try:
        services.delete_comment(request.user, pk)
    except SocialError as exc:
        return _fail(request, exc)
    return JsonResponse({'ok': True}) if _ajax(request) else _back(request)


@login_required
@require_POST
def follow(request, user_id):
    author = get_object_or_404(User, pk=user_id, is_active=True)
    try:
        services.follow(request.user, author, request.POST.get('on', '1') == '1')
    except SocialError as exc:
        return _fail(request, exc)
    state = services.follow_state(request.user, author)
    return JsonResponse({'following': state == 'on', 'requested': state == 'requested',
                         **services.counts(author, request.user)}) if _ajax(request) else _back(request)


@login_required
def requests_view(request):
    """Заявки в подписчики закрытого профиля: одобрить или отклонить."""
    if request.method == 'POST':
        uid = request.POST.get('user', '')
        if uid.isdigit():
            services.answer_request(request.user, int(uid), request.POST.get('ok') == '1')
        return redirect('social:requests')
    return render(request, 'social/requests.html', {'people': services.follow_requests(request.user), 'active_section': 'feed'})


@login_required
@require_POST
def story_new(request):
    try:
        services.add_story(request.user, request.FILES.get('photo'), request.POST.get('caption', ''), request.POST.get('privacy', 'all'))
    except SocialError as exc:
        return _fail(request, exc)
    return JsonResponse({'ok': True}) if _ajax(request) else _back(request)


@login_required
@require_POST
def story_act(request, pk, action):
    try:
        if action == 'view':
            services.view_story(request.user, pk, request.POST.get('reaction', ''))
        elif action == 'delete':
            services.delete_story(request.user, pk)
        elif action == 'viewers':
            return JsonResponse({'items': [{'name': v['user']['name'], 'reaction': v['reaction']}
                                           for v in services.story_viewers(request.user, pk)]})
        else:
            raise Http404
    except SocialError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)
    return JsonResponse({'ok': True})
