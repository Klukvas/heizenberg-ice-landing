from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(ModelAdmin):
    list_display = ('title', 'image_thumb', 'is_published', 'published_at', 'updated_at')
    list_filter = ('is_published',)
    list_editable = ('is_published',)
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('image_preview', 'created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author', 'excerpt'),
        }),
        ('Контент', {
            'fields': ('content',),
        }),
        ('Зображення', {
            'fields': ('image', 'image_preview'),
        }),
        ('Публікація', {
            'fields': ('is_published', 'published_at'),
        }),
        ('Службове', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def image_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:50px;height:35px;object-fit:cover;border-radius:4px;"/>',
                obj.image.url,
            )
        return format_html('<span style="color:#999;">--</span>')
    image_thumb.short_description = ''

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:400px;border-radius:8px;"/>',
                obj.image.url,
            )
        return format_html('<em>Немає зображення</em>')
    image_preview.short_description = 'Превʼю'
