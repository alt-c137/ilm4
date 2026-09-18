from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import module_required
from apps.core.models import Moderation

from .forms import ReplyForm, TopicForm
from .models import Topic


@module_required('forum')
def topic_list(request):
    topics = (Topic.objects.filter(status=Moderation.APPROVED)
              .select_related('author'))
    return render(request, 'forum/list.html', {'topics': topics[:50]})


@module_required('forum')
def topic_detail(request, pk):
    topic = get_object_or_404(Topic, pk=pk, status=Moderation.APPROVED)
    form = ReplyForm()
    return render(request, 'forum/detail.html', {
        'topic': topic, 'replies': topic.replies.select_related('author'), 'form': form,
    })


@login_required
@module_required('forum')
def topic_create(request):
    form = TopicForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        topic = form.save(commit=False)
        topic.author = request.user
        topic.save()
        messages.success(request, 'Вопрос отправлен — после проверки появится на форуме.')
        return redirect('forum:list')
    return render(request, 'forum/create.html', {'form': form})


@login_required
@module_required('forum')
def reply_create(request, pk):
    topic = get_object_or_404(Topic, pk=pk, status=Moderation.APPROVED)
    form = ReplyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        reply = form.save(commit=False)
        reply.topic = topic
        reply.author = request.user
        reply.save()
    return redirect('forum:detail', pk=pk)
