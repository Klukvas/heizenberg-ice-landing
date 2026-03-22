from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'image_thumb', 'slug', 'order')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    readonly_fields = ('image_preview',)

    def image_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;object-fit:cover;border-radius:4px;"/>',
                obj.image.url,
            )
        return format_html('<span style="color:#999;">—</span>')
    image_thumb.short_description = 'Фото'

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:300px;max-height:300px;border-radius:8px;"/>',
                obj.image.url,
            )
        return format_html('<em>Зображення не завантажено</em>')
    image_preview.short_description = 'Превʼю'


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('image_thumb', 'name', 'category', 'price', 'weight_kg', 'is_available', 'order')
    list_editable = ('price', 'is_available', 'order')
    list_filter = ('category', 'is_available')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('image_preview', 'image_info', 'created_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'category', 'description'),
        }),
        ('Ціна та наявність', {
            'fields': ('price', 'weight_kg', 'is_available', 'order'),
        }),
        ('Зображення', {
            'fields': ('image', 'image_preview', 'image_info'),
            'description': (
                '<div style="background:#f0f9f0;border:1px solid #c3e6c3;border-radius:8px;'
                'padding:12px;margin-bottom:8px;font-size:13px;">'
                'Завантажте фото товару (JPG, PNG, WebP). '
                'Зображення автоматично конвертується у <b>WebP</b> та '
                'зменшується до <b>1200px</b> по ширині.'
                '</div>'
            ),
        }),
        ('Службове', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def image_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:50px;height:50px;object-fit:cover;border-radius:6px;"/>',
                obj.image.url,
            )
        return format_html(
            '<div style="width:50px;height:50px;background:#1a4a1a;border-radius:6px;'
            'display:flex;align-items:center;justify-content:center;">'
            '<svg width="24" height="24" fill="none" stroke="#00ff41" stroke-width="1.5" viewBox="0 0 24 24">'
            '<path d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.41a2.25 2.25 0 013.182 0l2.909 2.91m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"/>'
            '</svg></div>'
        )
    image_thumb.short_description = ''

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:400px;max-height:400px;border-radius:8px;'
                'border:1px solid #ddd;"/>',
                obj.image.url,
            )
        return format_html(
            '<div style="width:200px;height:200px;background:#f5f5f5;border-radius:8px;'
            'display:flex;align-items:center;justify-content:center;border:2px dashed #ccc;">'
            '<span style="color:#999;font-size:13px;">Немає зображення</span></div>'
        )
    image_preview.short_description = 'Превʼю'

    def image_info(self, obj):
        if not obj.image:
            return '—'
        try:
            size_kb = obj.image.size / 1024
            name = obj.image.name
            ext = name.rsplit('.', 1)[-1].upper() if '.' in name else '?'
            return format_html(
                '<span style="color:#666;font-size:13px;">'
                '{} &middot; {:.0f} KB &middot; {}</span>',
                ext, size_kb, name,
            )
        except Exception:
            return format_html('<span style="color:#666;">{}</span>', obj.image.name)
    image_info.short_description = 'Інфо'
