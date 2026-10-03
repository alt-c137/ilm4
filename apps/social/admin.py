from django.contrib import admin

from .models import Comment, Gift, Post, Short, Story, UserGift


class PhotoInline(admin.TabularInline):
    from .models import PostPhoto
    model = PostPhoto
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('author', 'text', 'privacy', 'likes', 'comments', 'hidden', 'created_at')
    list_filter = ('hidden', 'privacy')
    search_fields = ('text', 'author__email')
    raw_id_fields = ('author', 'repost_of')
    inlines = [PhotoInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'target', 'text', 'hidden', 'created_at')
    list_filter = ('hidden',)
    raw_id_fields = ('user', 'reply_to')


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ('author', 'kind', 'caption', 'views', 'expires_at')
    raw_id_fields = ('author',)


@admin.register(Short)
class ShortAdmin(admin.ModelAdmin):
    list_display = ('author', 'caption', 'duration', 'status', 'views', 'likes', 'created_at')
    list_filter = ('status',)
    list_editable = ('status',)
    raw_id_fields = ('author',)


@admin.register(Gift)
class GiftAdmin(admin.ModelAdmin):
    list_display = ('title', 'emoji', 'price', 'active', 'order')
    list_editable = ('price', 'active', 'order')


@admin.register(UserGift)
class UserGiftAdmin(admin.ModelAdmin):
    list_display = ('gift', 'sender', 'receiver', 'anonymous', 'created_at')
    raw_id_fields = ('sender', 'receiver')
